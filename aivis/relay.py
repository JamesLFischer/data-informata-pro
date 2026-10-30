"""Encrypted relay: lets the public GitHub Pages site talk to this box with NO inbound connection.
Browser -> ntfy.sh topic <channel>-req  (AES-256-GCM, key = PBKDF2-SHA256(password, channel, 200k))
Box     -> subscribes over HTTPS, decrypts, runs the same handlers as aivis.server, encrypts reply -> <channel>-r-<reqid>
ntfy.sh only ever sees ciphertext. Wrong password = undecryptable = ignored. Replays/old requests (>120s) are dropped.
Run: python3 -m aivis.relay   (or ./relay.sh)"""
import os, json, time, base64, zlib, hashlib, secrets, sys, requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from . import asks
from .server import _secret
NTFY = os.environ.get("AIVIS_NTFY", "https://ntfy.sh").rstrip("/")
CHAN = _secret("AIVIS_RELAY_CHANNEL"); PW = _secret("AIVIS_DASH_PASSWORD")
KEY = hashlib.pbkdf2_hmac("sha256", PW.encode(), CHAN.encode(), 200_000, 32) if PW and CHAN else None
CHUNK = 3000

def enc(obj):
    iv = secrets.token_bytes(12); raw = zlib.compress(json.dumps(obj).encode())
    return base64.b64encode(iv + AESGCM(KEY).encrypt(iv, raw, None)).decode()
def dec(s):
    b = base64.b64decode(s); return json.loads(zlib.decompress(AESGCM(KEY).decrypt(b[:12], b[12:], None)))

def handle(req):
    p, b = req.get("path", ""), req.get("body") or {}
    if p == "clients": return asks.clients()
    if p == "context": return asks.context(b.get("client", ""))
    if p == "asks": return [x for x in asks.load_all() if x["client"] == b.get("client")][-30:]
    if p == "ask":
        if not str(b.get("question", "")).strip(): return {"error": "question required"}
        return asks.save(b)
    return {"error": "unknown path"}

def publish(topic, text):
    r = requests.post(f"{NTFY}/{topic}", data=text.encode(), headers={"Cache": "yes"}, timeout=20); r.raise_for_status()

def reply(rid, obj):
    blob = enc(obj); parts = [blob[i:i + CHUNK] for i in range(0, len(blob), CHUNK)] or [""]
    for i, d in enumerate(parts):
        publish(f"{CHAN}-r-{rid}", json.dumps({"i": i, "n": len(parts), "d": d}))
        if len(parts) > 1: time.sleep(0.3)

def main():
    if not KEY: sys.exit("missing AIVIS_DASH_PASSWORD / AIVIS_RELAY_CHANNEL in secrets dir")
    seen = {}; print(f"relay listening on {NTFY}/<channel>-req", flush=True)
    while True:
        try:
            with requests.get(f"{NTFY}/{CHAN}-req/json", stream=True, timeout=(10, 90)) as r:
                for line in r.iter_lines():
                    if not line: continue
                    m = json.loads(line)
                    if m.get("event") != "message": continue
                    try: req = dec(m["message"])
                    except Exception: continue  # wrong password / junk
                    rid = str(req.get("id", ""))[:40]
                    if not rid.isalnum() or rid in seen or abs(time.time() - req.get("ts", 0) / 1000) > 120: continue
                    seen[rid] = time.time(); seen = {k: v for k, v in seen.items() if time.time() - v < 600}
                    try: out = handle(req)
                    except Exception as e: out = {"error": str(e)[:200]}
                    reply(rid, out); print(time.strftime("%H:%M:%S"), "served", req.get("path"), flush=True)
        except Exception as e:
            print("reconnect:", str(e)[:120], flush=True); time.sleep(3)

if __name__ == "__main__": main()
