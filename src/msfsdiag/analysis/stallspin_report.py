"""Stall/spin reports: per-run pages, a cross-aircraft comparison, and results files.

For every stall-spin run under data/baselines:
- data/baselines/.../results/<run>.points.json   measurements per test point (committed)
- reports/.../<run>.html                           one card per point: summary + charts
- reports/stall-spin.html                          the aircraft side by side

Charts carry only the point windows, thinned to CHART_HZ, so pages are small even
though the recordings are 100+ MB. Self-contained and offline (vendored uPlot).

usage: python -m msfsdiag.analysis.stallspin_report
"""

import html
import json
import math
from pathlib import Path

from .. import __version__
from ..config import load as load_config
from . import stallspin as ss
from .report import VENDOR
from .run import find_runs, peek_title

CHART_HZ = 20


def stallspin_runs(baselines):
    return [p for p in find_runs(baselines) if "stall-spin" in p.name]


def aircraft_id(run_path):
    return Path(run_path).parent.parent.name


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def chart_data(pt):
    """Thinned series for one point, time in seconds from the segment start."""
    s, out, last = pt.samples, [], None
    for x in s:
        if last is None or x["t"] - last >= 1 / CHART_HZ:
            out.append(x)
            last = x["t"]
    t0 = pt.t_start
    keys = {"aoa": 1, "pitch": 1, "bank": 1, "rot": 1, "ias": 1, "alt": 0, "g": 2, "yoke": 2, "ped": 2, "ail": 2}
    data = {"t": [round(x["t"] - t0, 2) for x in out]}
    for k, nd in keys.items():
        data[k] = [_r(x[k], nd) for x in out]
    data["events"] = {k: round(s[i]["t"] - t0, 2) for k, i in pt.events.items() if i is not None}
    return data


def run_payload(run_path, meta, points):
    return {
        "name": Path(run_path).name.removesuffix(".gz").removesuffix(".jsonl"),
        "aircraft": meta.get("aircraft_title"),
        "meta": {k: meta.get(k) for k in ("site", "weather", "sim", "notes", "mass_lb", "test_card")},
        "version": __version__,
        "points": [{"label": p.label, "point": p.point, "what": p.what, "m": p.m, "chart": chart_data(p)} for p in points],
    }


def render_run(payload, back_href="../../../stall-spin.html"):
    css = (VENDOR / "uPlot.min.css").read_text(encoding="utf-8")
    lic = (VENDOR / "uPlot.LICENSE").read_text(encoding="utf-8").replace("*/", "* /")
    js = "/*\n" + lic + "*/\n" + (VENDOR / "uPlot.iife.min.js").read_text(encoding="utf-8")
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return (RUN_PAGE.replace("%%TITLE%%", html.escape(payload["aircraft"] or payload["name"]))
            .replace("%%UPLOT_CSS%%", css).replace("%%UPLOT_JS%%", js).replace("%%DATA%%", blob)
            .replace("%%BACK%%", html.escape(back_href)))


# ---------- comparison page (inline SVG dot plots)

W, H_ROW, ML, MR, MT, MB = 640, 34, 190, 24, 10, 40


def nice_ticks(lo, hi, n=5):
    span = max(hi - lo, 1e-9)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t, out = math.ceil(lo / step) * step, []
    while t <= hi + step * 1e-6:
        out.append(round(t, 10))
        t += step
    return out


def dot_plot(rows, cats, xlabel, label):
    """rows: (category index, value, tooltip). one row per category, dots along x."""
    vals = [v for _, v, _ in rows if v is not None]
    if not vals:
        return '<p class="note">no data</p>'
    lo, hi = min(0, min(vals)), max(vals) * 1.1 or 1
    h = MT + MB + H_ROW * len(cats)
    x = lambda v: ML + (v - lo) / (hi - lo) * (W - ML - MR)
    y = lambda c: MT + H_ROW * c + H_ROW / 2
    out = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{html.escape(label)}">']
    for t in nice_ticks(lo, hi):
        out.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{MT}" y2="{h - MB}"/>'
                   f'<text class="tick" x="{x(t):.1f}" y="{h - MB + 16}" text-anchor="middle">{t:g}</text>')
    for i, c in enumerate(cats):
        out.append(f'<text class="cat" x="{ML - 10}" y="{y(i) + 4:.1f}" text-anchor="end">{html.escape(c)}</text>'
                   f'<line class="axis" x1="{ML}" x2="{W - MR}" y1="{y(i):.1f}" y2="{y(i):.1f}"/>')
    for c, v, tip in rows:
        if v is None:
            continue
        out.append(f'<g class="pt" data-tip="{html.escape(tip)}"><circle class="dot c{c + 1}" cx="{x(v):.1f}" '
                   f'cy="{y(c):.1f}" r="6"/><circle class="hit" cx="{x(v):.1f}" cy="{y(c):.1f}" r="12"/></g>')
    out.append(f'<text class="alabel" x="{(ML + W - MR) / 2:.0f}" y="{h - 6}" text-anchor="middle">{html.escape(xlabel)}</text></svg>')
    return "".join(out)


