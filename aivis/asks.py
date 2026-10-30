"""Ask bridge: dashboard questions -> inbox/*.json -> grounded answers from run artifacts (+ Profound Bot escalation).
CLI:  python3 -m aivis.asks list [--all] | show <id> | answer <id> "text" | auto <id> | context <slug>"""
import os, sys, json, csv, glob, uuid, datetime, re, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "inbox")

def _csv(path):
    rows = list(csv.reader(open(path)))
    return rows[1:] if rows and rows[0] and rows[0][0].startswith("EXAMPLE") else rows

def runs(slug, include_tests=False):
    return sorted(d for d in glob.glob(os.path.join(ROOT, "output", slug, "*")) if os.path.isdir(d)
                  and (include_tests or not d.endswith(("_EXAMPLE", "_SMOKE"))))

def clients():
    return [os.path.basename(f)[:-5] for f in sorted(glob.glob(os.path.join(ROOT, "configs", "*.yaml"))) if not os.path.basename(f).startswith("_")]

def context(slug, date_from=None, date_to=None, engines=None):
    """Facts pulled only from real artifacts. Every value carries its source file.
    Filters: date_from/date_to (YYYY-MM-DD, by run timestamp) and engines (list or comma string: perplexity,gemini,claude,openai)."""
    from . import history as H
    cfgf = os.path.join(ROOT, "configs", slug + ".yaml")
    if not os.path.exists(cfgf): return {"error": f"unknown client '{slug}'", "clients": clients()}
    try: H.parse_date(date_from); H.parse_date(date_to)
    except ValueError: return {"error": "dates must be YYYY-MM-DD", "clients": clients()}
    cfg = yaml.safe_load(open(cfgf)); all_rs = runs(slug); rs = H.real_runs(slug, date_from, date_to)
    sel = H.parse_engines(engines)
    avail = list(dict.fromkeys(H.canon(d["AI Engine"]) for r in all_rs for d in H.dashboard_rows(r)))
    ctx = {"client": slug, "brand": cfg["brand"], "domain": cfg.get("domain"), "competitors": cfg.get("competitors", []),
           "unconfirmed": cfg.get("placeholders_unconfirmed", []), "run_count": len(rs), "total_runs": len(all_rs), "runs": [], "latest": None,
           "engines_available": avail, "filters": {"date_from": date_from or "", "date_to": date_to or "", "engines": sorted(sel) if sel else []},
           "first_run": os.path.basename(all_rs[0]) if all_rs else None}
    for r in rs:
        m = H.metrics(r, engines)
        if m: ctx["runs"].append({"run": os.path.basename(r), "date": H.run_time(r).strftime("%Y-%m-%d"), "som_by_engine": {k: f"{v['som']:.1f}%" for k, v in m.items()}})
    rs = [r for r in rs if H.metrics(r, engines)]; ctx["run_count"] = len(rs)
    if rs:
        r = rs[-1]; L = {"run": os.path.basename(r), "source_dir": os.path.relpath(r, ROOT)}
        L["dashboard"] = H.dashboard_rows(r, engines)
        L["share_of_voice"] = H.share_of_voice(r, engines)
        c = os.path.join(r, "cost.json")
        if os.path.exists(c): L["cost"] = json.load(open(c))
        ctx["latest"] = L
        ctx["mom"] = H.mom(slug, engines, date_from, date_to)
    return ctx

