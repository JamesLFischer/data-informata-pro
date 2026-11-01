# SDM AEO Reporting: UI / Graphics Design Brief
Oct 31, 2026. Owner: James Fischer. Scope: public Projects dashboard (auth-gated) plus the client-facing Visual and Written reports.

## 1. Lessons from the earlier ChatGPT / Profound visual reports
From James's ChatGPT history (`/workspace/chatgpt/profound_chats.txt`) and the Avorio notes (`AVORIO_PROFOUND_HISTORY.md`, kept local and out of git):
- **Ugly, generic output.** On the dashboard PDF, James said "kinda looks like shit" (L2459).
- **Too thin, with no prompts:**
  - "I just wish it was way more detailed, and showed the actual prompts and all that within the reporting" (L4621).
  - The assistant itself admitted the new visualization was "only slightly more detailed" (L4734).
- **No competitor context.** "this section doesnt even show avarios metrics within this in comparison to their competitors, it needs to be way more detailed" (L4676).
- **No detail in the automated reports.** "why can we not get the auto reports to just be more detailed like this?" (L5270), and the request for visual reports "more detailed as i requested prior… in addition to the detailed worded reports" (L6203).
- **Not positive enough.** "it just doesnt look to positive, nor does it feel like its giving enough positive information" (L8450).
- **Backend showing.** The rule became: clients must never see "what is happening in the background", so no tool or agent names appear.
- **Agent-made images were weak.** "we also do not want the agents to produce analytical imgs anymore" (L6739). Visuals must be rendered from data, not generated.

**Design response:**
- Every chart is drawn deterministically from real run data.
- Every prompt is visible.
- The client is always shown next to its competitors.
- Strengths lead, and gaps are framed as opportunities.
- No internal tooling appears anywhere.

## 2. Visual language
- **Tone:** consultancy deliverable, not a toy dashboard. Restrained navy chrome (`#0b2240 → #1f5a96`), white cards with a 1px border, 14px radius and soft two-layer shadows.
- **Client brand color** is pulled from each `configs/<slug>.yaml` `brand_color`. It appears in the card strip, the monogram, the highlighted bar for the client and the report rule. Competitors are shown in neutral slate (`#b8c4d4`), so the client always pops.
- **Semantic scale:** used consistently for topics, KPIs, rings and the heatmap.
  - Green `#1a7f37` = strong (≥50%).
  - Amber `#b7791f` = building (25–49%).
  - Orange `#c2410c` = opportunity (<25%).
  - Red is never used, which keeps the framing positive.
- **Engine colors:**
  - Perplexity teal `#20808d`
  - ChatGPT green `#10a37f`
  - Gemini / Google blue `#4285f4`
  - Claude clay `#d97757`
- **Typography:**
  - UI uses Inter / system sans, with tabular numerals for figures.
  - The Written report uses Georgia serif headings for an editorial, print-quality feel.
  - Small caps-style uppercase labels mark KPI captions.
- **Density:** the Overview is airy (KPIs plus context). The Visual report is dense but gridded, in two columns that collapse to one below 860px. The prompt matrix is deliberately data-dense, because that is the detail James asked for.
- **Print/PDF:** the Written report hides navigation, avoids breaks inside cards and headings, and prints with a brand-colored title rule.

## 3. Information architecture
- **Projects home:** one card per client showing:
  - an SoM ring, SoM per engine and a trend sparkline;
  - chips for prompt count, runs, last updated and "Setup pending" (competitors unconfirmed);
  - plus a "+ New project" card.
- **Project page:** a monogram header with segmented tabs.
  1. **Overview:** KPI tiles (SoM per engine, unbranded discovery, branded sentiment, own-site citations), filters, the metrics table, MoM and history.
  2. **Visual report:** see section 4.
  3. **Written report:** see section 5.
  4. **Ask Profound Bot:** project-scoped Q&A over the encrypted relay. Instant answers come from data, and judgment questions are queued.
- Routes are `#/p/<slug>/<tab>`. Stale data is cleared on project switch, with skeleton loading.

## 4. Charts that beat Profound's single-score widgets
| Chart | Why it beats a single-score widget | Status |
|---|---|---|
| **Headline callouts** (SoM, #1 recommendations, own-site citations, open opportunities) | A story in four numbers, positive-first | Shipped |
| **Engine comparison panel**: 5 metrics × each engine, with ChatGPT / Google AIO columns shown as "awaiting activation" | Engines are never blended, so the parity gap is visible | Shipped |
| **SoM over time, annotated** (baseline and prompt-set changes as labelled markers; area fill per engine) | Explains *why* a line moved | Shipped |
| **Discovery vs. recognition rings** (unbranded vs branded, plus sentiment) | Separates visibility from reputation, matching the Avorio 35/7 model | Shipped |
| **Topic × engine heatmap** | Shows where each engine includes the brand at a glance | Shipped |
| **Competitive SOV ranked bars** (client highlighted) | The competitor comparison James asked for | Shipped |
| **"Who appears when the brand doesn't"** | Turns gaps into named competitive targets | Shipped |
| **Citation source mix** (100% stacked: client site / reviews & directories / media & industry / competitor sites) plus top domains | Shows the information supply chain behind AI answers | Shipped |
| **Opportunity matrix** (buying intent × competitor pressure scatter, priority quadrant) plus a priority table with full prompt text | Prioritized action list, not just a score | Shipped |
| **Win callouts with verbatim answer excerpts** | Proof clients can read | Shipped |
| **Prompt-level matrix**: every locked prompt × engine status (#1 / Top 3 / Missing), competitors named, own-site cited; filters All / Wins / Opportunities / Branded | Directly fixes "show the actual prompts" | Shipped |
| Citation network graph (domain ↔ prompt bipartite) | Nice to have; the source mix covers 80% of it | Next |
| MoM delta waterfall per topic | Needs 2+ months of data | Next (Dec) |
| Engine pair overlay (ChatGPT vs AIO lines) | Needs OpenAI and Gemini funding | Ready once enabled |

## 5. What the visuals can't show, so the Written report carries it
Visuals show *what*. The Written report explains *so what* and *now what*. Its structure (generated from the same data, InformataPro-style wording, positive framing, no tool names):
1. Executive summary (scope, SoM, #1-recommendation strength, baseline framing)
2. Where the brand already wins (strong topics, branded recognition and sentiment)
3. The discovery opportunity (unbranded rate, weakest topics, which competitors fill the gap)
4. Competitive landscape (client SOV vs peers; provisional-set caveat)
5. Citations and sources (own-site citations, source mix, which publications to target)
6. What changed (MoM, with prompt-set changes explained)
7. Recommended actions (the top 3 missing high-intent questions named verbatim, source outreach, reinforcing strengths, re-measuring)
8. Methodology (engines reported separately, never blended)

## 6. Guardrails
- Auth gate unchanged. No client data in the public HTML.
- No external chart CDNs: all inline SVG/CSS.
- Never show internal tooling, agents, costs or backend detail in client-facing text. The cost card is staff-only on the dashboard and is not in the Written report.
- Perplexity-only runs are labelled until the ChatGPT + Google AIO pair is funded.
