"""Local dashboard + ask API. Binds 127.0.0.1 only. Auth: POST /api/login {password} -> bearer token (12h, HMAC-signed). Password from AIVIS_DASH_PASSWORD (env or secrets dir).
Static private site is served only to direct localhost requests; through a tunnel only the authenticated API is reachable.
GET /  -> docs/ ; GET /api/clients ; GET /api/asks[?client=] ; GET /api/context?client=&from=YYYY-MM-DD&to=YYYY-MM-DD&engines=perplexity,gemini ; POST /api/ask {client,question,date_range,filters}"""
import os, json, hmac, hashlib, time, base64
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from . import asks
DOCS = os.path.join(asks.ROOT, os.environ.get("AIVIS_SITE_DIR", "private_site")); TOKEN = os.environ.get("AIVIS_ASK_TOKEN", "")
SD = os.environ.get("AIVIS_SECRETS_DIR", "/home/box/.secrets")
def _secret(name):
    v = os.environ.get(name)
    if not v and os.path.exists(os.path.join(SD, name)): v = open(os.path.join(SD, name)).read().strip()
    return v or ""
PASSWORD = _secret("AIVIS_DASH_PASSWORD"); SIGN = (_secret("AIVIS_SESSION_KEY") or PASSWORD).encode()
ORIGINS = set(filter(None, os.environ.get("AIVIS_ALLOWED_ORIGINS", "https://jameslfischer.github.io,http://127.0.0.1:8000,http://localhost:8000").split(",")))
TTL = 12 * 3600
def make_token():
    exp = str(int(time.time()) + TTL); sig = hmac.new(SIGN, exp.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{exp}.{sig}".encode()).decode()
def check_token(t):
    try: exp, sig = base64.urlsafe_b64decode(t.encode()).decode().split(".")
    except Exception: return False
    return int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(SIGN, exp.encode(), hashlib.sha256).hexdigest())
class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DOCS, **k)
    def _cors(self):
        o = self.headers.get("Origin", "")
        if o in ORIGINS: self.send_header("Access-Control-Allow-Origin", o); self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    def do_OPTIONS(self): self.send_response(204); self._cors(); self.end_headers()
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self._cors(); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _ok(self):
        a = self.headers.get("Authorization", "")
        return bool(PASSWORD) and a.startswith("Bearer ") and check_token(a[7:])
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/api/health": return self._json({"ok": True, "auth": bool(PASSWORD)})
        if not u.path.startswith("/api/"):
            return super().do_GET() if self.client_address[0] == "127.0.0.1" and not self.headers.get("Cf-Connecting-Ip") else self._json({"error": "static files are local-only"}, 403)
        if not self._ok(): return self._json({"error": "bad token"}, 401)
        if u.path == "/api/clients": return self._json(asks.clients())
        if u.path == "/api/context":
            g = lambda k: q.get(k, [""])[0] or None
            return self._json(asks.context(g("client") or "", g("from"), g("to"), g("engines")))
        if u.path == "/api/asks":
            c = q.get("client", [None])[0]; return self._json([x for x in asks.load_all() if not c or x["client"] == c][-30:])
        self._json({"error": "not found"}, 404)
    def do_POST(self):
        if urlparse(self.path).path == "/api/login":
            n = min(int(self.headers.get("Content-Length", 0)), 2000)
            try: pw = json.loads(self.rfile.read(n) or b"{}").get("password", "")
            except ValueError: pw = ""
            if PASSWORD and hmac.compare_digest(str(pw), PASSWORD): return self._json({"token": make_token(), "ttl": TTL})
            time.sleep(2); return self._json({"error": "wrong password"}, 401)
        if urlparse(self.path).path != "/api/ask": return self._json({"error": "not found"}, 404)
        if not self._ok(): return self._json({"error": "bad token"}, 401)
        n = min(int(self.headers.get("Content-Length", 0)), 20000)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._json({"error": "bad json"}, 400)
        if not body.get("question"): return self._json({"error": "question required"}, 400)
        self._json(asks.save(body))
if __name__ == "__main__":
    if not PASSWORD: print("WARNING: no AIVIS_DASH_PASSWORD - all /api calls will be refused")
    port = int(os.environ.get("PORT", 8000)); print(f"dashboard + ask API on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
