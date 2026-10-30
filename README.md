# SDM AEO Tracker: Hosting and Git (added Oct 30, 2026)

## Layout
- `aivis/` engine, scoring, report and dashboard code
- `configs/<slug>.yaml` one file per client (`_template.yaml` to start a new one)
- `output/` raw runs. **Gitignored**, because it holds full AI answers and logs.
- `docs/` static dashboard (GitHub Pages serves this folder)
- `.env.example`: copy it to `.env` (gitignored). `run.sh` loads it.

## Monthly workflow
    ./run_all.sh                 # run every client
    ./build_dashboard.sh         # rebuild docs/ from output/ (add --include-examples to show mock runs)
    ./serve.sh                   # preview at http://localhost:8000
    git add docs configs && git commit -m "Monthly run $(date +%Y-%m)" && git push

## Deploy to GitHub Pages
1. Create a **private** repo, for example `gh repo create SDM-AEO-Tracker --private --source=. --push`. Otherwise create it on github.com, then `git remote add origin <url> && git push -u origin main`.
2. In the repo, go to Settings > Pages > Source: "Deploy from a branch", branch `main`, folder `/docs`.
3. Note: on free and Pro accounts, **Pages sites are public even when the repo is private**. Client results would be visible to anyone who has the URL. For a private dashboard, use a GitHub org with Enterprise (private Pages), or put Cloudflare Pages + Cloudflare Access in front of it (free for up to 50 users). With Cloudflare, connect the repo, set the build output dir to `docs`, and leave the build command empty.

## OpenAI key (james@seattledigitalmarketing.com, $20 cap)
1. Sign in at platform.openai.com as james@seattledigitalmarketing.com and create or select the SDM organization.
2. Settings > Billing: add a card and buy $20 of prepaid credits. Leave auto-recharge **off**, so spend can't go past $20.
3. Settings > Limits (Projects > your project > Limits): set the monthly budget to $20 and an email alert at $15.
4. API keys > Create new secret key, restricted to project "aeo-tracker". Put it in `.env` as `OPENAI_API_KEY=...`. Never commit it.
5. Test with `./run.sh jonesfirm --engines openai --limit 2`. If no key is present, the OpenAI engine is skipped with a warning and the other engines still run.

# SDM Multi-Client Quick Start (added Oct 30, 2026)

    ./run.sh --list                         # show client configs
    ./run.sh jonesfirm --mock               # pipeline test, free, labeled EXAMPLE DATA
    ./run.sh jonesfirm --limit 2            # live smoke test with whatever keys are set
    ./run.sh canycom                        # full live run
    ./run_all.sh                            # monthly batch over every configs/*.yaml (skips _template)
    ./run.sh canycom --resume output/canycom/<run dir>   # finish a run that hit a quota

Clients: `configs/windows101.yaml` (Blake sample), `configs/jonesfirm.yaml` (Dax Jones), `configs/canycom.yaml` (Canycom USA).
New client: copy `configs/_template.yaml` to `configs/<slug>.yaml`. Only verified claims go in `facts`. List anything unconfirmed under `placeholders_unconfirmed`, and the CLI will print a warning on every run until it's cleared.
Output: `output/<slug>/<Brand>_<YYYYMMDD_HHMM>/` (CSV log, dashboard CSV, xlsx, HTML, PDF). Older Windows 101 runs stay in `output/` top level.
Avorio stays in Profound (Growth plan = one workspace). To mirror it here as well, add `configs/avorio.yaml` with its 35 prompts.

## API keys (export in the shell, or add to ~/.profile on the box)
- GEMINI_API_KEY: aistudio.google.com/apikey. Turn on billing (Cloud project, then link a billing account) for Search grounding beyond the free tier and to lift the 20-requests/day cap.
- OPENAI_API_KEY: platform.openai.com/api-keys (prepaid credits; minimum $5).
- PERPLEXITY_API_KEY: perplexity.ai/settings/api (prepaid credits).
- ANTHROPIC_API_KEY: console.anthropic.com, Settings, API keys (prepaid credits). Set `CLAUDE_MODEL` to a Haiku model to cut cost.
Set a monthly spend cap in each console.

