# SDM AEO Reporting Tool — Infra Status (Oct 30, 2026, 3:35 PM PT)

Profound remains Avorio-only. This repo is the in-house, multi-client Share-of-Model tracker.

## Works now
- CLI runner across Gemini / Perplexity / Claude / OpenAI with pacing, retries, quota stop and `--resume`.
- Scoring: LLM judge (OpenAI → Anthropic → Gemini fallback) or rule-based; Share of Model, sentiment, citation fidelity, cited domains.
- **New today:** competitive share-of-voice (brand vs config competitors) CSV and report section; per-run `cost.json`; `--estimate` (no spend); `new_client.sh`; keys auto-loaded from `/home/box/.secrets`; `_SMOKE` runs kept out of the published dashboard; Share-of-Model trend table per client; Perplexity migrated to Agent API (old Sonar endpoint returned 403).
- Static dashboard `docs/` rebuilt cleanly (real runs only; currently Windows 101 has 4 real runs, Canycom/Jones Firm have none).

## Smoke test (real)
- Canycom, 2 prompts, Perplexity only, rule scoring: **$0.0057 total**. Canycom mentioned on 1/2 prompts. Stored as `output/canycom/..._SMOKE` (not published).

## Key status (checked Oct 30, 3:32 PM PT)
| Engine | Status |
|---|---|
| Perplexity | ✅ works (Agent API) |
| OpenAI | ❌ key valid, `insufficient_quota` — needs ≥$10 credit |
| Anthropic | ❌ key valid, "credit balance too low" — earlier card was declined |
| Gemini | ❌ no key in secrets (billing pending) |
Without OpenAI/Anthropic credit, scoring falls back to rule-based (no LLM judge).

## Blockers — James
1. Add billing: OpenAI and Anthropic credits (card ••3042 is in the vault — approve a specific top-up), Gemini key with billing for grounding.
2. Confirm competitor lists (Canycom and Jones Firm are PLACEHOLDER) and the facts used for accuracy scoring.
3. Git remote: create a GitHub repo (private) and decide on hosting given Pages is public (see README).
4. Avorio: no in-house config by design (Profound owns Avorio). Say if you want a parallel in-house Avorio config.

## Next steps
- Once keys are funded: `./run.sh canycom --limit 2` per engine to verify, then full monthly `./run_all.sh` (~$3/client).
- Month-over-month deltas in the client report (trend table exists on the dashboard).
- Scheduled monthly run + auto-commit of `docs/` (routine) after a git remote exists.
- Avoid committing `AVORIO_PROFOUND_HISTORY.md` (untracked, internal).

## Dashboard ↔ Profound Bot bridge (v1, Oct 30 3:40 PM PT)
- `./serve.sh` → local server on 127.0.0.1 serving `docs/` + `/api/ask`, `/api/asks`, `/api/context`, `/api/clients`. Optional token header.
- Ask panel on every dashboard page → `inbox/*.json` with an instant artifact-grounded answer; judgment questions are queued `needs_bot`.
- Profound Bot side: `./asks.sh list | context <slug> | answer <id> "text"`. Tested end-to-end (ask → auto answer → bot reply shown in panel).
- **Limits:** no push into Grok Bot chat — the bot doesn't see an ask until it runs `./asks.sh list` (by hand or from a routine). The server is local to the box, so James uses it through the bot's desktop browser, not his own laptop. No public exposure.
- **Later:** a routine that polls `needs_bot` every N minutes; a protected tunnel (e.g. Cloudflare Access) so James can open it from his laptop; LLM-written answers once OpenAI/Anthropic credit exists; real date-range/engine filtering (they're recorded but not applied yet).

## Public hosting (Oct 30, 3:50 PM PT)
- Repo is PUBLIC per James: https://github.com/JamesLFischer/sdm-aeo-reporting. Pages: https://jameslfischer.github.io/sdm-aeo-reporting/
- `docs/` = public shell + sign-in app (no client data). Client metrics + chat only via the password-gated API (`aivis.server`).
- Git history squashed to one clean commit before first push; output/, inbox/, private_site/, keys never published.
- Box needs a tunnel for the public site to reach the API. A quick tunnel's URL changes on restart and stops if the box restarts → a named Cloudflare tunnel on an SDM domain is the durable fix (James: Cloudflare account + domain).
- Client configs (prompt sets, competitor lists) ARE public in configs/. Move them out if they're sensitive.

### BLOCKER: public site can't reach the API yet (Oct 30, 3:42 PM PT)
- Tried a Cloudflare quick tunnel from the box: the box's network blocks outbound TCP 7844 and QUIC, so no tunnel connects. The server and tunnel were stopped, and `docs/config.js` stays empty.
- Result: the public site shows the shell + sign-in form, and sign-in fails with "API not reachable". Client data is not exposed anywhere.
- Fix options (James picks one):
  1. Run `./serve.sh` + `cloudflared tunnel` on a machine whose network allows Cloudflare tunnels (an SDM PC/server), with the repo + `output/` synced there. Asks then land in that machine's `inbox/`, which Profound Bot can't read from the box without syncing.
  2. Ask Grok Bot support to allow outbound tunnel traffic (TCP 7844) from the box — keeps everything on the box (best fit).
  3. Deploy the API to a small host (Fly/Render) with the outputs and a shared inbox store (more work; v2).
- Once a stable tunnel URL exists: set `window.AIVIS_API_BASE` in `docs/config.js` and push.

## FIXED: public site ↔ box via encrypted relay (Oct 30, 3:50 PM PT)
- Tunnel tests from the box: cloudflared quic + http2 (blocked, TCP 7844), localhost.run/serveo/pinggy ssh (closed), localtunnel (URL issued, data port blocked → 503), tunnelmole (port 8083 blocked), ngrok (needs James's account token; untested). Plain outbound HTTPS works.
- Shipped: encrypted ntfy.sh relay (`aivis/relay.py`, `./relay.sh`), wired into `docs/index.html`. Verified on the live Pages site in a real browser: wrong password rejected, correct password signs in, Windows 101 metrics load, ask posted and auto-answered (test ask deleted afterwards).
- Profound Bot loop unchanged: `./asks.sh list` → `./asks.sh answer <id> "..."` → reply shows in the site chat within ~30s.
- Limits: relay worker must stay running (stops if the box restarts — restart `./relay.sh`, or add a routine/watchdog). ntfy.sh public server has rate limits (fine for a few staff, not heavy use). Questions aren't pushed into Profound Bot's chat; it checks `./asks.sh list` (routine recommended). Answers to judgment questions wait for the bot.
