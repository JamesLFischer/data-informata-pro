"""Create configs/<slug>.yaml from _template.yaml safely (any brand name characters), then validate.
CLI: python3 -m aivis.newclient <slug> "<Brand Name>" <domain> [--competitors "A, B, C"]"""
import os, re, sys, argparse, yaml
from .validate import CDIR, SLUG, check

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("brand"); ap.add_argument("domain")
    ap.add_argument("--competitors", default="", help="comma-separated; marked unconfirmed until James/the client confirms")
    a = ap.parse_args(argv)
    if not SLUG.match(a.slug): sys.exit(f"bad slug '{a.slug}': use lowercase letters, digits, dashes")
    dom = re.sub(r"^https?://", "", a.domain).strip("/").lower()
    if "/" in dom or "." not in dom: sys.exit(f"bad domain '{a.domain}': use a bare domain like example.com")
    f = os.path.join(CDIR, a.slug + ".yaml")
    if os.path.exists(f): sys.exit(f"{f} already exists")
    tpl = open(os.path.join(CDIR, "_template.yaml")).read()
    cfg = yaml.safe_load(tpl)
    comps = [c.strip() for c in a.competitors.split(",") if c.strip()]
    cfg.update({"brand": a.brand, "domain": dom, "competitors": comps,
                "placeholders_unconfirmed": ["competitors list", "facts", "prompt set"]})
    cfg["clusters"] = [{"name": n, "prompts": [{"id": f"P{i*5+j+1:02d}", "text": "TODO"} for j in range(5)]}
                       for i, n in enumerate(["Cluster 1 - Category Discovery", "Cluster 2 - Product & Specs", "Cluster 3 - Head-to-Head",
                                              "Cluster 4 - Educational", "Cluster 5 - Reputation & Objections"])]
    header = "\n".join(l for l in tpl.splitlines() if l.startswith("#"))
    body = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, width=200)
    open(f, "w").write(f"# Client: {a.brand} ({dom}) - created by new_client.sh. Replace every TODO prompt; only VERIFIED claims in facts.\n{header}\n{body}")
    E, W = check(yaml.safe_load(open(f)), a.slug)
    print(f"created {f}\nNext: replace the 25 TODO prompts, add competitors + verified facts, then:\n"
          f"  python3 -m aivis.validate {a.slug}     # must show no ERROR lines\n  ./run.sh {a.slug} --estimate          # cost, no spend\n"
          f"  ./run.sh {a.slug} --limit 2            # smoke test (marked _SMOKE, not published)\n"
          f"Still to do: {len(E)} error(s), {len(W)} warning(s).")
if __name__ == "__main__": main()
