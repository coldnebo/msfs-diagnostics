"""Polar comparison page: manual polars vs measured steady legs, across all runs.

Per aircraft:
- the polar curve with every steady leg on it. legs are brought back to the
  polar's reference mass, straight flight and sea level (polar.to_reference),
  so they sit on the same scale as the curve.
- the gap per leg: measured − predicted sink, in the leg's own conditions.
Across aircraft: predicted vs measured sink, with the line of agreement.

Inline SVG with a small hover script; no libraries, works offline.

usage: python -m msfsdiag.analysis.polar_report    (also built by report --all)
"""

import html
import math
import re
from datetime import datetime
from pathlib import Path
from statistics import median, pstdev

from .. import __version__
from ..config import load as load_config
from . import legs as legs_mod
from . import polar as polar_mod
from . import run as run_mod

GOOD_MS = 0.15      # |Δ| within this counts as matching the polar
W, H = 640, 340     # svg viewBox
ML, MR, MT, MB = 58, 18, 14, 46


# ---------- data

def collect(baselines_dir: Path, polars):
    """{polar name: {"polar": Polar, "legs": [Leg]}} over every run under baselines_dir."""
    out = {}
    for path in run_mod.glider_runs(baselines_dir, polars):
        r = run_mod.load(path, polars)
        # older runs didn't record flaps; their note may say where the lever was ("flaps were at index 6")
        noted = re.search(r"flaps? (?:were |was )?at index (\d+)", r.meta.get("note") or "", re.I)
        for g in legs_mod.find_legs(r.rows):
            pol = polar_mod.for_title(polars, g.title)
            if not pol:
                continue
            g.run = path.stem
            g.flap_from_note = bool(not g.flap and noted)
            if g.flap_from_note:
                g.flap = noted.group(1)
            out.setdefault(pol.name, {"polar": pol, "legs": []})["legs"].append(g)
    return out


def category(g, pol=None):
    if pol is not None and not pol.has_flaps:
        return "no flaps"
    if not g.flap:
        return "flap not recorded"
    names = dict(pol.flap_names) if pol is not None else {}
    idx = g.flap.split(",")
    if len(idx) > 1:
        return "flap changing (" + " → ".join(names.get(i, i) for i in reversed(idx)) + ")"
    label = "flap " + names.get(idx[0], "index " + idx[0])
    return label + (" (pilot note)" if getattr(g, "flap_from_note", False) else "")


# ---------- svg helpers

def nice_ticks(lo, hi, n=5):
    span = max(hi - lo, 1e-9)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + step * 1e-6:
        out.append(round(t, 10))
        t += step
    return out


class Frame:
    def __init__(self, x0, x1, y0, y1, invert_y=False):
        self.x0, self.x1, self.y0, self.y1, self.inv = x0, x1, y0, y1, invert_y

    def x(self, v):
        return ML + (v - self.x0) / (self.x1 - self.x0) * (W - ML - MR)

    def y(self, v):
        f = (v - self.y0) / (self.y1 - self.y0)
        return MT + f * (H - MT - MB) if self.inv else H - MB - f * (H - MT - MB)


def axes(fr, xlabel, ylabel, xfmt="{:g}", yfmt="{:g}"):
    s = []
    for t in nice_ticks(fr.y0, fr.y1):
        y = fr.y(t)
        s.append(f'<line class="grid" x1="{ML}" x2="{W - MR}" y1="{y:.1f}" y2="{y:.1f}"/>'
                 f'<text class="tick" x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end">{yfmt.format(t)}</text>')
    for t in nice_ticks(fr.x0, fr.x1, 6):
        x = fr.x(t)
        s.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{MT}" y2="{H - MB}"/>'
                 f'<text class="tick" x="{x:.1f}" y="{H - MB + 18}" text-anchor="middle">{xfmt.format(t)}</text>')
    s.append(f'<line class="axis" x1="{ML}" x2="{W - MR}" y1="{H - MB}" y2="{H - MB}"/>')
    s.append(f'<text class="alabel" x="{(ML + W - MR) / 2:.0f}" y="{H - 8}" text-anchor="middle">{html.escape(xlabel)}</text>')
    s.append(f'<text class="alabel" transform="translate(14 {(MT + H - MB) / 2:.0f}) rotate(-90)" '
             f'text-anchor="middle">{html.escape(ylabel)}</text>')
    return "".join(s)


