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

def context(slug):
    """Facts pulled only from real artifacts. Every value carries its source file."""
    cfgf = os.path.join(ROOT, "configs", slug + ".yaml")
    if not os.path.exists(cfgf): return {"error": f"unknown client '{slug}'", "clients": clients()}
    cfg = yaml.safe_load(open(cfgf)); rs = runs(slug)
    ctx = {"client": slug, "brand": cfg["brand"], "domain": cfg.get("domain"), "competitors": cfg.get("competitors", []),
           "unconfirmed": cfg.get("placeholders_unconfirmed", []), "run_count": len(rs), "runs": [], "latest": None}
    for r in rs:
        d = glob.glob(os.path.join(r, "*_executive_dashboard.csv"))
        if not d: continue
        rows = _csv(d[0]); som = {x[0]: x[5] for x in rows[1:] if len(x) > 5}
        ctx["runs"].append({"run": os.path.basename(r), "som_by_engine": som})
    if rs:
        r = rs[-1]; L = {"run": os.path.basename(r), "source_dir": os.path.relpath(r, ROOT)}
        d = glob.glob(os.path.join(r, "*_executive_dashboard.csv"))
        if d: rows = _csv(d[0]); L["dashboard"] = [dict(zip(rows[0], x)) for x in rows[1:]]
        s = glob.glob(os.path.join(r, "*_share_of_voice.csv"))
        if s: rows = _csv(s[0]); L["share_of_voice"] = [dict(zip(rows[0], x)) for x in rows[1:]]
        c = os.path.join(r, "cost.json")
        if os.path.exists(c): L["cost"] = json.load(open(c))
        ctx["latest"] = L
    return ctx

def auto_answer(ask):
    """Deterministic answer from artifacts. Anything it can't ground is marked for Profound Bot."""
    ctx = context(ask.get("client", ""))
    if "error" in ctx: return ctx["error"] + ". Known clients: " + ", ".join(ctx["clients"]), False
    q = ask["question"].lower(); out = [f"{ctx['brand']} ({ctx['domain']}) — {ctx['run_count']} real run(s)."]
    L = ctx["latest"]
    if not L: return out[0] + " No real runs yet, so there are no metrics to answer from. Run ./run.sh " + ctx["client"], True
    out.append(f"Latest run: {L['run']} (source: {L['source_dir']}).")
    hit = False
    if True:  # always include headline metrics
        for d in L.get("dashboard", []):
            out.append(f"- {d.get('AI Engine')}: SoM {d.get('Overall SoM %')}, mentions {d.get('Total Mentions')}/{d.get('Prompts Evaluated')}, #1 recs {d.get('#1 Recommendations')}, sentiment {d.get('Net ARS Score (0-100)')}")
        hit = True
    if re.search(r"compet|vs|versus|sov|share of voice|rival", q):
        sov = L.get("share_of_voice")
        out.append("Share of voice (all engines): " + ", ".join(f"{x['Brand']} {x['All engines']}" for x in sov[:8]) if sov else "No share-of-voice file in this run (older run format).")
    if re.search(r"trend|change|month|over time|history|improv|drop", q):
        out.append("History: " + "; ".join(f"{r['run']}: " + ", ".join(f"{k} {v}" for k, v in r["som_by_engine"].items()) for r in ctx["runs"]))
    if re.search(r"cost|spend|\$|price", q):
        out.append(f"Cost of latest run: ${L['cost']['total_usd']} ({L['cost']['note']})" if "cost" in L else "No cost.json for this run (predates cost tracking).")
    if ctx["unconfirmed"]: out.append("Caveat: unconfirmed config items: " + ", ".join(ctx["unconfirmed"]))
    needs_bot = bool(re.search(r"why|recommend|should|what to do|fix|improve|explain|profound|avorio", q))
    if needs_bot: out.append("This needs interpretation — flagged for Profound Bot.")
    return "\n".join(out), needs_bot

def save(ask):
    os.makedirs(INBOX, exist_ok=True)
    ask = {"id": datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4], "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "client": ask.get("client", ""), "question": str(ask.get("question", ""))[:2000], "date_range": ask.get("date_range", ""),
           "filters": ask.get("filters", ""), "status": "open", "answers": []}
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
    elif cmd == "show": print(json.dumps(json.load(open(os.path.join(INBOX, a[1] + ".json"))), indent=1))
    elif cmd == "context": print(json.dumps(context(a[1]), indent=1))
    elif cmd == "answer":
        p = os.path.join(INBOX, a[1] + ".json"); x = json.load(open(p))
        x["answers"].append({"by": "Profound Bot", "at": datetime.datetime.now().isoformat(timespec="seconds"), "text": a[2]}); x["status"] = "answered"
        json.dump(x, open(p, "w"), indent=1); print("answered", a[1])
    elif cmd == "ask": print(json.dumps(save({"client": a[1], "question": a[2]}), indent=1))
    else: print(__doc__)
if __name__ == "__main__": main()
