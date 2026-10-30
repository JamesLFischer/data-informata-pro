"""AI engine adapters. Each returns {"text": str, "citations": [url,...]}."""
import os, re, hashlib, random, time
import requests

TIMEOUT = 120

PACE = float(os.environ.get("AIVIS_PACE_SECONDS", "6"))  # free tier ~10 RPM; 6s keeps us well under
_last = [0.0]
import threading; _lock = threading.Lock()

class DailyQuotaExhausted(RuntimeError):
    pass

def _retry_delay(err):
    for d in err.get("details", []):
        if "RetryInfo" in d.get("@type", ""):
            m = re.match(r"([\d.]+)s", d.get("retryDelay", ""))
            if m: return float(m.group(1))
    return None

def _is_daily(err):
    for d in err.get("details", []):
        for v in d.get("violations", []) or []:
            if "PerDay" in v.get("quotaId", ""): return v
    return None

def _post(url, headers, body, retries=6):
    for i in range(retries):
        with _lock:  # global pacing across threads
            wait = _last[0] + PACE - time.time()
            if wait > 0: time.sleep(wait)
            _last[0] = time.time()
        try:
            r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        except requests.RequestException as e:
            if i < retries - 1: time.sleep(min(60, 2 ** (i + 2))); continue
            raise
        if r.status_code == 429:
            try: err = r.json().get("error", {})
            except ValueError: err = {}
            v = _is_daily(err)
            if v:
                raise DailyQuotaExhausted(f"daily quota exhausted ({v.get('quotaId')}, limit {v.get('quotaValue')}, model {v.get('quotaDimensions',{}).get('model')})")
            if i < retries - 1:
                time.sleep(min(120, (_retry_delay(err) or 2 ** (i + 3)) + 1)); continue
        elif r.status_code in (500, 502, 503, 529) and i < retries - 1:
            time.sleep(min(90, 2 ** (i + 2))); continue
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
        return r.json()

class Engine:
    name = "base"; env = None; default_model = None
    def __init__(self, model=None):
        self.key = os.environ.get(self.env) if self.env else None
        self.model = model or os.environ.get(f"{self.env}_MODEL".replace("_API_KEY", "")) or self.default_model
    @property
    def available(self): return bool(self.key)

class OpenAIEngine(Engine):
    name, env, default_model = "ChatGPT / SearchGPT", "OPENAI_API_KEY", "gpt-4.1-mini"
    def ask(self, prompt):
        d = _post("https://api.openai.com/v1/responses",
                  {"Authorization": f"Bearer {self.key}"},
                  {"model": self.model, "input": prompt, "tools": [{"type": "web_search"}]})
        text, cites = [], []
        for item in d.get("output", []):
            for c in item.get("content", []) or []:
                if c.get("type") == "output_text":
                    text.append(c.get("text", ""))
                    cites += [a.get("url") for a in c.get("annotations", []) if a.get("url")]
        return {"text": "\n".join(text), "citations": cites, "usage": d.get("usage", {})}

