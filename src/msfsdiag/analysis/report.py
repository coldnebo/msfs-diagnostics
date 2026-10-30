"""Build a self-contained HTML report for one recording.

The page embeds its data and the vendored uPlot library, so it opens from disk
with no server and no internet.

usage:
  python -m msfsdiag.analysis.report <run.jsonl> [...]   # reports next to reports/<build>/...
  python -m msfsdiag.analysis.report --all               # every run under data/baselines
"""

import argparse
import html
import json
from datetime import datetime, time as dtime
from pathlib import Path

from .. import __version__
from ..config import load as load_config
from . import legs as legs_mod
from . import polar as polar_mod
from . import run as run_mod

VENDOR = Path(__file__).with_name("vendor")


def _r(v, nd=3):
    return None if v is None else round(v, nd)


def _intervals(rows, key):
    """[t0, t1] spans where rows[key] is true."""
    out, start, last = [], None, None
    for r in rows:
        if r.get(key):
            start = r["t"] if start is None else start
            last = r["t"]
        elif start is not None:
            out.append([start, r["t"]])
            start = None
    if start is not None:
        out.append([start, last])
    return out


def _segments(meta, rows):
    """Meta 'segments' (local wall-clock HH:MM:SS) to unix-time spans."""
    if not rows or not meta.get("segments"):
        return []
    day = datetime.fromtimestamp(rows[0]["t"]).date()
    end_t = rows[-1]["t"]

    def ts(s):
        if s == "end":
            return end_t
        h, m, sec = (int(x) for x in s.split(":"))
        return datetime.combine(day, dtime(h, m, sec)).timestamp()

    return [{"t0": ts(s["from"]), "t1": ts(s["to"]), "weather": s.get("weather", ""), "what": s.get("what", "")}
            for s in meta["segments"]]


def payload(run, legs):
    rows = run.rows
    ok = [r["ok"] for r in rows]

    def series(key, only_ok=True, nd=3):
        return [_r(r.get(key), nd) if (r["ok"] or not only_ok) and isinstance(r.get(key), (int, float)) else None
                for r in rows]

    return {
        "name": run.path.stem,
        "tool_version": __version__,
        "meta": run.meta,
        "polars": run.polars_used,
        "t": [round(r["t"], 2) for r in rows],
        "ok": [1 if x else 0 for x in ok],
        "s": {
            "air_w": series("air_w_ms"),
            "te": series("te_ms"),
            "pred": series("pred_climb_ms"),
            "ias": series("ias_kmh", nd=1),
            "agl": series("agl_m", nd=0),
            "alt": series("alt_m", nd=0),
            "bank": series("bank_deg", nd=0),
            "lat": series("lat", only_ok=False, nd=5),
            "lon": series("lon", only_ok=False, nd=5),
        },
        "bands": {
            "paused": _intervals(rows, "paused"),
            "slew": _intervals(rows, "slew"),
            "frozen": _intervals(rows, "frozen"),
            "brakes": _intervals(rows, "brakes"),
        },
        "segments": _segments(run.meta, rows),
        "legs": [
            {"t0": g.t0, "t1": g.t1, "title": g.title, "dur": _r(g.dur_s, 0), "ias": _r(g.ias_kmh, 0),
             "bank": _r(g.bank_deg, 0), "air_w": _r(g.air_w_ms, 2), "te": _r(g.te_ms, 2), "sink": _r(g.sink_ms, 2),
             "pred": _r(g.pred_sink_ms, 2), "delta": _r(g.delta_ms, 2), "kg": _r(g.weight_kg, 0), "flap": g.flap}
            for g in legs
        ],
    }


def render(data) -> str:
    css = (VENDOR / "uPlot.min.css").read_text(encoding="utf-8")
    # uPlot is MIT: its notice travels with the copy embedded in every page
    lic = (VENDOR / "uPlot.LICENSE").read_text(encoding="utf-8").replace("*/", "* /")
    js = "/*\n" + lic + "*/\n" + (VENDOR / "uPlot.iife.min.js").read_text(encoding="utf-8")
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return (TEMPLATE
            .replace("%%TITLE%%", html.escape(data["name"]))
            .replace("%%UPLOT_CSS%%", css)
            .replace("%%UPLOT_JS%%", js)
            .replace("%%DATA%%", blob))


def build(run_path, out_path, polars):
    run = run_mod.load(run_path, polars)
    legs = legs_mod.find_legs(run.rows)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(payload(run, legs)), encoding="utf-8")
    return out_path, run, legs