def tip(acft, p, extra=""):
    m = p["m"]
    return (f"{acft} · {p['label']} ({m.get('kind')}{' ' + m['direction'] if m.get('direction') else ''})\n"
            f"{p['what']}\n{extra}").strip()


def compare_page(runs):
    """runs: list of (aircraft title, report href, payload)."""
    cats = [a for a, _, _ in runs]
    charts = []

    def collect(fn):
        rows = []
        for ci, (acft, _, pl) in enumerate(runs):
            for p in pl["points"]:
                r = fn(p["m"])
                if r is not None:
                    v, extra = r
                    rows.append((ci, v, tip(acft, p, extra)))
        return rows

    dev = lambda k: (lambda m: (m["developed"][k], f"{k.replace('_', ' ')}: {m['developed'][k]}")
                     if m.get("developed") else None)
    charts.append(("Spin rate, developed (seconds per turn)", "s per turn: lower = faster", collect(dev("s_per_turn"))))
    charts.append(("Height lost per turn, developed", "ft per turn", collect(dev("ft_per_turn"))))
    charts.append(("Angle of attack in the developed spin (mean)", "deg: higher = flatter",
                   collect(lambda m: (m["developed"]["aoa_deg"][1], f"AoA min/mean/max {m['developed']['aoa_deg']}, "
                                      f"mode {m.get('mode')}") if m.get("developed") else None)))
    charts.append(("Turns after the first recovery input", "turns until rotation stopped",
                   collect(lambda m: (m["turns_after_first_input"], f"stopped by {m.get('stopped_by')}; "
                                      f"after opposite rudder: {m.get('turns_after_opp_rudder', '–')}")
                           if m.get("turns_after_first_input") is not None else None)))
    charts.append(("Stall warning, flaps up", "IAS kt",
                   collect(lambda m: (m["warn_ias_kt"], f"AoA {m.get('warn_aoa_deg')}°")
                           if m.get("warn_ias_kt") and not m.get("flaps_deg") else None)))
    charts.append(("Stall warning, flaps down", "IAS kt",
                   collect(lambda m: (m["warn_ias_kt"], f"flaps {m.get('flaps_deg')}°, AoA {m.get('warn_aoa_deg')}°")
                           if m.get("warn_ias_kt") and m.get("flaps_deg") else None)))
    charts.append(("Wing drop at the break (stalls without pro-spin rudder)", "max bank, deg",
                   collect(lambda m: (m["wing_drop_deg"], f"roll rate {m.get('max_roll_rate_dps')}°/s, "
                                      f"pitch break {m.get('pitch_break_deg')}°")
                           if m.get("wing_drop_deg") is not None and not m.get("pro_rudder_before_departure")
                           and m.get("kind") != "spin" else None)))
    legend = "".join(f'<span><i class="sw c{i + 1}"></i>{html.escape(a)}</span>' for i, a in enumerate(cats))
    links = " · ".join(f'<a href="{html.escape(href)}">{html.escape(a)}</a>' for a, href, _ in runs)
    body = "".join(f'<section class="card"><h2>{html.escape(t)}</h2>{dot_plot(rows, cats, xl, t)}</section>'
                   for t, xl, rows in charts)
    table = []
    for acft, _, pl in runs:
        for p in pl["points"]:
            m, d = p["m"], p["m"].get("developed") or {}
            table.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in (
                acft, p["label"], m.get("kind"), m.get("direction", ""), m.get("warn_ias_kt", ""), m.get("flaps_deg", ""),
                m.get("peak_aoa_deg", ""), m.get("wing_drop_deg", ""), m.get("turns_total", ""),
                d.get("s_per_turn", ""), d.get("ft_per_turn", ""), (d.get("aoa_deg") or ["", "", ""])[1], m.get("mode", ""),
                m.get("turns_after_first_input", ""), m.get("turns_after_opp_rudder", ""), m.get("stopped_by", ""),
                m.get("height_lost_ft", ""), m.get("max_g", ""), m.get("max_ias_kt", ""))) + "</tr>")
    return (COMPARE_PAGE.replace("%%LEGEND%%", legend).replace("%%LINKS%%", links).replace("%%CHARTS%%", body)
            .replace("%%ROWS%%", "".join(table)).replace("%%VERSION%%", __version__))