class GeminiEngine(Engine):
    name, env, default_model = "Google Gemini", "GEMINI_API_KEY", "gemini-3.5-flash"
    grounding = os.environ.get("GEMINI_GROUNDING", "1") != "0"
    def __init__(self, model=None):
        super().__init__(model)
        if not self.grounding: self.name = "Google Gemini (no grounding)"
    def ask(self, prompt):
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        if self.grounding: body["tools"] = [{"google_search": {}}]
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                  {"x-goog-api-key": self.key}, body)
        cand = (d.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        gm = cand.get("groundingMetadata", {})
        # grounding URIs are redirect links; the title carries the real domain
        cites = [c.get("web", {}).get("title") or c.get("web", {}).get("uri") for c in gm.get("groundingChunks", [])]
        return {"text": text, "citations": [c for c in cites if c], "usage": d.get("usageMetadata", {})}

class PerplexityEngine(Engine):
    # Sonar chat/completions was retired Sep 27 2026 -> Agent API (/v1/agent). Model is Perplexity's choice per effort level.
    name, env, default_model = "Perplexity", "PERPLEXITY_API_KEY", "fast"
    def ask(self, prompt):
        d = _post("https://api.perplexity.ai/v1/agent",
                  {"Authorization": f"Bearer {self.key}"},
                  {"effort": self.model if self.model in ("fast", "low", "medium", "high", "xhigh") else "fast", "input": prompt})
        text, cites = [], []
        for o in d.get("output", []):
            if o.get("type") == "search_results": cites += [x.get("url") for x in o.get("results", [])]
            for c in o.get("content", []) or []:
                if c.get("type") == "output_text": text.append(c.get("text", ""))
        u = d.get("usage", {}); u["cost_usd"] = (u.get("cost") or {}).get("total_cost")
        self.model_used = d.get("model")
        return {"text": "\n".join(text), "citations": [c for c in cites if c], "usage": u}

class ClaudeEngine(Engine):
    name, env, default_model = "Anthropic Claude", "ANTHROPIC_API_KEY", "claude-sonnet-4-5"
    def ask(self, prompt):
        d = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                  {"model": self.model, "max_tokens": 2048,
                   "messages": [{"role": "user", "content": prompt}],
                   "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]})
        text, cites = [], []
        for b in d.get("content", []):
            if b.get("type") == "text":
                text.append(b.get("text", ""))
                cites += [c.get("url") for c in b.get("citations", []) or [] if c.get("url")]
        return {"text": "".join(text), "citations": cites, "usage": d.get("usage", {})}

class MockEngine(Engine):
    """Deterministic fake answers for pipeline testing. Output is EXAMPLE DATA, not real AI results."""
    env = None
    def __init__(self, name, cfg, bias):
        self.name, self.cfg, self.bias, self.model, self.key = name, cfg, bias, "mock", "mock"
    def ask(self, prompt):
        rnd = random.Random(hashlib.md5((self.name + prompt).encode()).hexdigest())
        brand, comps = self.cfg["brand"], list(self.cfg.get("competitors", []))
        prods = self.cfg.get("products", []); facts = self.cfg.get("facts", [])
        rnd.shuffle(comps)
        names = comps[:4]
        r = rnd.random()
        if r < self.bias: names.insert(0, brand)
        elif r < self.bias + 0.25: names.insert(rnd.randint(1, 2), brand)
        elif r < self.bias + 0.35: names.append(brand)
        lines = []
        for i, n in enumerate(names, 1):
            extra = ""
            if n == brand:
                extra = f" Known for {rnd.choice(facts) if facts else 'good service'}"
                if prods and rnd.random() < 0.6: extra += f"; its {rnd.choice(prods)} is highly rated and reliable"
            lines.append(f"{i}. **{n}** - a solid option.{extra}")
        doms = [self.cfg.get("domain", "example.com"), "reddit.com", "youtube.com", "google.com/maps"]
        return {"text": "Here are good options:\n" + "\n".join(lines),
                "citations": [f"https://{d}/" for d in rnd.sample(doms, 2)], "usage": {}}

REAL = [GeminiEngine, PerplexityEngine, ClaudeEngine, OpenAIEngine]

# Rough list prices (USD per 1M tokens in/out) + per-search fees, for cost notes only. Verify on vendor pricing pages.
PRICES = {"gpt-4.1-mini": (0.4, 1.6, 0.025), "claude-sonnet-4-5": (3, 15, 0.01), "claude-haiku-4-5": (1, 5, 0.01),
          "gemini-3.5-flash": (0.3, 2.5, 0.035)}
def est_cost(model, usage):
    if not usage: return 0.0
    if usage.get("cost_usd") is not None: return float(usage["cost_usd"])
    i, o, search = PRICES.get(model, (1, 5, 0.02))
    tin = usage.get("input_tokens") or usage.get("promptTokenCount") or 0
    tout = usage.get("output_tokens") or usage.get("candidatesTokenCount") or 0
    return tin / 1e6 * i + tout / 1e6 * o + search
