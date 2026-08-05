import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { triggerBuild } from "../src/trigger.js";

describe("triggerBuild", () => {
  it("POSTs a workflow_dispatch to the correct GitHub endpoint", async () => {
    /** @type {RequestInit | undefined} */
    let capturedInit;
    /** @type {string | undefined} */
    let capturedUrl;

    const fetchFn = async (url, init) => {
      capturedUrl = String(url);
      capturedInit = init;
      return new Response(null, { status: 204 });
    };

    const response = await triggerBuild(
      { GITHUB_TOKEN: "test-token-value" },
      fetchFn,
    );

    assert.equal(response.status, 200);
    assert.equal(await response.text(), "Oink build triggered");
    assert.equal(
      capturedUrl,
      "https://api.github.com/repos/Alldred/oink/actions/workflows/build-dashboard.yml/dispatches",
    );
    assert.equal(capturedInit?.method, "POST");
    assert.deepEqual(JSON.parse(String(capturedInit?.body)), { ref: "main" });

    const headers = new Headers(capturedInit?.headers);
    assert.equal(headers.get("Authorization"), "Bearer test-token-value");
    assert.equal(headers.get("Accept"), "application/vnd.github+json");
    assert.equal(headers.get("X-GitHub-Api-Version"), "2022-11-28");
    assert.equal(headers.get("User-Agent"), "oink-cloudflare-scheduler");
  });

  it("throws a useful error when GitHub returns a non-success status", async () => {
    const fetchFn = async () =>
      new Response('{"message":"Bad credentials"}', { status: 401 });

    await assert.rejects(
      () => triggerBuild({ GITHUB_TOKEN: "bad-token" }, fetchFn),
      (error) => {
        assert.ok(error instanceof Error);
        assert.match(error.message, /GitHub returned 401/);
        assert.match(error.message, /Bad credentials/);
        assert.doesNotMatch(error.message, /bad-token/);
        return true;
      },
    );
  });

  it("throws when GITHUB_TOKEN is missing", async () => {
    await assert.rejects(
      () => triggerBuild({}),
      /GITHUB_TOKEN secret is not configured/,
    );
  });
});
