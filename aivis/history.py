"""Run history, month-over-month deltas and date/engine filtering. Reads only real run artifacts in output/<slug>/.
CLI: python3 -m aivis.history <slug> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--engines perplexity,gemini]"""
import os, re, csv, glob, json, datetime, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_SUFFIXES = ("_EXAMPLE", "_SMOKE")
METRICS = [("som", "Share of Model", "Overall SoM %", "pp"), ("mentions", "Mention rate", None, "pp"),
           ("top1", "#1 rec rate", None, "pp"), ("sentiment", "Net sentiment", "Net ARS Score (0-100)", "pts"),
           ("fidelity", "Citation fidelity", "Citation Fidelity", "pp")]

def canon(engine):
    """Stable engine key so renamed engines (e.g. 'Perplexity Sonar' -> 'Perplexity') still compare."""
    n = (engine or "").lower()
    if "perplexity" in n: return "Perplexity"
    if "gemini" in n: return "Gemini (no grounding)" if "no grounding" in n else "Gemini"
    if "claude" in n or "anthropic" in n: return "Claude"
    if "chatgpt" in n or "openai" in n or "gpt" in n: return "ChatGPT"
    return engine

def run_time(run):
    m = re.search(r"_(\d{8})_(\d{4})(?:_|$)", os.path.basename(run.rstrip("/")))
    return datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M") if m else None

def parse_date(s, end=False):
    if not s: return None
    if isinstance(s, datetime.datetime): return s
    d = datetime.datetime.strptime(str(s)[:10], "%Y-%m-%d")
    return d + datetime.timedelta(days=1) - datetime.timedelta(seconds=1) if end else d

def parse_engines(e):
    if not e: return None
    xs = e if isinstance(e, (list, tuple)) else str(e).split(",")
    out = {canon(x.strip()) for x in xs if str(x).strip()}
    for x in xs:  # 'gemini' selects grounded and ungrounded Gemini
        if str(x).strip().lower() == "gemini": out.add("Gemini (no grounding)")
    return out or None

def real_runs(slug, date_from=None, date_to=None, include_tests=False, base=None):
    f, t = parse_date(date_from), parse_date(date_to, end=True)
    out = []
    for d in sorted(glob.glob(os.path.join(base or os.path.join(ROOT, "output", slug), "*"))):
        if not os.path.isdir(d) or (not include_tests and d.endswith(TEST_SUFFIXES)): continue
        ts = run_time(d)
        if ts is None or (f and ts < f) or (t and ts > t): continue
        out.append(d)
    return sorted(out, key=run_time)

def _csv(path):
    rows = list(csv.reader(open(path, newline="")))
    return rows[1:] if rows and rows[0] and rows[0][0].startswith("EXAMPLE") else rows

def _pct(v):
    try: return float(str(v).rstrip("%"))
    except ValueError: return None

def dashboard_rows(run, engines=None):
    f = glob.glob(os.path.join(run, "*_executive_dashboard.csv"))
    if not f: return []
    rows = _csv(f[0]); sel = parse_engines(engines)
    return [dict(zip(rows[0], r)) for r in rows[1:] if r and (not sel or canon(r[0]) in sel)]

def metrics(run, engines=None):
    """{canonical engine: {som, mentions, top1, sentiment, fidelity, n, label}} from the dashboard CSV."""
    out = {}
    for d in dashboard_rows(run, engines):
        n = int(d.get("Prompts Evaluated") or 0)
        if not n: continue
        out[canon(d["AI Engine"])] = {"label": d["AI Engine"], "n": n, "som": _pct(d.get("Overall SoM %")),
            "mentions": round(100 * int(d.get("Total Mentions") or 0) / n, 1), "top1": round(100 * int(d.get("#1 Recommendations") or 0) / n, 1),
            "sentiment": _pct(d.get("Net ARS Score (0-100)")), "fidelity": _pct(d.get("Citation Fidelity"))}
    return out