# AI Visibility Tracker (in-house Profound replacement)

This tool rebuilds Michael Blake's "AI Reputation & Share of Model Tracker" workflow. It runs a client's prompt set through four AI engines that search the web, scores every answer, and writes the Evaluation Log, the Executive Dashboard, an .xlsx workbook, and a branded HTML/PDF report.

## Setup
    cd /workspace/ai-visibility
    python3 -m venv .venv && .venv/bin/pip install pyyaml openpyxl requests
    export OPENAI_API_KEY=...  GEMINI_API_KEY=...  PERPLEXITY_API_KEY=...  ANTHROPIC_API_KEY=...

If an engine's key is missing, that engine is skipped with a warning. A PDF needs google-chrome or chromium installed; without it you still get the HTML report.

## Run
    ./run.sh configs/windows101.yaml                 # real run, using every engine that has a key
    ./run.sh configs/windows101.yaml --engines gemini,perplexity
    ./run.sh configs/windows101.yaml --limit 3       # quick smoke test
    ./run.sh configs/windows101.yaml --no-judge      # rule-based scoring only
    ./run.sh configs/windows101.yaml --mock          # fake engines; output is labeled EXAMPLE DATA

Each run writes to `output/<Brand>_<YYYYMMDD_HHMM>[_EXAMPLE]/`:
`*_evaluation_log.csv`, `*_executive_dashboard.csv`, `*_tracker.xlsx` (Executive Dashboard + Evaluation Log tabs), `*_report.html`, `*_report.pdf`.

