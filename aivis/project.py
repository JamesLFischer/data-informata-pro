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
        p["trend"] = [round(next(iter(H.metrics(r).values()))["som"], 1) for r in rs[-8:] if H.metrics(r)]
        k = _kinds(cfg); p["unconfirmed"] = cfg.get("placeholders_unconfirmed", [])
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
    # ---- detail layer (v3 visual report) ----
    comps = cfg.get("competitors", []); hi = ("discovery", "local", "comparison", "head-to-head", "expanded", "case types", "product")
    def intent(cn):
        c = cn.lower(); return 3 if any(h in c for h in hi[:3] + ("expanded",)) else 2 if any(h in c for h in hi[3:]) else 1
    matrix = []
    for r in rows:
        e = H.canon(r["AI Engine Evaluated"]); k, cn = kinds.get(r["Prompt ID"], ("unbranded", r["Cluster / Category"]))
        raw = (r.get("Raw Answer") or "").lower(); cm = [c for c in comps if c.lower() in raw]
        ds = [d.strip().lower() for d in (r.get("Cited Sources / Domains") or "").split(",") if d.strip()]
        snip = ""
        if r.get(mcol) == "Yes":
            ra = r.get("Raw Answer") or ""; al = [brand] + cfg.get("brand_aliases", [])
            for a_ in al:
                i = ra.lower().find(a_.lower())
                if i >= 0: snip = " ".join(ra[max(0, i - 90): i + 160].split()); break
        matrix.append({"id": r["Prompt ID"], "prompt": r["Standardized Prompt"], "cluster": cn.split(" - ")[-1], "kind": k, "engine": e,
                       "hit": r.get(mcol) == "Yes", "rank": r.get("Prominence Rank"), "sentiment": r.get("Sentiment"), "intent": intent(cn),
                       "competitors": cm, "own_cited": any(dom and dom in d for d in ds), "sources": ds[:5], "snippet": snip[:260]})
    out["matrix"] = matrix
    out["engines"] = {k: v for k, v in H.metrics(rs[-1], engines).items()}
    bw = [w.lower() for w in brand.replace(",", " ").split() if len(w) >= 6]
    isown = lambda d: (dom and dom in d) or any(w in d for w in bw)
    mix = collections.Counter()
    for r in matrix:
        for d in r["sources"]:
            mix["Client site" if isown(d) else "Competitor sites" if any(c.split()[0].lower() in d for c in comps) else "Reviews & directories" if any(x in d for x in ("review", "yelp", "avvo", "justia", "lawyers", "martindale", "bbb", "google", "superlawyers", "findlaw", "nolo", "reddit", "quora")) else "Media & industry"] += 1
    out["source_mix"] = mix.most_common()
    cw = collections.Counter(c for r in matrix if r["kind"] == "unbranded" and not r["hit"] for c in r["competitors"])
    out["displacers"] = cw.most_common(6)
    out["opportunities"] = sorted([r for r in matrix if r["kind"] == "unbranded" and not r["hit"]], key=lambda r: (-r["intent"], -len(r["competitors"])))[:12]
    out["top_wins"] = [r for r in matrix if r["hit"] and r["kind"] == "unbranded"][:8] + [r for r in matrix if r["hit"] and r["kind"] == "branded" and r["sentiment"] == "Positive"][:4]
    ann = []; prev = None
    for r in rs:
        n = sum(v["n"] for v in H.metrics(r, engines).values())
        if prev is not None and n != prev: ann.append({"date": H.run_time(r).strftime("%Y-%m-%d %H:%M"), "text": f"Prompt set expanded to {n}"})
        prev = n
    if rs: ann.insert(0, {"date": H.run_time(rs[0]).strftime("%Y-%m-%d %H:%M"), "text": "Baseline"})
    out["annotations"] = ann
    out["written"] = narrative(brand, out, ctx)
    return out