def dot(x, y, cls, tip):
    return (f'<g class="pt" data-tip="{html.escape(tip)}"><circle class="dot {cls}" cx="{x:.1f}" cy="{y:.1f}" r="5"/>'
            f'<circle class="hit" cx="{x:.1f}" cy="{y:.1f}" r="12"/></g>')


def svg(body, label):
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}">'
            f'<defs><clipPath id="plot"><rect x="{ML}" y="{MT}" width="{W - ML - MR}" height="{H - MT - MB}"/></clipPath></defs>'
            f"{body}</svg>")


def tip_for(g, pol=None):
    pred = "–" if g.pred_sink_ms is None else f"{g.pred_sink_ms:.2f}"
    delta = "–" if g.delta_ms is None else f"{g.delta_ms:+.2f}"
    return (f"{g.run}\n{datetime.fromtimestamp(g.t0):%H:%M:%S}, {g.dur_s:.0f} s\n"
            f"IAS {g.ias_kmh:.0f} km/h, bank {g.bank_deg:.0f}°, {g.weight_kg:.0f} kg, {category(g, pol)}\n"
            f"air {g.air_w_ms:+.2f}, climb {g.te_ms:+.2f} m/s\n"
            f"sink {g.sink_ms:.2f}, predicted {pred}, gap {delta} m/s")


# ---------- charts

def polar_chart(pol, legs, cats):
    ref = min(pol.sets, key=lambda st: abs(st.mass_kg - median(g.weight_kg for g in legs)))
    pts = [(g, *polar_mod.to_reference(ref, g.ias_kmh, g.sink_ms, g.weight_kg, g.bank_deg, g.tas_kmh)) for g in legs]
    lo, hi = pol.valid_ias_kmh
    lo, hi = (max(lo, 40), min(hi, 300)) if hi < 1e8 else (60, 220)
    xs = [v for _, v, _ in pts] + [lo, hi]
    x0, x1 = math.floor(min(xs) / 10) * 10 - 5, math.ceil(max(xs) / 10) * 10 + 5
    ymax = max([s for *_, s in pts] + [ref.sink(hi)]) * 1.12
    fr = Frame(x0, x1, 0, max(1.0, math.ceil(ymax * 4) / 4), invert_y=True)

    curve = " ".join(f"{'M' if i == 0 else 'L'}{fr.x(v):.1f},{fr.y(ref.sink(v)):.1f}"
                     for i, v in enumerate(range(int(lo), int(hi) + 1, 2)))
    vend = int(hi)
    body = [axes(fr, f"IAS km/h  (legs scaled to {ref.mass_kg:.0f} kg, straight flight, sea level)", "sink m/s  (down = more sink)"),
            f'<path class="curve" d="{curve}" clip-path="url(#plot)"/>',
            # label just below the slow end of the curve, clear of the legs (which cluster near min sink)
            f'<text class="dlabel" x="{fr.x(lo) + 2:.1f}" y="{fr.y(ref.sink(lo)) + 18:.1f}">'
            f'manual polar, {ref.mass_kg:.0f} kg</text>']
    for g, v, s in sorted(pts, key=lambda p: cats.index(category(p[0], pol)) if category(p[0], pol) in cats else 9, reverse=True):
        body.append(dot(fr.x(v), fr.y(s), cls_for(g, cats, pol), tip_for(g, pol)))
    return svg("".join(body), f"{pol.name} polar with measured legs"), ref


