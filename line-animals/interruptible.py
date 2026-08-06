"""Make long native/MLX/HTTP work interruptible with Ctrl-C.

CPython defers SIGINT until the next bytecode boundary, so a 60s Metal step
swallows Ctrl-C until it finishes. Running that work in a child process lets the
parent poll and kill the child as soon as SIGINT is delivered.

Also avoids a Queue deadlock: a large PNG can fill the pipe so ``put`` blocks in
the child while the parent waits for the child to exit before ``get``. The parent
now drains the queue while the child is still alive.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import sys
import time
import traceback
from collections.abc import Callable
from queue import Empty
from typing import Any, TypeVar

T = TypeVar("T")

_SIGINT_HITS = 0
_CLEANUP: Callable[[], None] | None = None


def install_sigint_handler(*, cleanup: Callable[[], None] | None = None) -> None:
    """
    First Ctrl-C: request a clean stop (KeyboardInterrupt when Python is awake).
    Second Ctrl-C: run cleanup and os._exit immediately.
    """
    global _CLEANUP
    _CLEANUP = cleanup
    signal.signal(signal.SIGINT, _handle_sigint)


def _handle_sigint(signum: int, frame: Any) -> None:
    del signum, frame
    global _SIGINT_HITS
    _SIGINT_HITS += 1
    if _SIGINT_HITS >= 2:
        sys.stderr.write("\nForce quit.\n")
        sys.stderr.flush()
        if _CLEANUP is not None:
            try:
                _CLEANUP()
            except Exception:
                pass
        os._exit(130)
    sys.stderr.write("\nInterrupt — stopping (Ctrl-C again to force quit)…\n")
    sys.stderr.flush()
    raise KeyboardInterrupt


def _worker_entry(queue: Any, fn: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    # Avoid nested subprocess wrappers if fn itself calls interruptible code.
    os.environ["LINE_ANIMALS_IN_WORKER"] = "1"
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        result = fn(*args, **kwargs)
        # Large PNG bytes can deadlock a small Queue pipe; spill to a temp file.
        if isinstance(result, (bytes, bytearray)) and len(result) > 64_000:
            import tempfile
            from pathlib import Path

            tmp = Path(tempfile.mkstemp(prefix="line-animals-", suffix=".bin")[1])
            tmp.write_bytes(bytes(result))
            queue.put(("ok_file", str(tmp)))
        else:
            queue.put(("ok", result))
    except BaseException as exc:
        queue.put(("err", f"{type(exc).__name__}: {exc}", traceback.format_exc()))


def run_in_subprocess(
    fn: Callable[..., T],
    *args: Any,
    label: str = "step",
    poll_s: float = 0.25,
    heartbeat_s: float = 15.0,
    **kwargs: Any,
) -> T:
    """
    Run ``fn`` in a spawned child. Parent stays responsive to Ctrl-C and kills
    the child on interrupt. Drains the result queue while the child is alive so
    large payloads cannot deadlock.
    """
    if os.environ.get("LINE_ANIMALS_IN_WORKER") == "1":
        return fn(*args, **kwargs)
    if os.environ.get("LINE_ANIMALS_NO_SUBPROCESS") == "1":
        return fn(*args, **kwargs)

    ctx = mp.get_context("spawn")
    queue: Any = ctx.Queue(1)
    proc = ctx.Process(
        target=_worker_entry,
        args=(queue, fn, args, kwargs),
        name=f"line-animals-{label}",
        daemon=True,
    )
    print(f"  ▸ {label}: starting worker …", flush=True)
    started = time.monotonic()
    last_beat = started
    proc.start()
    result: tuple[Any, ...] | None = None
    try:
        while result is None:
            try:
                result = queue.get(timeout=poll_s)
            except Empty:
                pass
            if result is not None:
                break
            if not proc.is_alive():
                try:
                    result = queue.get(timeout=1.0)
                except Empty as exc:
                    raise RuntimeError(
                        f"{label} subprocess exited with code {proc.exitcode} "
                        "and no result"
                    ) from exc
                break
            now = time.monotonic()
            if heartbeat_s > 0 and now - last_beat >= heartbeat_s:
                elapsed = int(now - started)
                print(
                    f"  ▸ {label}: still running … {elapsed}s "
                    f"(pid {proc.pid})",
                    flush=True,
                )
                last_beat = now

        assert result is not None
        status, *payload = result
        proc.join(10.0)
        if proc.is_alive():
            _kill_process(proc)
        elapsed = time.monotonic() - started
        if status == "ok":
            print(f"  ▸ {label}: done ({elapsed:.1f}s)", flush=True)
            return payload[0]  # type: ignore[no-any-return]
        if status == "ok_file":
            from pathlib import Path

            path = Path(payload[0])
            try:
                data = path.read_bytes()
            finally:
                path.unlink(missing_ok=True)
            print(f"  ▸ {label}: done ({elapsed:.1f}s, {len(data)} bytes)", flush=True)
            return data  # type: ignore[return-value]
        message, tb = payload[0], payload[1]
        print(f"  ▸ {label}: failed after {elapsed:.1f}s", flush=True)
        raise RuntimeError(f"{label} failed: {message}\n{tb}")
    except KeyboardInterrupt:
        sys.stderr.write(f"\nKilling {label}…\n")
        sys.stderr.flush()
        _kill_process(proc)
        raise
    finally:
        if proc.is_alive():
            _kill_process(proc)


def _kill_process(proc: Any) -> None:
    proc.terminate()
    proc.join(2.0)
    if proc.is_alive():
        proc.kill()
        proc.join(1.0)