def narrative(brand, o, ctx):
    """Client-ready monthly narrative as [{h, p:[...]}] sections. Positive framing, no internal tooling names."""
    s = o["summary"]; som = s.get("som", {}); E = o.get("engines", {}); u = o["kinds"].get("unbranded") or {}; b = o["kinds"].get("branded") or {}
    S = []; eng = " and ".join(f"{e} ({v}%)" for e, v in som.items()) or "the measured engines"
    top1 = next(iter(E.values()), {}).get("top1")
    S.append({"h": "Executive summary", "p": [
        f"This report measures how AI answer engines present {brand} to buyers. It covers a locked battery of {s['prompts']} buyer-intent questions: {u.get('n', 0)} category questions that do not name the brand, plus {b.get('n', 0)} branded questions that gauge reputation. Our analysis indicates a Share of Model of {eng}.",
        (f"When {brand} appears, it is usually recommended first. It was the #1 recommendation in {top1}% of all answers, which is a strong signal of authority in the answers buyers actually read." if top1 else ""),
        "This period sets the baseline. Every future report re-asks the same questions on the same engines, so month-over-month movement reflects real change in AI visibility."]})
    cl = sorted([(max([v for v in c["by_engine"].values() if v is not None] or [0]), c["cluster"].split(" - ")[-1]) for c in o["clusters"]], reverse=True)
    strong = [c for v, c in cl if v >= 50]; grow = [f"{c} ({v}%)" for v, c in cl if v < 25]
    S.append({"h": "Where the brand already wins", "p": [
        f"{brand} is strongest in {', '.join(strong[:3]) or cl[0][1]}. Those topic areas already return the brand reliably." if cl else "",
        (f"Branded questions return {brand} in {b.get('rate')}% of answers, and the average sentiment is {round(o['sentiment'])} on a 0–100 scale (50 = neutral). AI engines describe the brand accurately and favorably to buyers who are already considering it." if b else ""),
        "Representative answers are quoted in the Visual report under Wins, so the client can see exactly how engines describe the brand."]})
    S.append({"h": "The discovery opportunity", "p": [
        f"On unbranded category questions, the moment buyers first form a shortlist, {brand} appears in {u.get('rate')}% of answers. That is the single largest growth lever in this program.",
        (f"The topics with the most room to grow are {', '.join(grow[:4])}. Answer-ready content on these topics typically produces the fastest gains." if grow else ""),
        (f"In the answers where {brand} is not yet included, the brands most often named instead are {', '.join(f'{c} ({n})' for c, n in o['displacers'][:4])}. Our analysis indicates that matching their coverage on these specific questions is a direct path to displacing them." if o.get("displacers") else "")]})
    sov = [r for r in ((ctx.get("latest") or {}).get("share_of_voice") or []) if r.get("Brand") != brand and str(list(r.values())[-1]).strip("%") not in ("0.0", "0", "")][:4]
    allsov = (ctx.get("latest") or {}).get("share_of_voice") or []
    mine = [r for r in allsov if r.get("Brand") == brand]; me_sov = list(mine[0].values())[-1] if mine else "n/a"
    f_ = lambda v: float(str(v).strip("%") or 0)
    lead = bool(mine) and all(f_(me_sov) >= f_(list(r.values())[-1]) for r in sov)
    S.append({"h": "Competitive landscape", "p": [
        (f"Across all answers, {brand} holds {me_sov} of brand mentions" + (", ahead of every tracked peer: " if lead else ". The most-mentioned peers are: ") + ", ".join(f"{r.get('Brand')} {list(r.values())[-1]}" for r in sov) + ".") if sov else f"Tracked competitors were rarely named, which leaves the category open for {brand} to own.",
        "" if o["competitors_confirmed"] else "The competitor set is provisional and will be finalized with you, so share-of-voice figures may be refined."]})
    oc = o["own_citations"]; mix = dict(o.get("source_mix") or []); tot = sum(mix.values()) or 1
    S.append({"h": "Citations and sources", "p": [
        f"AI engines cited {s.get('domain')} directly in {oc['answers']} of {oc['of']} answers. The engines treat the site as a primary source of truth.",
        "Source mix: " + ", ".join(f"{k} {round(100 * v / tot)}%" for k, v in mix.items()) + ". The most-cited domains (" + ", ".join(d for d, _ in o["domains"][:5]) + ") are the publications and directories that shape AI answers in this category.",
        "Strengthening listings and coverage on those sources compounds over time, because engines re-use trusted sources across many questions."]})
    mom = ctx.get("mom") or {}; rows = mom.get("rows") or []
    if mom.get("baseline") and rows:
        r0 = rows[0]; note = r0.get("note") or ""
        P = [f"Compared with the previous measurement, Share of Model on {r0['engine']} is {r0['som']['now']}%." + (f" The prompt set was expanded during this period ({note}), which broadens coverage into new buyer questions. Going forward, the expanded set is the locked baseline." if "prompt count" in note else "")]
    else: P = ["This is the baseline period. Next month's report will chart movement against these figures."]
    S.append({"h": "What changed", "p": P})
    ops = o.get("opportunities") or []
    S.append({"h": "Recommended actions", "p": [
        "1. Publish answer-ready pages for the highest-intent missing questions" + (": " + "; ".join(f"“{x['prompt']}”" for x in ops[:3]) if ops else "") + ".",
        "2. Earn or refresh presence on the most-cited third-party sources listed above, so the brand is in the material engines draw from.",
        "3. Reinforce the strengths that already win by keeping facts, reviews and specifications consistent everywhere the brand appears.",
        "4. Re-measure on the same locked questions next month and report movement by engine and topic."]})
    S.append({"h": "Methodology", "p": [f"Each question is asked fresh on each engine. Answers are scored for brand inclusion, position, sentiment and cited sources. Engines measured this period: {', '.join(som) or 'n/a'}. ChatGPT and Google AI Overviews are added as a comparable pair once enabled and are always reported separately, never blended."]})
    for x in S: x["p"] = [p for p in x["p"] if p]
    return S

def projects():
    return [summary(c) for c in A.clients()]
