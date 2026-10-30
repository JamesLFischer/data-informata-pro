import argparse, sys, os, yaml, datetime, concurrent.futures as cf
from . import engines as E, scoring, report

def main(argv=None):
    ap = argparse.ArgumentParser(description="AI search visibility / share-of-model tracker")
    ap.add_argument("config", nargs="?", help="client slug (configs/<slug>.yaml) or path to a YAML config"); ap.add_argument("-o", "--out", default="output")
    ap.add_argument("--mock", action="store_true", help="use fake engines (output is labeled EXAMPLE DATA)")
    ap.add_argument("--engines", help="comma list subset: gemini,perplexity,claude,openai")
    ap.add_argument("--no-judge", action="store_true", help="rule-based scoring only")
    ap.add_argument("--limit", type=int, help="only run first N prompts (smoke test)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-grounding", action="store_true", help="Gemini without Google Search grounding (labeled in report)")
    ap.add_argument("--resume", help="previous output dir: reuse its successful rows, only run the rest")
    ap.add_argument("--model", help="override engine model (e.g. gemini-3-flash-preview)")
    ap.add_argument("--rescore", action="store_true", help="with --resume, re-judge reused rows that fell back to rules")
    ap.add_argument("--list", action="store_true", help="list client configs and exit")
    ap.add_argument("--estimate", action="store_true", help="print expected API calls and rough cost, then exit (no spend)")
    ap.add_argument("--pace", type=float, help="seconds to wait before each API call (free-tier pacing)")
    a = ap.parse_args(argv)
    if a.no_grounding: os.environ["GEMINI_GROUNDING"] = "0"; E.GeminiEngine.grounding = False
    if a.pace is not None: E.PACE = a.pace
    cdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")
    if a.list or not a.config:
        for f in sorted(os.listdir(cdir)):
            if f.endswith(".yaml") and not f.startswith("_"):
                c = yaml.safe_load(open(os.path.join(cdir, f)))
                n = sum(len(x["prompts"]) for x in c["clusters"])
                print(f"  {f[:-5]:<14} {c['brand']:<28} {c.get('domain','')}  ({n} prompts)")
        return
    path = a.config if os.path.exists(a.config) else os.path.join(cdir, a.config + ".yaml")
    if not os.path.exists(path): sys.exit(f"No config '{a.config}'. Run with --list.")
    cfg = yaml.safe_load(open(path))
    slug = os.path.splitext(os.path.basename(path))[0]
    if cfg.get("placeholders_unconfirmed"): print("NOTE: this config has facts marked PLACEHOLDER - confirm with James before client delivery", file=sys.stderr)
    prompts = [(p.get("id") or f"P{i+1:02d}", c["name"], p["text"] if isinstance(p, dict) else p)
               for c in cfg["clusters"] for i, p in enumerate(c["prompts"])]
    if a.limit: prompts = prompts[:a.limit]
    if a.estimate:
        sel = a.engines.split(",") if a.engines else ["gemini", "perplexity", "claude", "openai"]
        per = {"gemini": .04, "perplexity": .01, "claude": .03, "openai": .03}  # observed/rough $ per grounded prompt
        tot = sum(per.get(k.strip(), .03) for k in sel) * len(prompts)
        print(f"{slug}: {len(prompts)} prompts x {len(sel)} engines = {len(prompts)*len(sel)} calls; ~${tot:.2f} answers + ~${.002*len(prompts)*len(sel):.2f} judge (rough)")
        return
    if a.mock:
        engs = [E.MockEngine(n, cfg, b) for n, b in [("Perplexity", .65), ("Google Gemini", .5), ("Anthropic Claude", .35), ("ChatGPT / SearchGPT", .25)]]
    else:
        keys = {"gemini": E.GeminiEngine, "perplexity": E.PerplexityEngine, "claude": E.ClaudeEngine, "openai": E.OpenAIEngine}
        sel = [keys[k.strip()] for k in a.engines.split(",")] if a.engines else E.REAL
        engs = []
        for cls in sel:
            eng = cls(a.model or cfg.get("models", {}).get(cls.env))
            if eng.available: engs.append(eng)
            else: print(f"WARNING: {cls.env} not set - skipping {cls.name}", file=sys.stderr)
        if not engs: sys.exit("No engine keys found. Set at least one API key, or use --mock for a pipeline test.")
    use_judge = not a.no_judge and not a.mock
    if use_judge and not any(os.environ.get(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")):
        print("NOTE: no judge key - using rule-based scoring", file=sys.stderr)
    prior = {}
    if a.resume:
        import csv, glob
        f = glob.glob(os.path.join(a.resume, "*_evaluation_log.csv"))[0]
        rows = list(csv.reader(open(f)))
        if rows and rows[0][0].startswith("EXAMPLE"): sys.exit("Refusing to resume from EXAMPLE data")
        hdr = rows[0]
        for row in rows[1:]:
            d = dict(zip(hdr, row))
            if d["Scored By"] == "ERROR" or d["Raw Answer"].startswith("[ERROR]"): continue
            prior[(d["AI Engine Evaluated"], d["Prompt ID"])] = d
        print(f"resume: reusing {len(prior)} successful rows from {f}", file=sys.stderr)
    jobs = [(eng, *p) for eng in engs for p in prompts]
    stop = {"msg": None}
    def run(job):
        eng, pid, cl, text = job
        if (eng.name, pid) in prior:
            d = prior[(eng.name, pid)]
            ans = {"text": d["Raw Answer"], "citations": [u for u in d["Cited Sources / Domains"].split(", ") if u]}
            if a.rescore and d["Scored By"].startswith("rules") and use_judge and not stop["msg"]:
                sc = scoring.score(cfg, text, ans, use_llm=True)
            else:
                yn = lambda v: v == "Yes"; cols = list(d)
                sc = {"brand_mentioned": yn(d[cols[5]]), "product_mentioned": yn(d[cols[6]]), "rank": d["Prominence Rank"],
                      "weight": float(d["Position Weight"]), "sentiment": d["Sentiment"], "score": float(d["ARS Sentiment Score"]),
                      "features": d["Core Product Drivers Cited"], "accuracy": d["Technical Accuracy / Fidelity"],
                      "domains": d["Cited Sources / Domains"], "gaps": d["Strategic Notes / Gaps"], "scored_by": d["Scored By"]}
            return {"pid": pid, "cluster": cl, "prompt": text, "engine": eng.name, "model": d["Model"], "text": d["Raw Answer"], "s": sc}
        if stop["msg"]:
            return {"pid": pid, "cluster": cl, "prompt": text, "engine": eng.name, "model": eng.model, "text": f"[ERROR] skipped: {stop['msg']}", "error": True,
                    "s": {"brand_mentioned": False, "product_mentioned": False, "rank": "ERROR", "weight": 0, "sentiment": "N/A", "score": 0,
                          "features": "", "accuracy": "N/A", "domains": "", "gaps": "Not run - daily quota exhausted; rerun with --resume", "scored_by": "ERROR"}}
        print(f"  running {eng.name} {pid}", file=sys.stderr, flush=True)
        try: ans = eng.ask(text)
        except E.DailyQuotaExhausted as ex:
            stop["msg"] = str(ex); print(f"STOPPING: {ex}. Rerun later with --resume <this output dir>.", file=sys.stderr, flush=True)
            return run(job)
        except Exception as ex:
            return {"pid": pid, "cluster": cl, "prompt": text, "engine": eng.name, "model": eng.model, "text": f"[ERROR] {ex}", "error": True,
                    "s": {"brand_mentioned": False, "product_mentioned": False, "rank": "ERROR", "weight": 0, "sentiment": "N/A", "score": 0,
                          "features": "", "accuracy": "N/A", "domains": "", "gaps": "Engine call failed - excluded from dashboard", "scored_by": "ERROR"}}
        return {"pid": pid, "cluster": cl, "prompt": text, "engine": eng.name, "model": getattr(eng, "model_used", None) or eng.model,
                "text": ans["text"], "cost": E.est_cost(eng.model, ans.get("usage")), "s": scoring.score(cfg, text, ans, use_llm=use_judge)}
    with cf.ThreadPoolExecutor(a.workers) as ex: results = list(ex.map(run, jobs))
    outdir = os.path.join(a.out, slug, f"{cfg['brand'].replace(' ','_')}_{datetime.datetime.now():%Y%m%d_%H%M}" + ("_EXAMPLE" if a.mock else "") + ("_SMOKE" if a.limit and not a.mock else ""))
    if stop["msg"]: print(f"RUN INCOMPLETE: {stop['msg']}. Finish later with: --resume <output dir>", file=sys.stderr)
    errs = sum(1 for r in results if r.get("error"))
    if errs: print(f"WARNING: {errs} of {len(results)} engine calls failed; excluded from dashboard (see log)", file=sys.stderr)
    paths = report.write_all(cfg, results, outdir, example=a.mock)
    for d in report.dashboard(results): print("  ", " | ".join(map(str, d)))
    for v in paths.values(): print("wrote", v)

if __name__ == "__main__": main()
