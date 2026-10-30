"""Per-client project payload: overview, visual data and a written monthly narrative, built only from real run artifacts."""
import os, csv, glob, json, collections, yaml
from . import history as H, asks as A
ROOT = A.ROOT

def _cfg(slug): return yaml.safe_load(open(os.path.join(ROOT, "configs", slug + ".yaml")))

def _kinds(cfg):
    al = [cfg["brand"].lower()] + [a.lower() for a in cfg.get("brand_aliases", [])]
    out = {}
    for c in cfg.get("clusters", []):
        for p in c["prompts"]:
            k = c.get("kind") or ("branded" if any(a in p["text"].lower() for a in al) else "unbranded")
            out[p["id"]] = (k, c["name"])
    return out

def _rows(run):
    f = glob.glob(os.path.join(run, "*_evaluation_log.csv"))
    return list(csv.DictReader(open(f[0], encoding="utf-8"))) if f else []

def summary(slug):
    cfg = _cfg(slug); rs = H.real_runs(slug)
    p = {"client": slug, "brand": cfg["brand"], "domain": cfg.get("domain"), "color": cfg.get("brand_color", "#334"),
         "prompts": sum(len(c["prompts"]) for c in cfg.get("clusters", [])), "locked": cfg.get("locked"), "runs": len(rs)}
    if rs:
        m = H.metrics(rs[-1]); p["latest"] = os.path.basename(rs[-1]); p["date"] = H.run_time(rs[-1]).strftime("%b %d, %Y")
        p["som"] = {k: round(v["som"], 1) for k, v in m.items()}
    return p

def build(slug, engines=None):
    if not os.path.exists(os.path.join(ROOT, "configs", f"{slug}.yaml")): return {"error": "unknown project"}
    cfg = _cfg(slug); kinds = _kinds(cfg); brand = cfg["brand"]; dom = (cfg.get("domain") or "").lower()
    ctx = A.context(slug, engines=engines); out = {"summary": summary(slug), "context": ctx,
        "competitors": cfg.get("competitors", []), "competitors_confirmed": "competitors list" not in cfg.get("placeholders_unconfirmed", []),
        "parity_engines": cfg.get("parity_engines", []), "unconfirmed": cfg.get("placeholders_unconfirmed", [])}
    rs = [r for r in H.real_runs(slug) if H.metrics(r, engines)]
    if not rs: out["written"] = [f"No measured runs yet for {brand}. The first baseline will appear here once a run completes."]; return out
    rows = [r for r in _rows(rs[-1]) if not engines or H.canon(r["AI Engine Evaluated"]) in H.parse_engines(engines)]
    mcol = f"{brand} Mentioned (Yes/No)"
    clus = collections.defaultdict(lambda: collections.defaultdict(list)); kind = collections.defaultdict(list)
    sent = []; doms = collections.Counter(); own = 0; gaps = []; wins = []
    for r in rows:
        e = H.canon(r["AI Engine Evaluated"]); hit = r.get(mcol, "No") == "Yes"
        k, cn = kinds.get(r["Prompt ID"], ("unbranded", r["Cluster / Category"]))
        clus[cn][e].append(hit); kind[k].append(hit)
        if k == "branded" and hit:
            try: sent.append(float(r.get("ARS Sentiment Score") or 0))
            except ValueError: pass
        ds = [d.strip().lower() for d in (r.get("Cited Sources / Domains") or "").split(",") if d.strip()]
        doms.update(set(ds)); own += any(dom and dom in d for d in ds)
        (wins if hit and k == "unbranded" else gaps if k == "unbranded" else []).append({"id": r["Prompt ID"], "prompt": r["Standardized Prompt"], "engine": e, "rank": r.get("Prominence Rank")})
    pct = lambda l: round(100 * sum(l) / len(l), 1) if l else None
    out["clusters"] = [{"cluster": c, "by_engine": {e: pct(v) for e, v in d.items()}} for c, d in clus.items()]
    out["kinds"] = {k: {"rate": pct(v), "n": len(v)} for k, v in kind.items()}
    out["sentiment"] = round(sum(sent) / len(sent), 2) if sent else None
    out["domains"] = doms.most_common(12); out["own_citations"] = {"answers": own, "of": len(rows)}
    out["gaps"] = gaps[:15]; out["wins"] = wins[:15]
    out["trend"] = [{"date": H.run_time(r).strftime("%Y-%m-%d %H:%M"), "som": {k: round(v["som"], 1) for k, v in H.metrics(r, engines).items()}} for r in rs]
    out["written"] = narrative(brand, out, ctx)
    return out

def narrative(brand, o, ctx):
    L = ctx.get("latest") or {}; s = o["summary"]; P = []
    som = s.get("som", {}); eng = ", ".join(f"{e.title()} {v}%" for e, v in som.items())
    P.append(f"Executive summary. In the latest measurement ({s.get('date')}), {brand} earned a Share of Model of {eng} across a locked battery of {s['prompts']} buyer-intent prompts. This establishes a clear, repeatable baseline we will track month over month.")
    u = o["kinds"].get("unbranded"); b = o["kinds"].get("branded")
    if u: P.append(f"Unbranded visibility. When buyers asked category questions without naming {brand}, AI answers included the brand {u['rate']}% of the time ({u['n']} answers). Every unbranded answer that omits the brand is a concrete content opportunity, listed in the Opportunities section.")
    if b: P.append(f"Branded perception. On questions that name {brand} directly, the brand was recognized in {b['rate']}% of answers" + (f", with an average sentiment score of {o['sentiment']} on a 0-100 scale (50 = neutral)." if o["sentiment"] is not None else ".") + " This shows how AI engines describe the brand to buyers who are already considering it.")
    cl = sorted([(max(v for v in c["by_engine"].values() if v is not None), c["cluster"]) for c in o["clusters"] if any(v is not None for v in c["by_engine"].values())], reverse=True)
    if cl: P.append(f"Strongest topic: {cl[0][1].split(' - ')[-1]} ({cl[0][0]}% inclusion). Biggest growth area: {cl[-1][1].split(' - ')[-1]} ({cl[-1][0]}%), where focused content can move the needle fastest.")
    sov = L.get("share_of_voice") or []
    comp = [r for r in sov if r.get("Brand") != brand and str(list(r.values())[-1]).strip("%") not in ("0.0","0","")][:3]
    if comp: P.append("Competitive landscape. The brands most often named alongside or instead of " + brand + " were " + ", ".join(f"{r.get('Brand')} ({list(r.values())[-1]})" for r in comp) + "." + ("" if o["competitors_confirmed"] else " The competitor set is provisional and will be finalized with the client."))
    oc = o["own_citations"]; top = ", ".join(d for d, _ in o["domains"][:5])
    P.append(f"Citations. AI engines cited {s.get('domain')} in {oc['answers']} of {oc['of']} answers. The most-cited sources were {top}. Earning placement on these sources is a high-leverage path to more AI recommendations.")
    mom = ctx.get("mom") or {}
    if mom.get("previous"): P.append("Month-over-month. " + "; ".join(f"{e.title()}: {v}" for e, v in (mom.get("delta_text") or {}).items()) if mom.get("delta_text") else "Month-over-month comparison is available in the trend chart.")
    else: P.append("Month-over-month. This is the baseline period; next month's report will show movement against these figures.")
    P.append("Next steps. Publish answer-ready content for the top opportunity prompts, strengthen presence on the most-cited third-party sources, and re-measure on the same locked prompts next month.")
    return P

def projects():
    return [summary(c) for c in A.clients()]