def auto_answer(ask):
    """Deterministic answer from artifacts. Anything it can't ground is marked for Profound Bot."""
    f = ask.get("filters") if isinstance(ask.get("filters"), dict) else {}
    ctx = context(ask.get("client", ""), f.get("date_from") or None, f.get("date_to") or None, f.get("engines") or None)
    if "error" in ctx: return ctx["error"] + ". Known clients: " + ", ".join(ctx["clients"]), False
    q = ask["question"].lower(); out = [f"{ctx['brand']} ({ctx['domain']}) — {ctx['run_count']} real run(s)."]
    L = ctx["latest"]
    if any(ctx["filters"].values()):
        fl = ctx["filters"]; out.append("Filters: " + ", ".join(x for x in [f"from {fl['date_from']}" if fl["date_from"] else "", f"to {fl['date_to']}" if fl["date_to"] else "", "engines " + "/".join(fl["engines"]) if fl["engines"] else ""] if x) + ".")
    if not L:
        if any(ctx["filters"].values()): return " ".join(out) + " No real runs match these filters - widen the date range or engines.", False
        return out[0] + " No real runs yet, so there are no metrics to answer from. Run ./run.sh " + ctx["client"], True
    out.append(f"Latest run: {L['run']} (source: {L['source_dir']}).")
    hit = False
    if True:  # always include headline metrics
        for d in L.get("dashboard", []):
            out.append(f"- {d.get('AI Engine')}: SoM {d.get('Overall SoM %')}, mentions {d.get('Total Mentions')}/{d.get('Prompts Evaluated')}, #1 recs {d.get('#1 Recommendations')}, sentiment {d.get('Net ARS Score (0-100)')}")
        hit = True
    if re.search(r"compet|vs|versus|sov|share of voice|rival", q):
        sov = L.get("share_of_voice")
        out.append("Share of voice (all engines): " + ", ".join(f"{x['Brand']} {x['All engines']}" for x in sov[:8]) if sov else "No share-of-voice file in this run (older run format).")
    if re.search(r"trend|change|month|over time|history|improv|drop|delta|mom", q):
        m = ctx.get("mom") or {}
        if m.get("baseline"):
            from .history import fmt_delta
            out.append(f"vs {m['baseline']} ({m['basis']}): " + "; ".join(f"{r['engine']} SoM {r['som']['now']}% ({fmt_delta(r['som']['delta'])} pp)" + (f" [{r['note']}]" if r["note"] else "") for r in m["rows"]))
        out.append("History: " + "; ".join(f"{r['run']}: " + ", ".join(f"{k} {v}" for k, v in r["som_by_engine"].items()) for r in ctx["runs"]))
    if re.search(r"cost|spend|\$|price", q):
        out.append(f"Cost of latest run: ${L['cost']['total_usd']} ({L['cost']['note']})" if "cost" in L else "No cost.json for this run (predates cost tracking).")
    if ctx["unconfirmed"]: out.append("Caveat: unconfirmed config items: " + ", ".join(ctx["unconfirmed"]))
    needs_bot = bool(re.search(r"why|recommend|should|what to do|fix|improve|explain|profound|avorio", q))
    if needs_bot: out.append("This needs interpretation — flagged for Profound Bot.")
    return "\n".join(out), needs_bot

def _norm_filters(ask):
    """Structured filters {date_from, date_to, engines}. Also accepts legacy free text date_range 'YYYY-MM-DD..YYYY-MM-DD'."""
    f = ask.get("filters") if isinstance(ask.get("filters"), dict) else {}
    out = {"date_from": str(f.get("date_from") or "")[:10], "date_to": str(f.get("date_to") or "")[:10], "engines": f.get("engines") or []}
    if isinstance(out["engines"], str): out["engines"] = [x.strip() for x in out["engines"].split(",") if x.strip()]
    out["engines"] = [str(x)[:30] for x in out["engines"]][:6]
    d = re.findall(r"\d{4}-\d{2}-\d{2}", str(ask.get("date_range") or ""))
    if d and not out["date_from"]: out["date_from"] = d[0]
    if len(d) > 1 and not out["date_to"]: out["date_to"] = d[1]
    for k in ("date_from", "date_to"):
        if out[k] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", out[k]): out[k] = ""
    return out

def save(ask):
    os.makedirs(INBOX, exist_ok=True)
    ask = {"id": datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4], "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "client": ask.get("client", ""), "question": str(ask.get("question", ""))[:2000], "date_range": ask.get("date_range", ""),
           "filters": _norm_filters(ask), "status": "open", "answers": []}
    text, needs = auto_answer(ask)
    ask["answers"].append({"by": "auto (artifacts)", "at": ask["created"], "text": text})
    ask["status"] = "needs_bot" if needs else "answered"
    json.dump(ask, open(os.path.join(INBOX, ask["id"] + ".json"), "w"), indent=1); return ask

def load_all():
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(INBOX, "*.json")))]

def main(a=sys.argv[1:]):
    cmd = a[0] if a else "list"
    if cmd == "list":
        for x in load_all():
            if "--all" in a or x["status"] != "answered": print(f"{x['id']}  [{x['status']}]  {x['client']}: {x['question'][:90]}")
    elif cmd == "pending":  # for routines: prints count, exit 0 if none, 3 if questions wait for Profound Bot
        n = sum(x["status"] == "needs_bot" for x in load_all()); print(n); sys.exit(3 if n else 0)
    elif cmd == "show": print(json.dumps(json.load(open(os.path.join(INBOX, a[1] + ".json"))), indent=1))
    elif cmd == "context": print(json.dumps(context(a[1]), indent=1))
    elif cmd == "answer":
        p = os.path.join(INBOX, a[1] + ".json"); x = json.load(open(p))
        x["answers"].append({"by": "Profound Bot", "at": datetime.datetime.now().isoformat(timespec="seconds"), "text": a[2]}); x["status"] = "answered"
        json.dump(x, open(p, "w"), indent=1); print("answered", a[1])
    elif cmd == "ask": print(json.dumps(save({"client": a[1], "question": a[2]}), indent=1))
    else: print(__doc__)
if __name__ == "__main__": main()
