# SDM AEO Reporting — Completion Checklist (updated Oct 30, 2026, 4:20 PM PT)

Repo (public): https://github.com/JamesLFischer/data-informata-pro · Site: https://jameslfischer.github.io/data-informata-pro/

## Done ✅
- [x] Multi-client runner (`run.sh`, `run_all.sh`) for Gemini / OpenAI / Claude / Perplexity (Perplexity on the new Agent API), with pacing, retries and `--resume`
- [x] Scoring: Share of Model, sentiment, citation fidelity, cited domains, competitor share of voice; LLM judge falls back to rules
- [x] Outputs per run: CSV log, dashboard CSV, share-of-voice CSV, XLSX, HTML+PDF report, `cost.json`
- [x] `--estimate` (no spend), `new_client.sh`, `_SMOKE`/`_EXAMPLE` runs kept out of dashboards
- [x] Baseline runs (Perplexity only, rule scoring) for canycom, jonesfirm, windows101 — $0.14 total
- [x] Private dashboard `private_site/` (gitignored) via `./build_dashboard.sh`
- [x] Public GitHub repo + Pages (`main` /docs): public shell + sign-in only; no client data or secrets in git (output/, inbox/, private_site/, .env, keys ignored; history scrubbed)
- [x] In-site sign-in + metrics + Ask Profound Bot via end-to-end-encrypted ntfy.sh relay (box needs no inbound port; tunnels are blocked on the box)
- [x] Relay keepalive (`relay_keepalive.sh` → `relay_watchdog.sh`, 60s) — kill-tested, auto-restarted; also restarts a hung relay via stale heartbeat (5 min)
- [x] Ask loop: site → `inbox/` → instant artifact-grounded answer; judgment questions → `needs_bot` → `./asks.sh pending|list|answer` → reply shows in site. Verified end to end.
- [x] Month-over-month deltas: `mom.json` + "Change vs Last Month" section in every new client report (HTML/PDF), on the private dashboard, on the site, and in auto-answers (`aivis/history.py`)
- [x] Date-range + engine filters actually applied in the site and API (`/api/context?from=&to=&engines=`, relay `context`), incl. share of voice recomputed per selected engine; asks carry structured filters
- [x] Multi-client readiness: `aivis/validate.py` (live runs refuse configs with errors; `--estimate` still allowed), `new_client.sh` rewritten in Python (safe for any brand characters, 25 TODO prompt slots with ids)
- [x] Hosted chat robustness: relay backoff/resume/429 handling/publish retries/seen-id persistence; site streaming replies, liveness ping, clear error states (wrong password vs box offline vs rate-limited vs timeout), ask retry, hidden-tab pause. Tested in Chrome: wrong password → "Wrong password."; offline channel → "SDM box is offline"; filters + ask verified
- [x] Docs: README (setup, run, deploy, auth, filters, MoM, validation, relay ops), INFRA_STATUS.md, this checklist

## Only James can do ⛔
1. **Billing** — OpenAI (insufficient_quota), Anthropic (credit too low), Gemini (no key/billing). Until then runs are Perplexity-only with rule scoring. Full 4-engine run ≈ $3/client/month.
2. **Competitor + fact confirmation** — canycom and jonesfirm competitor lists and facts are PLACEHOLDER (shown as "unconfirmed" on the site).
3. **Vault the site password** — `/home/box/.secrets/AIVIS_DASH_PASSWORD` (parent bot vaults it); share with SDM staff only.
4. **Durable hosting for the chat path** — today the site reaches the box via the public ntfy.sh relay (works, but best-effort: shared rate limits, depends on the box staying up). Durable options need James: (a) a Cloudflare account + SDM domain for a named tunnel *on a machine whose network allows it* (the box blocks tunnel ports), (b) a paid ntfy.sh plan / self-hosted ntfy on an SDM server, or (c) a small always-on host (Fly/Render) for the API. Also: a routine to restart `relay_keepalive.sh` after box reboots.
5. **Decide** whether client configs (prompt sets/competitors) may stay in the public repo.
6. **Optional:** ask GitHub Support to purge the dangling commit `fa38fd9` (briefly contained internal Avorio notes).

## Recommended (Grok Bot routines, not code)
- Every 10–15 min: `./asks.sh pending` → answer `needs_bot` questions as Profound Bot.
- On box restart: `nohup ./relay_keepalive.sh >/dev/null 2>&1 &`.
- Monthly: `./run_all.sh && ./build_dashboard.sh` (after billing).

## Known limits
- ntfy.sh public server: rate limits, ~12h message retention — fine for a few staff.
- Month-over-month deltas appear once a client has a second run of the same engine; existing reports aren't re-rendered (new runs get the section; site/dashboard show MoM for all runs now).
- Windows 101 history mixes engines (old Gemini no-grounding runs, new Perplexity run); compare per engine.

## Projects + parity (Oct 30, 2026)
- [x] Project cards home, per-project Overview / Visual / Written / Ask
- [x] Written narrative from real data; positive framing; no tool names
- [x] Locked 42-prompt battery (unbranded + branded sentiment) for Jones Firm & Canycom
- [x] SoM, citations/mentions by engine, top cited domains, own-site citations, cost
- [x] Engine-pair plan documented; Perplexity-only runs flagged
- [ ] James: confirm competitor lists (Jones Firm, Canycom)
- [ ] James: fund OpenAI + Gemini (and Anthropic for the LLM judge) to reach ChatGPT + Google parity
