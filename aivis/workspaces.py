"""Workspaces: top-level containers of client projects. Stored locally (inbox/, gitignored)."""
import json, re, time, pathlib
F = pathlib.Path(__file__).resolve().parent.parent / "inbox" / "workspaces.json"
DEFAULT = {"id": "default", "name": "Data Informata", "clients": [], "created": "2026-10-31"}

def _load():
    try: return json.loads(F.read_text())
    except Exception: return [dict(DEFAULT)]
def _save(w):
    F.parent.mkdir(parents=True, exist_ok=True); F.write_text(json.dumps(w, indent=1))

def listing():
    from . import asks
    w = _load(); allc = list(asks.clients())
    allc = [c if isinstance(c, str) else (c.get("client") or c.get("id")) for c in allc]
    placed = {c for x in w for c in x["clients"]}
    d = next((x for x in w if x["id"] == "default"), None) or w[0]
    d["clients"] = d["clients"] + [c for c in allc if c not in placed]
    return w

def add(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if not name: return {"error": "name required"}
    w = listing(); base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "ws"; i, n = base, 2
    while any(x["id"] == i for x in w): i = f"{base}-{n}"; n += 1
    w.append({"id": i, "name": name, "clients": [], "created": time.strftime("%Y-%m-%d")}); _save(w)
    return {"ok": True, "id": i, "workspaces": w}

def move(client, to):
    w = listing()
    if not any(x["id"] == to for x in w): return {"error": "unknown workspace"}
    for x in w:
        x["clients"] = [c for c in x["clients"] if c != client]
        if x["id"] == to: x["clients"].append(client)
    _save(w); return {"ok": True, "workspaces": w}