def gap_chart(legs, cats, pol):
    pts = [g for g in legs if g.delta_ms is not None]
    if not pts:
        return '<p class="note">No legs inside the polar\'s valid speed range.</p>'
    x0 = math.floor(min(g.ias_kmh for g in pts) / 10) * 10 - 5
    x1 = math.ceil(max(g.ias_kmh for g in pts) / 10) * 10 + 5
    m = max(0.5, max(abs(g.delta_ms) for g in pts) * 1.15)
    m = math.ceil(m * 4) / 4
    fr = Frame(x0, x1, -m, m)
    band = (f'<rect class="band" x="{ML}" width="{W - ML - MR}" y="{fr.y(GOOD_MS):.1f}" '
            f'height="{fr.y(-GOOD_MS) - fr.y(GOOD_MS):.1f}"/>')
    body = [band, axes(fr, "IAS km/h", "measured − predicted sink, m/s", yfmt="{:+g}"),
            f'<line class="zero" x1="{ML}" x2="{W - MR}" y1="{fr.y(0):.1f}" y2="{fr.y(0):.1f}"/>',
            f'<text class="dlabel" x="{W - MR - 4}" y="{fr.y(GOOD_MS) - 6:.1f}" text-anchor="end">±{GOOD_MS} m/s</text>',
            f'<text class="dlabel" x="{ML + 6}" y="{MT + 14}">worse than polar ↑</text>',
            f'<text class="dlabel" x="{ML + 6}" y="{H - MB - 8}">better than polar ↓</text>']
    for g in pts:
        body.append(dot(fr.x(g.ias_kmh), fr.y(g.delta_ms), cls_for(g, cats, pol), tip_for(g, pol)))
    return svg("".join(body), "gap between measured and predicted sink per leg")


def summary_chart(groups):
    legs = [(name, g) for name, d in groups.items() for g in d["legs"] if g.pred_sink_ms is not None]
    if not legs:
        return ""
    names = list(groups)
    top = max(max(g.sink_ms, g.pred_sink_ms) for _, g in legs)
    top = math.ceil(top * 1.1 * 4) / 4
    fr = Frame(0, top, 0, top)
    band = (f'<path class="band" d="M{fr.x(0):.1f},{fr.y(GOOD_MS):.1f} L{fr.x(top - GOOD_MS):.1f},{fr.y(top):.1f} '
            f'L{fr.x(top):.1f},{fr.y(top):.1f} L{fr.x(top):.1f},{fr.y(top - GOOD_MS):.1f} '
            f'L{fr.x(GOOD_MS):.1f},{fr.y(0):.1f} L{fr.x(0):.1f},{fr.y(0):.1f} Z" clip-path="url(#plot)"/>')
    body = [band, axes(fr, "predicted sink, m/s (polar, in the leg's conditions)", "measured sink, m/s"),
            f'<line class="zero" x1="{fr.x(0):.1f}" y1="{fr.y(0):.1f}" x2="{fr.x(top):.1f}" y2="{fr.y(top):.1f}"/>',
            f'<text class="dlabel" x="{fr.x(top) - 6:.1f}" y="{fr.y(top) + 16:.1f}" text-anchor="end">measured = predicted</text>']
    for name, g in legs:
        body.append(dot(fr.x(g.pred_sink_ms), fr.y(g.sink_ms), f"c{names.index(name) + 1}", f"{name}\n" + tip_for(g)))
    return svg("".join(body), "predicted vs measured sink, all aircraft")


def cls_for(g, cats, pol=None):
    c = category(g, pol)
    return f"c{cats.index(c) + 1}" if c in cats else "cO"


def legend(items):
    return '<div class="legend">' + "".join(
        f'<span><i class="sw {cls}"></i>{html.escape(label)}</span>' for cls, label in items) + "</div>"


# ---------- page

