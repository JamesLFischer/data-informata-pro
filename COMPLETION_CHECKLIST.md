# SDM AEO Reporting — Completion Checklist (Oct 30, 2026, 4:05 PM PT)

Repo (public): https://github.com/JamesLFischer/sdm-aeo-reporting · Site: https://jameslfischer.github.io/sdm-aeo-reporting/

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
- [x] Docs: README (setup, run, deploy, auth), INFRA_STATUS.md, this checklist

## Only James can do ⛔
1. **Billing** — OpenAI (insufficient_quota), Anthropic (credit too low), Gemini (no key/billing). Until then runs are Perplexity-only with rule scoring. Full 4-engine run ≈ $3/client/month.
2. **Competitor + fact confirmation** — canycom and jonesfirm competitor lists and facts are PLACEHOLDER (shown as "unconfirmed" on the site).
3. **Vault the site password** — `/home/box/.secrets/AIVIS_DASH_PASSWORD` (parent bot vaults it); share with SDM staff only.
4. **Decide** whether client configs (prompt sets/competitors) may stay in the public repo.
5. **Optional:** ask GitHub Support to purge the dangling commit `fa38fd9` (briefly contained internal Avorio notes).

## Recommended (Grok Bot routines, not code)
- Every 10–15 min: `./asks.sh pending` → answer `needs_bot` questions as Profound Bot.
- On box restart: `nohup ./relay_keepalive.sh >/dev/null 2>&1 &`.
- Monthly: `./run_all.sh && ./build_dashboard.sh` (after billing).

## Known limits
- ntfy.sh public server: rate limits, ~12h message retention — fine for a few staff.
- Month-over-month deltas appear once a client has a second run of the same engine.
- Windows 101 history mixes engines (old Gemini no-grounding runs, new Perplexity run); compare per engine.