def share_of_voice(run, engines=None):
    """Brand -> % of answers mentioning it. Recomputed from the evaluation log when an engine filter is set."""
    sel = parse_engines(engines)
    if sel:
        f = glob.glob(os.path.join(run, "*_evaluation_log.csv")); s = glob.glob(os.path.join(run, "*_share_of_voice.csv"))
        if not f or not s: return []
        names = [r[0] for r in _csv(s[0])[1:]]
        rows = _csv(f[0]); h = rows[0]; ie, ia, isb = h.index("AI Engine Evaluated"), h.index("Raw Answer"), h.index("Scored By")
        ans = [r for r in rows[1:] if canon(r[ie]) in sel and r[isb] != "ERROR" and not r[ia].startswith("[ERROR]")]
        if not ans: return []
        cfg = _cfg_for(run); aliases = {cfg.get("brand"): [cfg.get("brand")] + list(cfg.get("brand_aliases", []))} if cfg else {}
        hit = lambda name, t: any(re.search(r"(?<!\w)" + re.escape(a.lower()) + r"(?!\w)", t.lower()) for a in aliases.get(name, [name]))
        out = [{"Brand": n, "Selected engines": f"{100 * sum(hit(n, r[ia]) for r in ans) / len(ans):.1f}%"} for n in names]
        return sorted(out, key=lambda x: -float(x["Selected engines"].rstrip("%")))
    s = glob.glob(os.path.join(run, "*_share_of_voice.csv"))
    if not s: return []
    rows = _csv(s[0]); return [dict(zip(rows[0], r)) for r in rows[1:]]

def _cfg_for(run):
    import yaml
    p = os.path.join(ROOT, "configs", os.path.basename(os.path.dirname(run.rstrip("/"))) + ".yaml")
    return yaml.safe_load(open(p)) if os.path.exists(p) else None

def previous_run(slug_dir, current_time, engines=None):
    """Baseline for 'month over month': latest real run in an earlier calendar month; else the latest earlier run."""
    earlier = [r for r in real_runs(None, base=slug_dir) if run_time(r) < current_time and metrics(r, engines)]
    if not earlier: return None, None
    prior_month = [r for r in earlier if (run_time(r).year, run_time(r).month) < (current_time.year, current_time.month)]
    return (prior_month[-1], "previous month") if prior_month else (earlier[-1], "previous run (same month)")

def deltas(cur, prev):
    """Rows comparing two metrics() dicts. Notes flag anything that makes the comparison apples-to-oranges."""
    rows = []
    for eng in list(cur) + [e for e in prev if e not in cur]:
        c, p = cur.get(eng), prev.get(eng); note = []
        if not p: note.append("new engine this run")
        elif not c: note.append("not run this time")
        elif c["n"] != p["n"]: note.append(f"prompt count changed {p['n']}→{c['n']}")
        row = {"engine": eng, "note": "; ".join(note)}
        for k, label, _, unit in METRICS:
            cv, pv = (c or {}).get(k), (p or {}).get(k)
            row[k] = {"now": cv, "prev": pv, "delta": round(cv - pv, 1) if cv is not None and pv is not None else None, "unit": unit}
        rows.append(row)
    return rows

def fmt_delta(d):
    if d is None: return "—"
    return ("▲ +" if d > 0 else "▼ " if d < 0 else "● ") + f"{d:.1f}"

def mom(slug, engines=None, date_from=None, date_to=None):
    rs = [r for r in real_runs(slug, date_from, date_to) if metrics(r, engines)]
    if not rs: return None
    cur = rs[-1]; prev, basis = previous_run(os.path.join(ROOT, "output", slug), run_time(cur), engines)
    if not prev: return {"run": os.path.basename(cur), "baseline": None, "basis": "first run - no baseline yet", "rows": []}
    return {"run": os.path.basename(cur), "baseline": os.path.basename(prev), "basis": basis,
            "rows": deltas(metrics(cur, engines), metrics(prev, engines))}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--from", dest="f"); ap.add_argument("--to"); ap.add_argument("--engines")
    a = ap.parse_args(); m = mom(a.slug, a.engines, a.f, a.to)
    if not m: print("no real runs in range"); return
    print(f"{a.slug}: {m['run']} vs {m['baseline']} ({m['basis']})")
    for r in m["rows"]:
        print(f"  {r['engine']:<24} " + "  ".join(f"{lab} {r[k]['now'] if r[k]['now'] is not None else '—'} ({fmt_delta(r[k]['delta'])})" for k, lab, _, _ in METRICS[:4]) + (f"  [{r['note']}]" if r["note"] else ""))
if __name__ == "__main__": main()
