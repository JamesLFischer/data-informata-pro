"""Build a static multi-client dashboard in docs/ (GitHub Pages ready) from output/<slug>/<run>/.
Usage: python3 -m aivis.dashboard [--include-examples] [--out private_site]
docs/ is the PUBLIC GitHub Pages shell (no client data); client data is only served by aivis.server behind login."""
import argparse, csv, glob, html, os, shutil, datetime, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = """body{font-family:system-ui,sans-serif;margin:0;background:#f5f7fa;color:#1a1a1a}header{background:#1F4E79;color:#fff;padding:20px 32px}
main{padding:24px 32px;max-width:1100px}.card{background:#fff;border-radius:8px;padding:18px 22px;margin:0 0 18px;box-shadow:0 1px 3px #0002}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:6px 8px;border-bottom:1px solid #e3e6ea;text-align:left}th{background:#eef2f6}
.tag{font-size:12px;background:#fde7c4;padding:2px 6px;border-radius:4px;margin-left:6px}a{color:#1F4E79}small{color:#666}"""
ASK = "<div class=card><small>Client Q&amp;A lives in the authenticated app (docs/index.html → Sign in).</small></div>"
def page(title, body, client=""):
    return f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'><title>{html.escape(title)}</title><style>{CSS}</style></head><body data-client='{html.escape(client)}'><header><h1>{html.escape(title)}</h1><small>Seattle Digital Marketing · AI Search Visibility · updated {datetime.date.today()}</small></header><main>{body}{ASK}</main></body></html>"
def table(rows):
    if not rows: return "<p><small>No dashboard data.</small></p>"
    h = "".join(f"<th>{html.escape(c)}</th>" for c in rows[0])
    b = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f"<table><tr>{h}</tr>{b}</table>"
def read_dash(run):
    f = glob.glob(os.path.join(run, "*_executive_dashboard.csv"))
    if not f: return []
    rows = list(csv.reader(open(f[0])))
    return rows[1:] if rows and rows[0] and rows[0][0].startswith("EXAMPLE") else rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--include-examples", action="store_true"); ap.add_argument("--out", default="private_site")  # gitignored: contains client data
    a = ap.parse_args(); out = os.path.join(ROOT, a.out)
    shutil.rmtree(os.path.join(out, "clients"), ignore_errors=True); os.makedirs(out, exist_ok=True)
    cards = []
    for cfgf in sorted(glob.glob(os.path.join(ROOT, "configs", "*.yaml"))):
        slug = os.path.basename(cfgf)[:-5]
        if slug.startswith("_"): continue
        cfg = yaml.safe_load(open(cfgf))
        runs = sorted(d for d in glob.glob(os.path.join(ROOT, "output", slug, "*")) if os.path.isdir(d) and (a.include_examples or not (d.endswith("_EXAMPLE") or d.endswith("_SMOKE"))))
        cdir = os.path.join(out, "clients", slug); os.makedirs(cdir, exist_ok=True)
        trend = [["Run"] + [d[0] for d in read_dash(runs[-1])[1:]]] if runs else []
        for r in runs:
            m = {d[0]: d[5] for d in read_dash(r)[1:] if len(d) > 5}
            if trend: trend.append([os.path.basename(r)] + [m.get(k, "—") for k in trend[0][1:]])
        trend_html = f"<div class=card><h3>Share of Model trend (per engine)</h3>{table(trend)}</div>" if len(trend) > 2 else ""
        items = []
        for r in reversed(runs):
            name = os.path.basename(r); dst = os.path.join(cdir, name); os.makedirs(dst)
            links = []
            for ext, label in (("_report.html", "Report"), ("_report.pdf", "PDF"), ("_share_of_voice.csv", "Share of voice CSV"), ("_executive_dashboard.csv", "Dashboard CSV")):
                for f in glob.glob(os.path.join(r, "*" + ext)):
                    fn = ext.lstrip("_"); shutil.copy(f, os.path.join(dst, fn)); links.append(f"<a href='{name}/{fn}'>{label}</a>")
            tag = "<span class=tag>EXAMPLE</span>" if name.endswith("_EXAMPLE") else ""
            items.append(f"<div class=card><h3>{html.escape(name)}{tag}</h3>{' · '.join(links)}{table(read_dash(r))}</div>")
        open(os.path.join(cdir, "index.html"), "w").write(page(f"{cfg['brand']} — run history", "<p><a href='../../index.html'>← All clients</a></p>" + trend_html + ("".join(items) or "<p>No runs yet.</p>"), slug))
        latest = runs[-1] if runs else None
        summ = table(read_dash(latest)) if latest else "<p><small>No runs yet.</small></p>"
        lt = os.path.basename(latest) if latest else "—"
        cards.append(f"<div class=card><h2><a href='clients/{slug}/index.html'>{html.escape(cfg['brand'])}</a></h2><small>{html.escape(cfg.get('domain',''))} · {len(runs)} run(s) · latest: {html.escape(lt)}</small>{summ}</div>")
    open(os.path.join(out, "index.html"), "w").write(page("AI Visibility Dashboard", "".join(cards)))
    print("wrote", os.path.join(out, "index.html"))
if __name__ == "__main__": main()
