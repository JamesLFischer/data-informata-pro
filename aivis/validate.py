"""Client config validation. Errors block live runs; warnings are printed (client delivery should wait until they're cleared).
CLI: python3 -m aivis.validate [slug ...]   (no args = every configs/*.yaml except _template)"""
import os, re, sys, glob, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(ROOT, "configs")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")

def check(cfg, slug=None):
    """-> (errors, warnings)"""
    E, W = [], []
    if not isinstance(cfg, dict): return ["config is not a YAML mapping"], []
    if slug is not None and not SLUG.match(slug): E.append(f"slug '{slug}' must be lowercase letters/digits/dashes (2-31 chars)")
    for k in ("brand", "domain", "clusters"):
        if not cfg.get(k): E.append(f"missing required field '{k}'")
    if cfg.get("brand") in ("Client Name",): E.append("brand is still the template placeholder")
    d = str(cfg.get("domain") or "")
    if d in ("example.com",): E.append("domain is still the template placeholder")
    elif d and (d.startswith("http") or "/" in d or " " in d): E.append(f"domain '{d}' should be a bare domain like example.com")
    for k in ("brand_aliases", "products", "competitors", "facts", "placeholders_unconfirmed"):
        if cfg.get(k) is not None and not isinstance(cfg.get(k), list): E.append(f"'{k}' must be a list")
    col = str(cfg.get("brand_color", "#1F4E79"))
    if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", col): E.append(f"brand_color '{col}' must be a 6-digit hex like #1F4E79")
    ids, n = set(), 0
    for ci, c in enumerate(cfg.get("clusters") or []):
        if not isinstance(c, dict) or not c.get("name"): E.append(f"cluster #{ci+1} needs a name"); continue
        ps = c.get("prompts") or []
        if not ps: E.append(f"cluster '{c['name']}' has no prompts")
        for p in ps:
            n += 1; text = p.get("text") if isinstance(p, dict) else p; pid = p.get("id") if isinstance(p, dict) else None
            if not text or str(text).strip() in ("...", "") or "TODO" in str(text): E.append(f"prompt {pid or n} in '{c['name']}' has no real text")
            if not pid: E.append(f"prompt #{n} in '{c['name']}' needs an id (e.g. P{n:02d}) - ids keep month-over-month history aligned")
            elif pid in ids: E.append(f"duplicate prompt id {pid}")
            ids.add(pid)
    if n and n < 25: W.append(f"only {n} prompts (aim for 25-50 for stable Share of Model)")
    if n > 60: W.append(f"{n} prompts - cost scales linearly; check ./run.sh <slug> --estimate")
    if not cfg.get("competitors"): W.append("no competitors listed - share-of-voice will only show the brand")
    if not cfg.get("facts"): W.append("no facts listed - citation accuracy can't be scored")
    if cfg.get("placeholders_unconfirmed"): W.append("unconfirmed: " + ", ".join(map(str, cfg["placeholders_unconfirmed"])))
    comp = [str(x).lower() for x in cfg.get("competitors") or []]
    if len(comp) != len(set(comp)): W.append("duplicate competitor names")
    if str(cfg.get("brand", "")).lower() in comp: E.append("brand is also listed as a competitor")
    return E, W

def check_file(path):
    slug = os.path.basename(path)[:-5]
    try: cfg = yaml.safe_load(open(path))
    except yaml.YAMLError as e: return [f"YAML parse error: {str(e).splitlines()[0]}"], []
    return check(cfg, slug)

def main(args=sys.argv[1:]):
    paths = [a if os.path.exists(a) else os.path.join(CDIR, a + ".yaml") for a in args] or \
            [f for f in sorted(glob.glob(os.path.join(CDIR, "*.yaml"))) if not os.path.basename(f).startswith("_")]
    bad = 0
    for p in paths:
        if not os.path.exists(p): print(f"✗ {p}: not found"); bad += 1; continue
        E, W = check_file(p); bad += bool(E)
        print(("✗ " if E else "⚠ " if W else "✓ ") + os.path.basename(p)[:-5] + ("" if E or W else ": OK"))
        for e in E: print("   ERROR:", e)
        for w in W: print("   warn: ", w)
    sys.exit(1 if bad else 0)
if __name__ == "__main__": main()