def _out_for(run_path, cfg):
    p = Path(run_path).resolve()
    try:
        rel = p.relative_to((cfg.data_dir / "baselines").resolve())
        return cfg.reports_dir / rel.with_suffix(".html")
    except ValueError:
        return cfg.reports_dir / (p.stem + ".html")


def _write_index(reports_dir, built):
    items = "\n".join(
        f'<li><a href="{html.escape(str(p.relative_to(reports_dir)).replace(chr(92), "/"))}">'
        f"{html.escape(p.stem)}</a> <span>{html.escape(title)}</span></li>"
        for p, title in sorted(built))
    (reports_dir / "index.html").write_text(INDEX.replace("%%ITEMS%%", items), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*", help="recording .jsonl files")
    ap.add_argument("--all", action="store_true", help="every run under data/baselines")
    args = ap.parse_args(argv)

    cfg = load_config()
    polars = polar_mod.load_polars(cfg.data_dir / "polars")
    runs = [Path(p) for p in args.runs]
    if args.all:
        runs += sorted((cfg.data_dir / "baselines").rglob("*.jsonl"))
    if not runs:
        ap.error("give run files or --all")

    built = []
    for rp in runs:
        out, run, legs = build(rp, _out_for(rp, cfg), polars)
        titles = ", ".join(t for t in run.polars_used if t)
        built.append((out.resolve(), titles))
        print(f"{out}  ({len(run.rows)} samples, {len(legs)} steady legs)")
    if args.all:
        from . import polar_report
        out, groups = polar_report.build(cfg.reports_dir / "polars.html", cfg.data_dir / "baselines", polars)
        print(f"{out}  ({sum(len(d['legs']) for d in groups.values())} legs)")
        _write_index(cfg.reports_dir.resolve(), built)
        print(cfg.reports_dir / "index.html")


INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Run reports</title>
<style>:root{--bg:#fbfaf8;--fg:#1d1d1b;--mute:#6b6a66;--link:#2457b3}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe7;--mute:#9b9a95;--link:#8fb3f5}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:32px auto;padding:0 16px}
a{color:var(--link)}span{color:var(--mute);margin-left:8px}li{margin:6px 0}</style></head>
<body><h1>Run reports</h1>
<p><a href="polars.html">Polars vs measured</a> <span>every steady leg against the manual polars</span></p>
<ul>%%ITEMS%%</ul></body></html>"""


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%%</title>
<style>%%UPLOT_CSS%%</style>
<style>
:root{
  --bg:#fbfaf8; --panel:#ffffff; --fg:#1d1d1b; --mute:#6b6a66; --line:#e4e2dc;
  --air:#d0582a; --te:#2457b3; --pred:#1a8f5a; --ias:#2a8a6e; --agl:#8a5cc2;
  --band-pause:rgba(120,120,120,.16); --band-slew:rgba(200,150,0,.16); --band-frozen:rgba(120,120,120,.10);
  --band-brakes:rgba(194,59,42,.12);
  --seg-a:rgba(36,87,179,.05); --seg-b:rgba(36,87,179,.10);
  --good:#2a8a6e; --bad:#c23b2a;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#161615; --panel:#1f1f1d; --fg:#ecebe7; --mute:#9b9a95; --line:#34332f;
  --air:#f08a5d; --te:#8fb3f5; --pred:#7ee0a8; --ias:#5fc9a8; --agl:#bb95ef;
  --band-pause:rgba(200,200,200,.12); --band-slew:rgba(230,180,40,.14); --band-frozen:rgba(200,200,200,.07);
  --band-brakes:rgba(240,122,106,.14);
  --seg-a:rgba(143,179,245,.05); --seg-b:rgba(143,179,245,.10);
  --good:#5fc9a8; --bad:#f07a6a;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:0 0 8px}
.sub{color:var(--mute);margin:0 0 16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:14px}
.kv{display:flex;flex-wrap:wrap;gap:6px 22px} .kv div span{color:var(--mute);margin-right:6px}
.readout{display:flex;flex-wrap:wrap;gap:4px 18px;font-variant-numeric:tabular-nums;min-height:20px}
.readout b{font-weight:600} .readout .k{color:var(--mute)}
.grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);gap:14px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
#track{width:100%;aspect-ratio:1/1;display:block;border-radius:6px}
.legend-bar{height:8px;border-radius:4px;margin:8px 0 2px;background:linear-gradient(90deg,#2f6fd6,#9aa0a6 50%,#d64a2a)}
.legend-lbl{display:flex;justify-content:space-between;color:var(--mute);font-size:12px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px}
th,td{padding:5px 6px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--mute);font-weight:500}
tbody tr{cursor:pointer} tbody tr:hover{background:var(--seg-b)}
.good{color:var(--good)} .bad{color:var(--bad)}
.tablewrap{overflow-x:auto}
.note{color:var(--mute);font-size:12px;margin-top:8px}
button{font:inherit;color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
.u-legend{font-size:12px} .uplot{font-family:inherit}
.seglist{font-size:13px;margin:0;padding-left:18px} .seglist li{margin:2px 0;cursor:pointer}
</style>
</head>
<body>
<main>
  <h1 id="title"></h1>
  <p class="sub" id="subtitle"></p>

  <div class="card"><div class="kv" id="facts"></div></div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
      <h2>Lift vs climb</h2>
      <div><span class="note" style="margin-right:8px">drag to zoom</span><button id="reset">Reset zoom</button></div>
    </div>
    <div id="c1"></div>
    <div id="c2"></div>
    <div id="c3"></div>
    <div class="readout" id="readout"></div>
    <p class="note">Air = vertical air reported by the sim (AMBIENT WIND Y). Climb = the glider's total-energy climb rate.
      Predicted = air − polar sink (mass, bank and altitude corrected). Grey bands: paused or frozen; amber: slew; red: airbrakes.</p>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Track</h2>
      <canvas id="track"></canvas>
      <div class="legend-bar"></div>
      <div class="legend-lbl"><span>sink −3 m/s</span><span>0</span><span>lift +3 m/s</span></div>
    </div>
    <div class="card">
      <h2>Steady legs</h2>
      <div class="tablewrap"><table id="legs"></table></div>
      <p class="note">Sink = air − climb over the leg. Δ = measured − predicted: positive means the glider did worse than its polar.
        Click a row to zoom.</p>
      <h2 style="margin-top:14px">Segments</h2>
      <ol class="seglist" id="segs"></ol>
    </div>
  </div>
</main>

<script>%%UPLOT_JS%%</script>
<script type="application/json" id="data">%%DATA%%</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmtT = t => new Date(t*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const f = (v,d=2) => v==null ? '–' : v.toFixed(d);
const M = D.meta || {};

// header
document.title = D.name;
document.getElementById('title').textContent = D.name;
const titles = Object.keys(D.polars).filter(k => k && k !== 'null');
document.getElementById('subtitle').textContent =
  `${fmtT(D.t[0])} – ${fmtT(D.t[D.t.length-1])} · ${D.t.length} samples · ${titles.join(', ') || 'unknown aircraft'}`;
const sim = M.sim || {};
const facts = [
  ['sim', [sim.store_version && ('store ' + sim.store_version), sim.version].filter(Boolean).join(' / ') || '–'],
  ['polar', titles.map(t => D.polars[t] ? `${D.polars[t]}` : 'none').join(', ') || '–'],
  ['site', M.site || '–'], ['weather', M.weather || '–'], ['mass', M.mass_kg ? M.mass_kg + ' kg' : '–'],
  ['report', 'msfsdiag ' + D.tool_version],
];
if (M.note) facts.push(['note', M.note]);
document.getElementById('facts').innerHTML = facts.map(([k,v]) => `<div><span>${k}</span>${esc(v)}</div>`).join('');
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

// bands and segments drawn behind both charts
function bandsPlugin(){
  return {hooks:{drawClear: u => {
    const ctx = u.ctx, top = u.bbox.top, h = u.bbox.height;
    const x = v => u.valToPos(v, 'x', true);
    ctx.save();
    D.segments.forEach((s,i) => { ctx.fillStyle = i%2 ? css('--seg-b') : css('--seg-a');
      ctx.fillRect(x(s.t0), top, x(s.t1)-x(s.t0), h); });
    [['frozen','--band-frozen'],['paused','--band-pause'],['slew','--band-slew'],['brakes','--band-brakes']].forEach(([k,c]) => {
      ctx.fillStyle = css(c);
      D.bands[k].forEach(([a,b]) => ctx.fillRect(x(a), top, Math.max(1, x(b)-x(a)), h));
    });
    ctx.restore();
  }}};
}

const sync = uPlot.sync('run');
const base = (h) => ({
  width: document.getElementById('c1').clientWidth, height: h,
  cursor: {sync: {key: sync.key, setSeries: false}, drag: {x: true, y: false}},
  scales: {x: {time: true}}, plugins: [bandsPlugin()],
  axes: [{stroke: css('--mute'), grid: {stroke: css('--line')}, ticks: {stroke: css('--line')}},
         {stroke: css('--mute'), grid: {stroke: css('--line')}, ticks: {stroke: css('--line')}}],
});

const o1 = base(300);
o1.series = [{},
  {label: 'air m/s', stroke: css('--air'), width: 1.5, value: (u,v) => f(v)},
  {label: 'climb m/s', stroke: css('--te'), width: 1.5, value: (u,v) => f(v)},
  {label: 'predicted m/s', stroke: css('--pred'), width: 1.6, dash: [6,4], value: (u,v) => f(v)}];
o1.axes[1].label = 'm/s';
// robust y range: dives and airbrakes would otherwise squash the interesting ±5 m/s
o1.scales.y = {range: () => {
  const v = [...D.s.air_w, ...D.s.te, ...D.s.pred].filter(x => x != null).sort((a,b) => a-b);
  if (!v.length) return [-1, 1];
  const q = p => v[Math.min(v.length-1, Math.floor(p*v.length))];
  return [Math.min(-2, Math.floor(q(0.01)) - 1), Math.max(2, Math.ceil(q(0.99)) + 1)];
}};
let ready = false;  // charts can fire cursor hooks while still being built
o1.hooks = {setCursor: [u => ready && onCursor(u.cursor.idx)]};
const u1 = new uPlot(o1, [D.t, D.s.air_w, D.s.te, D.s.pred], document.getElementById('c1'));

// one measure per chart: airspeed and height get their own charts, same time axis
const o2 = base(130);
o2.series = [{}, {label: 'IAS km/h', stroke: css('--ias'), width: 1.2, value: (u,v) => f(v,0)}];
o2.axes[1].label = 'km/h';
const u2 = new uPlot(o2, [D.t, D.s.ias], document.getElementById('c2'));
const o3 = base(130);
o3.series = [{}, {label: 'height above ground m', stroke: css('--agl'), width: 1.2, value: (u,v) => f(v,0)}];
o3.axes[1].label = 'm AGL';
const u3 = new uPlot(o3, [D.t, D.s.agl], document.getElementById('c3'));
const charts = [u1, u2, u3];

function zoom(a, b){ charts.forEach(u => u.setScale('x', {min: a, max: b})); if (ready) drawTrack(); }
document.getElementById('reset').onclick = () => zoom(D.t[0], D.t[D.t.length-1]);
// keep both charts' zoom together
charts.forEach(u => u.over.addEventListener('mouseup', () => setTimeout(() => {
  const s = u.scales.x; charts.forEach(o => o !== u && o.setScale('x', {min: s.min, max: s.max})); drawTrack(); }, 0)));
window.addEventListener('resize', () => { const w = document.getElementById('c1').clientWidth;
  u1.setSize({width: w, height: 300}); u2.setSize({width: w, height: 130}); u3.setSize({width: w, height: 130}); sizeTrack(); });

// readout
const ro = document.getElementById('readout');
function onCursor(i){
  if (i == null) { ro.innerHTML = ''; drawTrack(); return; }
  const s = D.s;
  ro.innerHTML = [['time', fmtT(D.t[i])], ['air', f(s.air_w[i])], ['climb', f(s.te[i])], ['pred', f(s.pred[i])],
    ['IAS', f(s.ias[i],0)], ['AGL', f(s.agl[i],0)], ['bank', f(s.bank[i],0)], ['MSL', f(s.alt[i],0)]]
    .map(([k,v]) => `<span><span class="k">${k}</span> <b>${v}</b></span>`).join('');
  drawTrack(i);
}

// track
const cv = document.getElementById('track'), cx = cv.getContext('2d');
let proj = null;
function sizeTrack(){ const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  cv.width = r.width*dpr; cv.height = r.height*dpr; proj = null; drawTrack(); }
let projKey = '';
function project(){
  const la = D.s.lat, lo = D.s.lon, xs = u1.scales.x, idx = [];
  for (let i=0;i<D.t.length;i++)
    if (D.ok[i] && la[i]!=null && (xs.min == null || (D.t[i] >= xs.min && D.t[i] <= xs.max))) idx.push(i);
  if (!idx.length) return null;
  // one site at a time: the 0.2° cell with the most points in view, plus everything within 0.15° of it
  const cells = new Map();
  idx.forEach(i => { const c = Math.round(la[i]/0.2) + ':' + Math.round(lo[i]/0.2); cells.set(c, (cells.get(c)||0) + 1); });
  const bc = [...cells.entries()].sort((a,b) => b[1]-a[1])[0][0].split(':').map(Number);
  const mla = bc[0]*0.2, mlo = bc[1]*0.2;
  const near = idx.filter(i => Math.abs(la[i]-mla) < 0.35 && Math.abs(lo[i]-mlo) < 0.35);
  const k = Math.cos(mla*Math.PI/180);
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  near.forEach(i => { const x=lo[i]*k, y=la[i]; x0=Math.min(x0,x); x1=Math.max(x1,x); y0=Math.min(y0,y); y1=Math.max(y1,y); });
  const pad = 14*(window.devicePixelRatio||1), W = cv.width-2*pad, H = cv.height-2*pad;
  const sc = Math.min(W/Math.max(x1-x0,1e-6), H/Math.max(y1-y0,1e-6));
  const ox = pad + (W-(x1-x0)*sc)/2, oy = pad + (H-(y1-y0)*sc)/2;
  const set = new Set(near);
  return {set, xy: i => [ox + (lo[i]*k - x0)*sc, cv.height - (oy + (la[i]-y0)*sc)]};
}
function colorFor(w){
  const v = Math.max(-3, Math.min(3, w ?? 0))/3;
  const mix = (a,b,t) => a.map((x,j) => Math.round(x + (b[j]-x)*t));
  const c = v < 0 ? mix([154,160,166],[47,111,214],-v) : mix([154,160,166],[214,74,42],v);
  return `rgb(${c})`;
}
function drawTrack(cur){
  const key = u1.scales.x.min + ':' + u1.scales.x.max + ':' + cv.width;
  if (!proj || key !== projKey) { proj = project(); projKey = key; }
  cx.clearRect(0,0,cv.width,cv.height);
  if (!proj) return;
  const xs = u1.scales.x, dpr = window.devicePixelRatio||1;
  cx.lineWidth = 2.2*dpr; cx.lineCap = 'round';
  for (let i=1;i<D.t.length;i++){
    if (!proj.set.has(i) || !proj.set.has(i-1)) continue;
    const inView = xs.min == null || (D.t[i] >= xs.min && D.t[i] <= xs.max);
    const [a,b] = proj.xy(i-1), [c,d] = proj.xy(i);
    cx.globalAlpha = inView ? 1 : 0.15;
    cx.strokeStyle = colorFor(D.s.air_w[i]);
    cx.beginPath(); cx.moveTo(a,b); cx.lineTo(c,d); cx.stroke();
  }
  cx.globalAlpha = 1;
  if (cur != null && proj.set.has(cur)) {
    const [x,y] = proj.xy(cur);
    cx.fillStyle = css('--fg'); cx.beginPath(); cx.arc(x,y,5*dpr,0,7); cx.fill();
    cx.strokeStyle = css('--panel'); cx.lineWidth = 2*dpr; cx.stroke();
  }
}

// legs table
const tb = document.getElementById('legs');
const cls = d => d==null ? '' : (Math.abs(d) <= 0.15 ? 'good' : (d > 0.3 ? 'bad' : ''));
tb.innerHTML = '<thead><tr><th>start</th><th>s</th><th>IAS</th><th>bank</th><th>air</th><th>climb</th><th>sink</th><th>pred</th><th>Δ</th><th>flap</th></tr></thead><tbody>' +
  (D.legs.length ? D.legs.map((g,i) => `<tr data-i="${i}"><td>${fmtT(g.t0)}</td><td>${g.dur}</td><td>${g.ias}</td><td>${g.bank}°</td>
    <td>${f(g.air_w)}</td><td>${f(g.te)}</td><td>${f(g.sink)}</td><td>${f(g.pred)}</td>
    <td class="${cls(g.delta)}">${g.delta==null?'–':(g.delta>0?'+':'')+g.delta.toFixed(2)}</td><td>${esc(g.flap)}</td></tr>`).join('')
  : '<tr><td colspan="10">no steady legs</td></tr>') + '</tbody>';
tb.querySelectorAll('tbody tr[data-i]').forEach(tr => tr.onclick = () => {
  const g = D.legs[+tr.dataset.i], pad = Math.max(10, (g.t1-g.t0)*0.3); zoom(g.t0-pad, g.t1+pad); drawTrack(); });

// segments list
document.getElementById('segs').innerHTML = D.segments.length
  ? D.segments.map((s,i) => `<li data-i="${i}"><b>${fmtT(s.t0)}–${fmtT(s.t1)}</b> ${esc(s.weather)}${s.what ? ' · ' + esc(s.what) : ''}</li>`).join('')
  : '<li>no segment notes in the .meta.json</li>';
document.querySelectorAll('#segs li[data-i]').forEach(li => li.onclick = () => {
  const s = D.segments[+li.dataset.i]; zoom(s.t0, s.t1); drawTrack(); });

ready = true;
sizeTrack();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
