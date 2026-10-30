"""Turn an engine answer into Michael-style log fields (LLM judge, rule-based fallback)."""
import os, re, json
from urllib.parse import urlparse
import requests, time
from .engines import _post, DailyQuotaExhausted

WEIGHTS = {"#1 Top Rec": 1.0, "Top 3": 0.7, "Incidental Mention": 0.3, "Not Mentioned": 0.0}
POS = ["praised", "reliable", "best", "top", "excellent", "highly rated", "recommended", "trusted", "fast", "great", "strong", "solid", "quality"]
NEG = ["complaint", "poor", "slow", "avoid", "issue", "problem", "unreliable", "worse", "expensive", "negative", "scam", "broken"]

def domains(urls):
    out = []
    for u in urls:
        u = u.strip()
        host = urlparse(u if "://" in u else "https://" + u).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        if host and host not in out: out.append(host)
    return out

def _find(text, name):
    m = re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", text.lower())
    return m.start() if m else None

def rule_score(cfg, prompt, answer):
    text = answer["text"]; brand = cfg["brand"]
    aliases = [brand] + cfg.get("brand_aliases", [])
    bpos = min([p for p in (_find(text, a) for a in aliases) if p is not None], default=None)
    prod_hit = [p for p in cfg.get("products", []) if _find(text, p) is not None]
    if bpos is None and prod_hit: bpos = min(_find(text, p) for p in prod_hit)
    if bpos is None:
        rank = "Not Mentioned"
    else:
        ahead = sum(1 for c in cfg.get("competitors", []) if (p := _find(text, c)) is not None and p < bpos)
        rank = "#1 Top Rec" if ahead == 0 else "Top 3" if ahead <= 2 else "Incidental Mention"
    sentiment, score = "N/A", 0
    if bpos is not None:
        win = text[max(0, bpos - 300): bpos + 500].lower()
        p = sum(win.count(w) for w in POS); n = sum(win.count(w) for w in NEG)
        sentiment = "Positive" if p > n else "Negative" if n > p else "Neutral"
        score = max(0, min(100, 50 + 12 * (p - n)))
    feats = [f for f in cfg.get("facts", []) if f.lower() in text.lower()]
    accuracy = "Accurate" if feats else ("Not verified" if bpos is not None else "N/A")
    gaps = []
    if rank == "Not Mentioned": gaps.append("Brand absent from answer")
    elif rank != "#1 Top Rec": gaps.append("Competitor ranked ahead")
    if cfg.get("domain") and cfg["domain"] not in " ".join(domains(answer["citations"] or re.findall(r"https?://[^\s)\]>\"']+", answer["text"]))): gaps.append("Own domain not cited")
    return {"brand_mentioned": bpos is not None and any(_find(text, a) is not None for a in aliases),
            "product_mentioned": bool(prod_hit), "rank": rank, "sentiment": sentiment, "score": score,
            "features": "; ".join(feats), "accuracy": accuracy, "gaps": "; ".join(gaps) or "None",
            "scored_by": "rules"}

JUDGE = """You are auditing an AI assistant's answer for brand visibility. Return ONLY JSON with keys:
brand_mentioned (bool), product_mentioned (bool), rank ("#1 Top Rec"|"Top 3"|"Incidental Mention"|"Not Mentioned"),
sentiment ("Positive"|"Neutral"|"Negative"|"N/A"), score (0-100 sentiment toward the brand, 0 if not mentioned),
features (short string: product/brand facts the answer cites), accuracy ("Accurate"|"Partially Accurate"|"Inaccurate"|"N/A", judged against the known facts),
gaps (one short sentence: what is missing or where competitors win).
Brand: {brand} (aliases: {aliases}). Products: {products}. Competitors: {competitors}. Known true facts: {facts}.
Prompt asked: {prompt}
Answer:
{answer}"""

def llm_score(cfg, prompt, answer):
    msg = JUDGE.format(brand=cfg["brand"], aliases=cfg.get("brand_aliases", []), products=cfg.get("products", []),
                       competitors=cfg.get("competitors", []), facts=cfg.get("facts", []), prompt=prompt,
                       answer=answer["text"][:12000])
    if k := os.environ.get("OPENAI_API_KEY"):
        r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {k}"},
            json={"model": os.environ.get("JUDGE_MODEL", "gpt-4.1-mini"), "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": msg}]}, timeout=120)
        r.raise_for_status(); raw, by = r.json()["choices"][0]["message"]["content"], "openai"
    elif k := os.environ.get("ANTHROPIC_API_KEY"):
        r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": k, "anthropic-version": "2023-06-01"},
            json={"model": os.environ.get("JUDGE_MODEL", "claude-haiku-4-5"), "max_tokens": 800,
                  "messages": [{"role": "user", "content": msg}]}, timeout=120)
        r.raise_for_status(); raw, by = r.json()["content"][0]["text"], "anthropic"
    elif k := os.environ.get("GEMINI_API_KEY"):
        j = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('JUDGE_MODEL','gemini-3.5-flash')}:generateContent",
            {"x-goog-api-key": k}, {"contents": [{"parts": [{"text": msg}]}],
            "generationConfig": {"responseMimeType": "application/json"}})
        raw, by = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"]), "gemini"
    else:
        return None
    d = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    d["scored_by"] = by
    if d.get("rank") not in WEIGHTS: d["rank"] = "Not Mentioned"
    return d

def score(cfg, prompt, answer, use_llm=True):
    base = rule_score(cfg, prompt, answer)
    if use_llm:
        try:
            d = llm_score(cfg, prompt, answer)
            if d: base.update({k: d[k] for k in base if k in d})
        except DailyQuotaExhausted as e:
            base["scored_by"] = f"rules (judge {str(e)[:90]})"
        except Exception as e:
            base["scored_by"] = f"rules (judge failed: {str(e)[:80]})"
    base["weight"] = WEIGHTS[base["rank"]]
    urls = answer["citations"] or re.findall(r"https?://[^\s)\]>\"']+", answer["text"])
    base["domains"] = ", ".join(domains(urls))
    return base