def build(out_path, baselines_dir, polars):
    groups = collect(baselines_dir, polars)
    sections = []
    for name, d in groups.items():
        pol, legs = d["polar"], d["legs"]
        counts = {}
        for g in legs:
            counts[category(g, pol)] = counts.get(category(g, pol), 0) + 1
        cats = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:3]
        chart, ref = polar_chart(pol, legs, cats)
        with_pred = [g for g in legs if g.delta_ms is not None]
        good = [g for g in with_pred if abs(g.delta_ms) <= GOOD_MS]
        med = median(g.delta_ms for g in with_pred) if with_pred else None
        sd = pstdev([g.delta_ms for g in with_pred]) if len(with_pred) > 1 else None
        titles = sorted({g.title for g in legs})
        items = [(f"c{i + 1}", f"{c} ({counts[c]})") for i, c in enumerate(cats)]
        if len(counts) > 3:
            items.append(("cO", "other"))
        stats = (f'<div class="stats"><div><b>{len(legs)}</b><span>steady legs</span></div>'
                 f'<div><b>{len(good)} / {len(with_pred)}</b><span>within ±{GOOD_MS} m/s of the polar</span></div>'
                 f'<div><b>{"–" if med is None else f"{med:+.2f}"}</b><span>median gap, m/s</span></div>'
                 f'<div><b>{"–" if sd is None else f"{sd:.2f}"}</b><span>spread of gaps (SD), m/s</span></div></div>'
                 + (f'<p class="note">{html.escape(NOTES[pol.path.name])}</p>' if pol.path.name in NOTES else ""))
        sections.append(f"""
<section class="card">
  <h2>{html.escape(name)} <span class="muted">· {html.escape(", ".join(titles))} · polar: {html.escape(pol.status)}, {html.escape(pol.path.name)}</span></h2>
  {stats}
  {legend(items + [("curve", "manual polar")])}
  <div class="two">
    <figure><figcaption>Polar with measured legs</figcaption>{chart}</figure>
    <figure><figcaption>Gap per leg (measured − predicted)</figcaption>{gap_chart(legs, cats, pol)}</figure>
  </div>
</section>""")

    names = list(groups)
    summary = summary_chart(groups)
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{html.escape(g.run)}</td><td>{datetime.fromtimestamp(g.t0):%H:%M:%S}</td>"
        f"<td>{g.dur_s:.0f}</td><td>{g.ias_kmh:.0f}</td><td>{g.bank_deg:.0f}°</td><td>{g.weight_kg:.0f}</td>"
        f"<td>{g.air_w_ms:+.2f}</td><td>{g.te_ms:+.2f}</td><td>{g.sink_ms:.2f}</td>"
        f"<td>{'–' if g.pred_sink_ms is None else f'{g.pred_sink_ms:.2f}'}</td>"
        f"<td>{'–' if g.delta_ms is None else f'{g.delta_ms:+.2f}'}</td><td>{html.escape(category(g, d["polar"]))}</td></tr>"
        for name, d in groups.items() for g in d["legs"])
    page = (PAGE.replace("%%SECTIONS%%", "".join(sections))
            .replace("%%SUMMARY%%", summary)
            .replace("%%SUMMARY_LEGEND%%", legend([(f"c{i + 1}", n) for i, n in enumerate(names[:3])]))
            .replace("%%ROWS%%", rows)
            .replace("%%VERSION%%", __version__)
            .replace("%%GOOD%%", str(GOOD_MS)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path, groups


def main():
    cfg = load_config()
    polars = polar_mod.load_polars(cfg.data_dir / "polars")
    out, groups = build(cfg.reports_dir / "polars.html", cfg.data_dir / "baselines", polars)
    print(f"{out}  ({sum(len(d['legs']) for d in groups.values())} legs, {len(groups)} aircraft)")


NOTES = {
    "as33-18m_600kg_provisional.json":
        "Flap N is the right setting only up to about 120 km/h at 600 kg (flap range chart); the N leg at 210 km/h "
        "and the flap-6 legs at 150-180 km/h fly the wrong flap for their speed, so they sink more than the polar.",
    "dg1000-20m_table.json":
        "The DG-1001e beats the DG-1000S manual by a steady ~0.2 m/s with little scatter: a constant offset "
        "(likely the newer airframe and winglets), not a sign of lost lift.",
}


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Polars vs measured</title>
<style>
:root{
  color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --other:#898781;
  --band:rgba(42,120,214,.08);
}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){
  color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --other:#898781;
  --band:rgba(57,135,229,.12);
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --other:#898781;
  --band:rgba(57,135,229,.12);
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:0 0 10px}
.muted,.sub{color:var(--ink2);font-weight:400} .sub{margin:0 0 16px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:900px){.two{grid-template-columns:1fr}}
figure{margin:0} figcaption{color:var(--ink2);font-size:13px;margin-bottom:4px}
svg{width:100%;height:auto;display:block}
.grid{stroke:var(--grid);stroke-width:1} .axis{stroke:var(--axis);stroke-width:1}
.zero{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:5 4}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.alabel{fill:var(--ink2);font-size:12px}
.dlabel{fill:var(--ink2);font-size:11.5px}
.band{fill:var(--band)}
.curve{fill:none;stroke:var(--ink);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dot{stroke:var(--surface);stroke-width:2;transition:r .1s}
.c1{fill:var(--s1)} .c2{fill:var(--s2)} .c3{fill:var(--s3)} .cO{fill:var(--other)}
.hit{fill:transparent;cursor:pointer}
.pt:hover .dot{r:7}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--ink2);font-size:13px;margin:0 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:10px;height:10px;border-radius:50%}
.sw.c1{background:var(--s1)} .sw.c2{background:var(--s2)} .sw.c3{background:var(--s3)} .sw.cO{background:var(--other)}
.sw.curve{width:16px;height:2px;border-radius:1px;background:var(--ink)}
.stats{display:flex;flex-wrap:wrap;gap:8px 32px;margin:0 0 12px}
.stats div{display:flex;flex-direction:column} .stats b{font-size:20px;font-weight:600} .stats span{color:var(--ink2);font-size:12px}
#tip{position:fixed;z-index:10;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);
  box-shadow:0 4px 16px rgba(0,0,0,.18);border-radius:8px;padding:8px 10px;font-size:12px;white-space:pre-line;max-width:320px}
