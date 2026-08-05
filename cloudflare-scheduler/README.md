# Cloudflare scheduler for Oink

Cloudflare Worker cron that triggers the existing **Build and publish dashboard** GitHub Actions workflow via `workflow_dispatch`. Cloudflare only schedules; image generation and GitHub Pages deployment stay in Actions.

All commands below run in a terminal (macOS **Terminal**, or **Terminal → New Terminal** in Cursor), from this folder unless noted.

## Why Cloudflare instead of GitHub schedule?

GitHub Actions `schedule` triggers are best-effort. Under load, cron windows are often skipped, so the Kindle dashboard can go stale for long stretches. A Cloudflare Cron Trigger calls GitHub’s workflow-dispatch API on a reliable cadence (same four UTC slots as before: `:07`, `:22`, `:37`, `:52`).

## Prerequisites

- A Cloudflare account ([sign up](https://dash.cloudflare.com/sign-up); free plan is enough — no custom domain required)
- Node.js 18+ (`node -v` should print a version; install from [nodejs.org](https://nodejs.org) LTS if needed, then reopen the terminal)
- A fine-grained GitHub personal access token (PAT) for `Alldred/oink` only

There is no separate “CLI” button in the Cloudflare website for this setup. **Wrangler** is the Cloudflare CLI; you install and run it from the terminal with `npx wrangler …`.

## GitHub token (fine-grained PAT)

1. GitHub → profile → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Resource owner**: the user or org that owns `Alldred/oink`.
3. **Repository access**: **Only select repositories** → choose `Alldred/oink`.
4. **Permissions** (minimum):
   - **Actions**: **Read and write** (required to create a `workflow_dispatch`)
   - **Contents**: **Read-only** (GitHub requires this so the token can resolve the target `ref`)
5. Generate the token and copy it once. **Never commit it** to this repository or put it in `wrangler.toml`.

### Revoke or replace the token

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → revoke the old token.
2. Create a new fine-grained PAT with the same permissions.
3. Update the Worker secret (no code redeploy required for a secret-only change):

```sh
cd cloudflare-scheduler
npx wrangler secret put GITHUB_TOKEN
```

## First-time setup

```sh
cd cloudflare-scheduler
npm install
npx wrangler login
npx wrangler secret put GITHUB_TOKEN
npx wrangler deploy
```

- `wrangler login` opens a browser to authorize your Cloudflare account.
- The secret **name** on the command line must be exactly `GITHUB_TOKEN` (what the Worker reads). When prompted `Enter a secret value:`, paste the PAT and press Enter. Never put the token itself after `secret put`.
- Success must say `Uploaded secret GITHUB_TOKEN`. If it says `Uploaded secret github_pat_…`, the token was used as the name — revoke it on GitHub, create a new PAT, and run `npx wrangler secret put GITHUB_TOKEN` again. Never paste a PAT into chat, commits, or screenshots.
- After deploy, note the Worker URL Wrangler prints (for example `https://oink-scheduler.stuartalldred.workers.dev`).

`wrangler.toml` sets `workers_dev = true` so that `*.workers.dev` URL stays enabled for manual testing.

## Update or redeploy the Worker

Any time you change files under `cloudflare-scheduler/` (code, `wrangler.toml` schedule, etc.):

```sh
cd cloudflare-scheduler
npm install          # only needed if package.json / lockfile changed
npx wrangler deploy
```

Secrets are not in the repo. Changing only `GITHUB_TOKEN` uses `npx wrangler secret put GITHUB_TOKEN` (see above); you do not need to redeploy for that.

Confirm you are logged into the right Cloudflare account with:

```sh
npx wrangler whoami
```

## Test the HTTP endpoint

A `GET` or `POST` to the Worker URL runs the same dispatch logic as the cron:

```sh
curl -i https://oink-scheduler.<your-subdomain>.workers.dev/
```

Expect `200` and body `Oink build triggered`. Then check [Actions → Build and publish dashboard](https://github.com/Alldred/oink/actions/workflows/build-dashboard.yml) for a new `workflow_dispatch` run.

Treat the Worker URL as a privileged trigger: anyone who can call it can start a build (Actions minutes). Do not publish it widely; rotate `GITHUB_TOKEN` if it leaks.

### Troubleshooting `curl`

| What you see | What it usually means | What to do |
| --- | --- | --- |
| HTTP `404`, body `error code: 1042` | The `workers.dev` route is disabled for this Worker | Redeploy (`npx wrangler deploy`) with `workers_dev = true` in `wrangler.toml`, **or** in the dashboard: **Workers & Pages** → `oink-scheduler` → **Settings** → **Domains & Routes** → enable `workers.dev` |
| HTTP `502` + `GitHub returned 401` | Bad or revoked token | Create a new PAT; `npx wrangler secret put GITHUB_TOKEN` |
| HTTP `502` + `GitHub returned 403` / `404` | Token missing permissions or wrong repo | PAT must be Actions R/W + Contents Read on `Alldred/oink` only |
| HTTP `502` + `GITHUB_TOKEN secret is not configured` | Secret missing, or stored under the wrong name (e.g. `github_pat_…` instead of `GITHUB_TOKEN`) | Run `npx wrangler secret put GITHUB_TOKEN`, paste the PAT only at the prompt, confirm success says `GITHUB_TOKEN`, then retry `curl` |
| `wrangler` / network errors in the terminal | Not logged in, wrong account, or offline | `npx wrangler login` and `npx wrangler whoami` |

## Confirm cron and Actions runs

1. **Cloudflare**: Dashboard → **Workers & Pages** → `oink-scheduler` → **Logs** / **Triggers** — confirm cron invocations at `:07`, `:22`, `:37`, `:52` UTC (UK summer time is UTC+1, so those are 08, 23, 38, 53 local).
2. **GitHub**: [Actions → Build and publish dashboard](https://github.com/Alldred/oink/actions/workflows/build-dashboard.yml) — each successful dispatch should show a run with event `workflow_dispatch` (actor is the token owner).

## Local tests

```sh
cd cloudflare-scheduler
npm test
```

These unit tests mock `fetch` and cover success, GitHub error responses, and a missing secret. They do not call GitHub or Cloudflare.

## Schedule

Configured in `wrangler.toml` (UTC):

```toml
crons = ["7 * * * *", "22 * * * *", "37 * * * *", "52 * * * *"]
```

That matches the previous GitHub Actions schedule (~every 15 minutes, offset from the hour). After changing crons, run `npx wrangler deploy` again.