def ordered_runs(base):
    """Stall-spin runs in the order flown (first test point time), not alphabetically."""
    def first_time(run):
        meta = json.loads(ss.meta_path(run).read_text(encoding="utf-8"))
        return (meta.get("split_from", ""), min((g["from"] for g in meta.get("segments", [])), default=""))
    return sorted(stallspin_runs(base), key=first_time)


def main():
    cfg = load_config()
    base = cfg.data_dir / "baselines"
    built = []
    for run in ordered_runs(base):
        meta, points = ss.analyze(run)
        res_dir = run.parent.parent / "results"
        res_dir.mkdir(exist_ok=True)
        name = run.name.removesuffix(".gz").removesuffix(".jsonl")
        (res_dir / f"{name}.points.json").write_text(json.dumps(ss.results(run, meta, points), indent=1),
                                                    encoding="utf-8")
        pl = run_payload(run, meta, points)
        out = cfg.reports_dir / run.parent.relative_to(base) / f"{name}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_run(pl), encoding="utf-8")
        built.append((meta.get("aircraft_title") or peek_title(run), out, pl))
        print(f"{out}  ({len(points)} points, {out.stat().st_size // 1024} KB)")
    page = cfg.reports_dir / "stall-spin.html"
    runs = [(a, str(o.relative_to(cfg.reports_dir)).replace("\\", "/"), pl) for a, o, pl in built]
    page.write_text(compare_page(runs), encoding="utf-8")
    print(page)


STYLE = """
:root{color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --ev:#898781; --band:rgba(42,120,214,.07);}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --ev:#898781; --band:rgba(57,135,229,.10);}}
:root[data-theme="dark"]{color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --ev:#898781; --band:rgba(57,135,229,.10);}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:0 0 8px} h3{font-size:13px;margin:0 0 2px;color:var(--ink2);font-weight:500}
.sub{color:var(--ink2);margin:0 0 16px} .note{color:var(--ink2);font-size:12px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;margin-bottom:14px}
a{color:var(--s1)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:12.5px}
th,td{padding:4px 6px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{color:var(--ink2);font-weight:500}
.tablewrap{overflow-x:auto}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--ink2);font-size:13px;margin:0 0 10px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:10px;height:10px;border-radius:50%}
.sw.c1{background:var(--s1)} .sw.c2{background:var(--s2)} .sw.c3{background:var(--s3)}
.sw.line{width:16px;height:2px;border-radius:1px}
"""

RUN_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%%TITLE%%: stalls and spins</title>
<style>%%UPLOT_CSS%%</style><style>""" + STYLE + r"""
.kv{display:flex;flex-wrap:wrap;gap:4px 22px;font-size:13px} .kv span{color:var(--ink2);margin-right:6px}
.stats{display:flex;flex-wrap:wrap;gap:6px 26px;margin:6px 0 10px}
.stats div{display:flex;flex-direction:column} .stats b{font-size:18px;font-weight:600} .stats span{color:var(--ink2);font-size:12px}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px}
@media (max-width:900px){.charts{grid-template-columns:1fr}}
.pill{display:inline-block;font-size:12px;border:1px solid var(--ring);border-radius:999px;padding:1px 8px;margin-left:6px;color:var(--ink2)}
.u-legend{font-size:11.5px}
</style></head><body><main>
<h1 id="title"></h1><p class="sub" id="sub"></p>
<div class="card"><div class="kv" id="facts"></div>
<p class="note">Signs: pitch + nose up, bank + right wing down, rotation + clockwise seen from above (right). Rotation is about the
vertical axis (body rates projected), which counts spin turns correctly near vertical. In a flat spin the indicated
airspeed is meaningless. Vertical lines mark detected events: W warning, A yoke full aft, P peak AoA, D departure,
R pro-spin rudder, Y yoke forward, O opposite rudder, S rotation stopped, L level.</p></div>
<div id="points"></div>
<p class="note"><a href="%%BACK%%">All aircraft compared</a></p>
</main>
<script>%%UPLOT_JS%%</script>
<script type="application/json" id="data">%%DATA%%</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f = (v, d=1) => v == null ? '–' : (typeof v === 'number' ? v.toFixed(d) : v);
document.title = D.aircraft + ': stalls and spins';
document.getElementById('title').textContent = D.aircraft + ': stalls and spins';
document.getElementById('sub').textContent = `${D.name} · ${D.points.length} test points · msfsdiag ${D.version}`;
const M = D.meta, sim = M.sim || {};
document.getElementById('facts').innerHTML = [['site', M.site], ['weather', M.weather], ['mass', M.mass_lb ? M.mass_lb + ' lb' : ''],
  ['sim', [sim.store_version, sim.version].filter(Boolean).join(' / ')], ['notes', M.notes]]
  .filter(([,v]) => v).map(([k,v]) => `<div><span>${k}</span>${esc(v)}</div>`).join('');
