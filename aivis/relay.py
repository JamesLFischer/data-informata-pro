"""Encrypted relay: lets the public GitHub Pages site talk to this box with NO inbound connection.
Browser -> ntfy.sh topic <channel>-req  (AES-256-GCM, key = PBKDF2-SHA256(password, channel, 200k))
Box     -> subscribes over HTTPS, decrypts, runs the same handlers as aivis.server, encrypts reply -> <channel>-r-<reqid>
ntfy.sh only ever sees ciphertext. Wrong password = undecryptable = ignored. Replays/old requests (>120s) are dropped.
Liveness: the site may post a random id to <channel>-ping; the box answers on <channel>-pong-<id> (no data, rate-limited),
so the site can tell "wrong password" from "box offline" without any secret.
Robustness: reconnects with exponential backoff, resumes from the last seen message (no lost requests during a reconnect),
honours ntfy 429 Retry-After, retries publishes, and writes a heartbeat to $AIVIS_RELAY_STATUS for relay_watchdog.sh.
Run: python3 -m aivis.relay   (or ./relay.sh)"""
import os, json, time, base64, zlib, hashlib, secrets, sys, requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from . import asks
from .server import _secret
NTFY = os.environ.get("AIVIS_NTFY", "https://ntfy.sh").rstrip("/")
CHAN = _secret("AIVIS_RELAY_CHANNEL"); PW = _secret("AIVIS_DASH_PASSWORD")
KEY = hashlib.pbkdf2_hmac("sha256", PW.encode(), CHAN.encode(), 200_000, 32) if PW and CHAN else None
CHUNK = 3000
STATUS_FILE = os.environ.get("AIVIS_RELAY_STATUS", "/tmp/aivis_relay_status.json")
SEEN_FILE = STATUS_FILE.replace("status", "seen")  # request ids already served, so a restart's catch-up replay never double-saves an ask
ST = {"pid": os.getpid(), "started": time.time(), "connected": False, "heartbeat": time.time(), "served": 0, "errors": 0, "last_error": ""}

def status(**kw):
    ST.update(kw); ST["heartbeat"] = time.time()
    try:
        tmp = STATUS_FILE + ".tmp"; json.dump(ST, open(tmp, "w")); os.replace(tmp, STATUS_FILE)
    except OSError: pass

def enc(obj):
    iv = secrets.token_bytes(12); raw = zlib.compress(json.dumps(obj).encode())
    return base64.b64encode(iv + AESGCM(KEY).encrypt(iv, raw, None)).decode()
def dec(s):
    b = base64.b64decode(s); return json.loads(zlib.decompress(AESGCM(KEY).decrypt(b[:12], b[12:], None)))

def handle(req):
    p, b = req.get("path", ""), req.get("body") or {}
    if p == "ping": return {"ok": True, "ts": int(time.time())}
    if p == "projects":
        from . import project; return project.projects()
    if p == "project":
        from . import project; return project.build(b.get("client"), b.get("engines"))
    if p == "workspaces":
        from . import workspaces; return workspaces.listing()
    if p == "workspace_add":
        from . import workspaces; return workspaces.add(b.get("name"))
    if p == "workspace_move":
        from . import workspaces; return workspaces.move(b.get("client"), b.get("to"))
    if p == "clients": return asks.clients()
    if p == "context": return asks.context(b.get("client", ""), b.get("date_from") or None, b.get("date_to") or None, b.get("engines") or None)
    if p == "asks": return [x for x in asks.load_all() if x["client"] == b.get("client")][-30:]
    if p == "ask":
        if not str(b.get("question", "")).strip(): return {"error": "question required"}
        return asks.save(b)
    return {"error": "unknown path"}

def _wait(r, default):
    try: return min(300, max(1, int(r.headers.get("Retry-After", default))))
    except (TypeError, ValueError): return default

def publish(topic, text, tries=5):
    delay = 1
    for i in range(tries):
        try:
            r = requests.post(f"{NTFY}/{topic}", data=text.encode(), headers={"Cache": "yes"}, timeout=20)
            if r.status_code == 429:
                w = _wait(r, 10); status(last_error=f"ntfy rate limit on publish, waiting {w}s"); time.sleep(w); continue
            r.raise_for_status(); return True
        except requests.RequestException as e:
            status(errors=ST["errors"] + 1, last_error=f"publish: {str(e)[:100]}")
        time.sleep(delay); delay = min(delay * 2, 20)
    return False

def reply(rid, obj):
    blob = enc(obj); parts = [blob[i:i + CHUNK] for i in range(0, len(blob), CHUNK)] or [""]
    for i, d in enumerate(parts):
        if not publish(f"{CHAN}-r-{rid}", json.dumps({"i": i, "n": len(parts), "d": d})): return False
        if len(parts) > 1: time.sleep(0.3)
    return True

_last_pong = [0.0]
def pong(msg):
    pid = (msg or "").strip()[:40]
    if not pid.isalnum() or time.time() - _last_pong[0] < 2: return
    _last_pong[0] = time.time(); publish(f"{CHAN}-pong-{pid}", "1", tries=2)

def serve_line(m, seen):
    if m.get("event") != "message": return
    if m.get("topic") == f"{CHAN}-ping": return pong(m.get("message"))
    try: req = dec(m["message"])
    except Exception: return  # wrong password / junk
    rid = str(req.get("id", ""))[:40]
    if not rid.isalnum() or rid in seen or abs(time.time() - req.get("ts", 0) / 1000) > 120: return
    seen[rid] = time.time()
    for k in [k for k, v in seen.items() if time.time() - v > 600]: del seen[k]
    try: json.dump(seen, open(SEEN_FILE, "w"))
    except OSError: pass
    try: out = handle(req)
    except Exception as e: out = {"error": str(e)[:200]}
    ok = reply(rid, out); status(served=ST["served"] + 1)
    print(time.strftime("%H:%M:%S"), "served" if ok else "FAILED to reply", req.get("path"), flush=True)

def main():
    if not KEY: sys.exit("missing AIVIS_DASH_PASSWORD / AIVIS_RELAY_CHANNEL in secrets dir")
    try: seen = {k: v for k, v in json.load(open(SEEN_FILE)).items() if time.time() - v < 600}
    except (OSError, ValueError): seen = {}
    since, backoff = "2m", 2  # 2m: pick up requests sent while the relay was restarting
    print(f"relay listening on {NTFY}/<channel>-req (+ -ping)", flush=True); status()
    while True:
        try:
            with requests.get(f"{NTFY}/{CHAN}-req,{CHAN}-ping/json", params={"since": since}, stream=True, timeout=(10, 90)) as r:
                if r.status_code == 429:
                    w = _wait(r, 60); status(connected=False, last_error=f"ntfy rate limit on subscribe, waiting {w}s")
                    print("rate limited, sleeping", w, flush=True); time.sleep(w); continue
                r.raise_for_status(); status(connected=True)
                for line in r.iter_lines():
                    status(); backoff = 2  # every line incl. ntfy keepalives (~45s) refreshes the heartbeat
                    if not line: continue
                    m = json.loads(line)
                    if m.get("time"): since = str(int(m["time"]))  # unix ts; duplicates are dropped by request id
                    serve_line(m, seen)
        except Exception as e:
            status(connected=False, errors=ST["errors"] + 1, last_error=f"stream: {str(e)[:100]}")
            print("reconnect in", backoff, "s:", str(e)[:120], flush=True); time.sleep(backoff); backoff = min(backoff * 2, 60)

if __name__ == "__main__": main()