## Client config (YAML)
To add a client, copy `configs/windows101.yaml` and fill in:
- `brand`, `brand_aliases`, `domain`
- `products`, `competitors`
- `facts`: true claims used to check whether engines cite the brand accurately
- `clusters`: 5 named groups of prompts (Michael's structure: Category Discovery, Product/Specs, Head-to-Head, Educational, Reputation). He recommends 30-50 prompts per client.
- Optional: `agency_name`, `brand_color`, `logo_url`, `models`

## Engines (default models; override per config with `models:` or env vars such as `GEMINI_MODEL`)
| Engine | API | Default model |
|---|---|---|
| ChatGPT / SearchGPT | OpenAI Responses API with the `web_search` tool | gpt-4.1-mini |
| Google Gemini | generateContent with the `google_search` grounding tool | gemini-3.5-flash |
| Perplexity Sonar | chat/completions | sonar |
| Anthropic Claude | Messages API with `web_search_20250305` (max 3 searches) | claude-sonnet-4-5 |

## Scoring
Each answer gets the same fields as Michael's log:
- brand mentioned, product mentioned
- prominence rank and position weight: #1 = 1.0, Top 3 = 0.7, incidental = 0.3, not mentioned = 0
- sentiment and a 0-100 score
- features cited and whether they are accurate
- cited domains
- gap notes

Scoring uses an LLM judge when a judge key is set. It tries OpenAI first, then Anthropic, then Gemini; set `JUDGE_MODEL` to override the model. Without a judge key it falls back to rules: brand order versus competitors, sentiment keyword counts, and matches against the `facts` list.

Dashboard formulas (they reproduce Michael's numbers):
- Share of Model % = average position weight
- Net sentiment score = average score, counting unmentioned prompts as 0
- Citation fidelity = Accurate ÷ judged answers

## Estimated cost per client run (25 prompts x 4 engines = 100 calls, 2026 list prices, rough)
These figures are estimates and have not been checked against a real run.
- Gemini Flash with grounding: ~$0.90, or $0 within the free grounding quota
- Perplexity Sonar: ~$0.20-0.30
- OpenAI mini with web search: ~$0.40-0.80
- Claude Sonnet with web search: ~$1.50-2.50 (search results inflate input tokens; use Haiku to cut this)
- LLM judge (100 mini calls): ~$0.10-0.20

Total is about $3-5 per 25-prompt run, or roughly $6-10 for 50 prompts. Profound Growth costs $399/month per seat.

## Notes
- Answers vary between runs, so run the battery monthly and compare trends rather than single numbers.
- Gemini grounding returns redirect URLs. The tracker records the source title (usually the domain) instead.
- The real API adapters had not been tested against live keys when this was written. Do a `--limit 2` run once keys are added.

## Platform quick reference (Oct 30, 2026 update)
- **Add a client:** `./new_client.sh <slug> "Brand" domain.com` → edit competitors/facts/prompts → `./run.sh <slug> --estimate` (no spend) → `./run.sh <slug> --limit 2` (smoke run, tagged `_SMOKE`, not published) → full run.
- **Monthly batch:** `./run_all.sh` then `./build_dashboard.sh` (writes gitignored `private_site/`; nothing to commit).
- **Keys:** `.env` or one file per key in `/home/box/.secrets/` (`AIVIS_SECRETS_DIR`). `run.sh` loads them; nothing is printed or committed.
- **Per-run outputs:** evaluation log CSV, executive dashboard CSV, **competitive share-of-voice CSV**, tracker.xlsx, HTML/PDF report, `cost.json` (Perplexity cost is billed-exact; others estimated).
- **Private dashboard:** `private_site/index.html` (gitignored; all clients) → per-client history with a Share-of-Model trend table. Examples and smoke runs are excluded unless `--include-examples`.
- **Perplexity:** uses the Agent API (`/v1/agent`, effort `fast`); Sonar chat/completions was retired Sep 27, 2026.
- **Cost (rough, 25 prompts):** Perplexity ≈ $0.07 measured (~$0.003/prompt), OpenAI gpt-4.1-mini + web search ≈ $0.75, Claude Sonnet + web search ≈ $0.75, Gemini grounded ≈ $1.00; ~$2.75/client/month all 4 engines + judge ~$0.20.


## Public site + authenticated app (current setup)
- **Repo (public):** https://github.com/JamesLFischer/sdm-aeo-reporting — code, configs template, and a public shell site only.
- **Public site:** https://jameslfischer.github.io/sdm-aeo-reporting/ (GitHub Pages from `main` /docs). Visitors see only the marketing/sign-in shell.
- **Never in git:** `.env`, keys, `output/` (run data), `inbox/` (questions), `private_site/` (built client dashboards), `AVORIO_PROFOUND_HISTORY.md`. History was rebuilt before the first push, so none of these were ever published.

### How sign-in and chat work (live)
- The public site talks to the box through an **end-to-end encrypted relay on ntfy.sh** (plain HTTPS, so the box needs no inbound port or tunnel — the box's network blocks Cloudflare/ssh/localtunnel tunnels).
- Sign-in: the browser derives an AES-256-GCM key from the team password (PBKDF2-SHA256, 200k rounds, salt = channel name) and sends an encrypted request. The box worker (`./relay.sh`, `aivis/relay.py`) holds the same password in `/home/box/.secrets/`, decrypts it, answers, and encrypts the reply. Wrong password → the box can't decrypt → no reply → "Sign-in failed".
- ntfy.sh only sees ciphertext. The channel name in `docs/config.js` is public by design; it doesn't let anyone read or forge messages. Old (>120s) and replayed requests are dropped. Messages expire from ntfy within ~12h.
- Rotate the password: replace `/home/box/.secrets/AIVIS_DASH_PASSWORD`, restart `./relay.sh`. Everyone signs in again.
- `./serve.sh` (`aivis/server.py`) remains as a direct HTTPS API alternative (bearer token, CORS limited) if a tunnel or host becomes available — set `AIVIS_API_BASE` (direct mode isn't wired into the new app yet).
- **Keep `./relay.sh` running on the box.** If it stops, sign-in shows "the SDM box is offline".

### Profound Bot side
`./asks.sh list | context <slug> | answer <id> "text"` — answers show up in the site chat within 20s.


See **COMPLETION_CHECKLIST.md** for what's done and what only James can do.