const EV = {warning:'W', full_aft:'A', peak_aoa:'P', departure:'D', pro_rudder:'R', yoke_fwd:'Y', opp_rudder:'O', stop:'S', level:'L'};
function events(ev){ return {hooks:{draw:[u => {
  const ctx = u.ctx; ctx.save(); ctx.strokeStyle = css('--ev'); ctx.fillStyle = css('--ink2');
  ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.font = `${11*devicePixelRatio}px system-ui`;
  for (const [k, t] of Object.entries(ev)) { const x = u.valToPos(t, 'x', true);
    if (x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue;
    ctx.beginPath(); ctx.moveTo(x, u.bbox.top); ctx.lineTo(x, u.bbox.top + u.bbox.height); ctx.stroke();
    ctx.fillText(EV[k] || k, x + 3*devicePixelRatio, u.bbox.top + 11*devicePixelRatio); }
  ctx.restore(); }]}}; }
const charts = [];
function chart(el, title, c, series, key){
  const box = document.createElement('div'); box.innerHTML = `<h3>${title}</h3>`; el.appendChild(box);
  const opts = {width: Math.max(280, box.clientWidth), height: 150, cursor: {sync: {key}}, scales: {x: {time: false}},
    legend: {show: series.length > 1}, plugins: [events(c.events)],
    axes: [{stroke: css('--muted'), grid: {stroke: css('--grid')}, ticks: {stroke: css('--grid')}, values: (u, v) => v.map(x => x + ' s')},
           {stroke: css('--muted'), grid: {stroke: css('--grid')}, ticks: {stroke: css('--grid')}, size: 46}],
    series: [{}, ...series.map(([k, lab, col]) => ({label: lab, stroke: css(col), width: 1.6, value: (u, v) => f(v)}))]};
  const u = new uPlot(opts, [c.t, ...series.map(([k]) => c[k])], box); charts.push([u, box]);
}
const host = document.getElementById('points');
D.points.forEach((p, i) => {
  const m = p.m, d = m.developed || {};
  const card = document.createElement('section'); card.className = 'card';
  const kind = `${m.kind || ''}${m.direction ? ' ' + m.direction : ''}${m.mode ? ', ' + m.mode : ''}`;
  const stats = [
    ['warning', m.warn_ias_kt != null ? `${f(m.warn_ias_kt)} kt / ${f(m.warn_aoa_deg)}°` : '–'],
    ['flaps', m.flaps_deg != null ? m.flaps_deg + '°' : '–'],
    ['peak AoA', f(m.peak_aoa_deg) + '°'], ['wing drop', f(m.wing_drop_deg) + '°'],
    ['turns', f(m.turns_total, 2)],
    ['developed', d.s_per_turn ? `${f(d.s_per_turn, 1)} s · ${d.ft_per_turn} ft / turn` : '–'],
    ['AoA in spin', d.aoa_deg ? `${d.aoa_deg[0]}–${d.aoa_deg[2]}° (mean ${d.aoa_deg[1]})` : '–'],
    ['turns after 1st input', f(m.turns_after_first_input, 2)], ['after opposite rudder', f(m.turns_after_opp_rudder, 2)],
    ['stopped by', m.stopped_by || '–'], ['height lost', m.height_lost_ft != null ? m.height_lost_ft + ' ft' : '–'],
    ['max g / IAS', `${f(m.max_g, 1)} / ${m.max_ias_kt ?? '–'} kt`]];
  card.innerHTML = `<h2>${esc(p.label)}<span class="pill">${esc(kind)}</span></h2><p class="note">${esc(p.what)}</p>
    <div class="stats">${stats.map(([k, v]) => `<div><b>${esc(v)}</b><span>${k}</span></div>`).join('')}</div>`;
  const grid = document.createElement('div'); grid.className = 'charts'; card.appendChild(grid); host.appendChild(card);
  const c = p.chart, key = 'p' + i;
  chart(grid, 'Angle of attack and pitch (deg)', c, [['aoa', 'AoA', '--s1'], ['pitch', 'pitch (nose up +)', '--s2']], key);
  chart(grid, 'Rotation about the vertical (deg/s, right +)', c, [['rot', 'rotation', '--s1']], key);
  chart(grid, 'Indicated airspeed (kt)', c, [['ias', 'IAS', '--s1']], key);
  chart(grid, 'Altitude (ft)', c, [['alt', 'altitude', '--s1']], key);
  chart(grid, 'Bank (deg, right +)', c, [['bank', 'bank', '--s1']], key);
  chart(grid, 'Controls (−1 … +1): yoke aft +, pedals right +, aileron right +', c,
        [['yoke', 'yoke', '--s1'], ['ped', 'pedals', '--s2'], ['ail', 'aileron', '--s3']], key);
});
addEventListener('resize', () => charts.forEach(([u, b]) => u.setSize({width: Math.max(280, b.clientWidth), height: 150})));
})();
</script></body></html>"""

COMPARE_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Stalls and spins compared</title>
<style>""" + STYLE + r"""
.grid{stroke:var(--grid);stroke-width:1} .axis{stroke:var(--axis);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums} .cat{fill:var(--ink);font-size:12.5px}
.alabel{fill:var(--ink2);font-size:12px}
svg{width:100%;height:auto;display:block}
.dot{stroke:var(--surface);stroke-width:2} .c1{fill:var(--s1)} .c2{fill:var(--s2)} .c3{fill:var(--s3)}
.hit{fill:transparent;cursor:pointer} .pt:hover .dot{r:8}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0 14px} @media (max-width:900px){.cols{grid-template-columns:1fr}}
#tip{position:fixed;z-index:10;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);
  box-shadow:0 4px 16px rgba(0,0,0,.18);border-radius:8px;padding:8px 10px;font-size:12px;white-space:pre-line;max-width:340px}
</style></head><body><main>
<h1>Stalls and spins compared</h1>
<p class="sub">MSFS 2024 flight models, same test card (doc/TESTCARD-stall-spin.md). One dot per test point; hover for details.
Measurements of the sim, not verdicts on the real aircraft. msfsdiag %%VERSION%%</p>
<div class="card"><div class="legend">%%LEGEND%%</div><p class="note">Per-aircraft pages with charts for every point: %%LINKS%%</p></div>
<div class="cols">%%CHARTS%%</div>
<section class="card"><details><summary>All points as a table</summary><div class="tablewrap"><table>
<thead><tr><th>aircraft</th><th>point</th><th>kind</th><th>dir</th><th>warn kt</th><th>flaps °</th><th>peak AoA</th>
<th>wing drop</th><th>turns</th><th>s/turn</th><th>ft/turn</th><th>spin AoA</th><th>mode</th><th>turns after 1st input</th>
<th>after opp rudder</th><th>stopped by</th><th>height lost</th><th>max g</th><th>max IAS</th></tr></thead>
<tbody>%%ROWS%%</tbody></table></div></details></section>
</main><div id="tip" hidden></div>
<script>
(function(){ const tip = document.getElementById('tip');
  document.addEventListener('pointerover', e => { const t = e.target.closest('[data-tip]');
    if (!t) { tip.hidden = true; return; } tip.textContent = t.dataset.tip; tip.hidden = false; });
  document.addEventListener('pointermove', e => { if (tip.hidden) return;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
    tip.style.top = (e.clientY + 14 + tip.offsetHeight > innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 14) + 'px'; });
})();
</script></body></html>"""


if __name__ == "__main__":
    main()