details summary{cursor:pointer;color:var(--ink2)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:12.5px;margin-top:8px}
th,td{padding:4px 6px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}
th:nth-child(-n+3),td:nth-child(-n+3),th:last-child,td:last-child{text-align:left}
th{color:var(--ink2);font-weight:500}
.tablewrap{overflow-x:auto}
.note{color:var(--ink2);font-size:12px}
</style>
</head>
<body>
<main>
  <h1>Polars vs measured</h1>
  <p class="sub">Every steady leg from every baseline run, against the manual polar. msfsdiag %%VERSION%% ·
    <a href="index.html" style="color:inherit">run reports</a></p>

  <section class="card">
    <h2>All aircraft: predicted vs measured sink</h2>
    %%SUMMARY_LEGEND%%
    <div class="two">
      <figure>%%SUMMARY%%</figure>
      <div class="note">
        <p>Each dot is one steady leg (≥15 s, bank ≤10°, IAS within ±10 km/h). <b>Measured sink</b> is the vertical air the sim
          reported minus the glider's total-energy climb rate: how fast the glider sinks relative to the air around it.
          <b>Predicted</b> is the manual polar at the leg's speed, mass, bank and altitude.</p>
        <p>On the dashed line the glider does exactly what its polar says. The shaded strip is ±%%GOOD%% m/s.
          Dots well above it sank more than the polar allows (e.g. a wrong flap setting); a glider ignoring lift would show the same.</p>
        <p>Polars: AS 33 points are provisional (read by eye from a "preliminary estimate" chart); the DG-1001e is compared with the
          DG-1000S manual table, a proxy airframe.</p>
      </div>
    </div>
  </section>

  %%SECTIONS%%

  <section class="card">
    <details><summary>All legs as a table</summary>
      <div class="tablewrap"><table>
        <thead><tr><th>aircraft</th><th>run</th><th>start</th><th>s</th><th>IAS</th><th>bank</th><th>kg</th>
          <th>air</th><th>climb</th><th>sink</th><th>pred</th><th>gap</th><th>flap</th></tr></thead>
        <tbody>%%ROWS%%</tbody>
      </table></div>
    </details>
  </section>
</main>
<div id="tip" hidden></div>
<script>
(function(){
  const tip = document.getElementById('tip');
  document.addEventListener('pointerover', e => {
    const t = e.target.closest('[data-tip]');
    if (!t) { tip.hidden = true; return; }
    tip.textContent = t.dataset.tip; tip.hidden = false;
  });
  document.addEventListener('pointermove', e => {
    if (tip.hidden) return;
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    const y = e.clientY + 14 + tip.offsetHeight > innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  });
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
