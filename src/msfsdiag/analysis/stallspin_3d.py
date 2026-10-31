"""3D view of stall/spin test points: the recorded path and an animated aircraft.

One page per aircraft run, with a test-point picker. The aircraft is flown along
the recorded path with its recorded pitch, bank and heading; play/pause, speed,
a time slider and a live readout. Orbit with the mouse; "follow" keeps the
camera on the aircraft.

Positions are local east/north/up metres from the point's first sample, at true
scale (a spin's path is a tight helix, so the attitude is the story). Uses
three.js r147 (MIT, vendored) so the page works offline.
"""

import html
import json
import math

from .. import __version__
from .report import VENDOR

HZ = 20


def _thin(samples, hz=HZ):
    out, last = [], None
    for x in samples:
        if last is None or x["t"] - last >= 1 / hz:
            out.append(x)
            last = x["t"]
    return out


def point_payload(pt):
    s = _thin(pt.samples)
    if not s:
        return None
    lat0, lon0, alt0 = s[0]["lat"], s[0]["lon"], s[0]["alt"]
    k = math.cos(math.radians(lat0))
    r = lambda v, nd=1: None if v is None else round(v, nd)
    rows = {"t": [], "e": [], "n": [], "u": [], "pitch": [], "bank": [], "hdg": [], "aoa": [], "rot": [], "ias": [],
            "alt": [], "vs": [], "g": [], "yoke": [], "ped": [], "ail": []}
    for x in s:
        if x["lat"] is None or x["lon"] is None or x["hdg"] is None:
            continue
        rows["t"].append(round(x["t"] - pt.t_start, 2))
        rows["e"].append(round((x["lon"] - lon0) * 111320.0 * k, 2))
        rows["n"].append(round((x["lat"] - lat0) * 110540.0, 2))
        rows["u"].append(round((x["alt"] - alt0) * 0.3048, 2))
        for key in ("pitch", "bank", "hdg", "aoa", "rot", "ias", "g"):
            rows[key].append(r(x[key]))
        rows["alt"].append(r(x["alt"], 0))
        rows["vs"].append(r(x["vs"], 0))
        for key in ("yoke", "ped", "ail"):
            rows[key].append(r(x[key], 2))
    m = pt.m
    summary = {k: m.get(k) for k in ("kind", "direction", "mode", "turns_total", "turns_after_first_input",
                                     "turns_after_opp_rudder", "stopped_by", "height_lost_ft")}
    if m.get("developed"):
        summary["s_per_turn"] = m["developed"]["s_per_turn"]
    return {"label": pt.label, "what": pt.what, "summary": summary, "data": rows}


def payload(meta, points):
    pts = [p for p in (point_payload(x) for x in points) if p]
    return {"aircraft": meta.get("aircraft_title"), "version": __version__, "points": pts}


def render(pl, back_href):
    js = ""
    for name, lic in (("three.min.js", "three.LICENSE"), ("three-OrbitControls.js", "three.LICENSE")):
        notice = (VENDOR / lic).read_text(encoding="utf-8").replace("*/", "* /")
        js += "/*\n" + notice + "*/\n" + (VENDOR / name).read_text(encoding="utf-8") + "\n"
    blob = json.dumps(pl, separators=(",", ":")).replace("</", "<\\/")
    return (PAGE.replace("%%TITLE%%", html.escape(pl["aircraft"] or "aircraft"))
            .replace("%%THREE%%", js).replace("%%DATA%%", blob).replace("%%BACK%%", html.escape(back_href)))


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%%TITLE%%: spins in 3D</title>
<style>
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
  --grid:#c3c2b7;--ring:rgba(11,11,11,.10);--sky:#e9eef3;--path:#a8a6a0;--trail:#2a78d6;--accent:#2a78d6}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
  --ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#46453f;--ring:rgba(255,255,255,.10);--sky:#141619;--path:#5f5e59;
  --trail:#3987e5;--accent:#3987e5}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
  --grid:#46453f;--ring:rgba(255,255,255,.10);--sky:#141619;--path:#5f5e59;--trail:#3987e5;--accent:#3987e5}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:18px 16px 36px}
h1{font-size:20px;margin:0 0 4px} .sub{color:var(--ink2);margin:0 0 12px} a{color:var(--accent)}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin:0 0 10px}
select,button{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--ring);border-radius:7px;padding:4px 10px}
button{cursor:pointer;min-width:74px} label{color:var(--ink2);display:inline-flex;align-items:center;gap:6px}
.stage{position:relative;background:var(--sky);border:1px solid var(--ring);border-radius:12px;overflow:hidden;
  height:min(68vh,640px);min-height:360px}
canvas{display:block;width:100%;height:100%;cursor:grab}
.hint{position:absolute;left:12px;bottom:10px;color:var(--muted);font-size:12px;pointer-events:none}
.scrub{display:flex;align-items:center;gap:10px;margin:10px 0 6px}
.scrub input{flex:1;accent-color:var(--accent)} .scrub output{font-variant-numeric:tabular-nums;min-width:64px;text-align:right}
.readout{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:6px 14px;
  background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:10px 14px}
.readout div{display:flex;flex-direction:column} .readout b{font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.readout span{color:var(--ink2);font-size:12px}
.what{color:var(--ink2);margin:10px 0 0;font-size:13px}
.note{color:var(--muted);font-size:12px;margin:10px 0 0}
</style></head><body><main>
<h1 id="title"></h1>
<p class="sub">Recorded path and attitude at true scale, 20 samples per second. <a href="%%BACK%%">Back to the charts</a></p>
<div class="bar">
  <select id="point" aria-label="test point"></select>
  <button id="play">Play</button>
  <label>speed <select id="speed"><option>0.25</option><option>0.5</option><option selected>1</option><option>2</option></select>×</label>
  <label><input type="checkbox" id="follow" checked> follow aircraft</label>
  <label>aircraft size <select id="scale"><option value="1">true</option><option value="2" selected>×2</option><option value="4">×4</option></select></label>
</div>
<div class="stage"><canvas id="c"></canvas><div class="hint">drag to orbit · scroll to zoom · right-drag to pan · grid arrow points north</div></div>
<div class="scrub"><input type="range" id="t" min="0" max="1" step="0.01" value="0" aria-label="time"><output id="tout">0.0 s</output></div>
<div class="readout" id="ro"></div>
<p class="what" id="what"></p>
<p class="note">Wingtips: red = left, green = right. Signs: pitch + nose up, bank + right wing down, rotation + clockwise seen
from above. In a flat spin the indicated airspeed is meaningless. three.js (MIT) · msfsdiag <span id="ver"></span></p>
</main>
<script>%%THREE%%</script>
<script type="application/json" id="data">%%DATA%%</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const $ = id => document.getElementById(id);
$('title').textContent = D.aircraft + ': spins in 3D'; document.title = $('title').textContent; $('ver').textContent = D.version;

// ---- scene
const canvas = $('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias: true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(css('--sky'));
const camera = new THREE.PerspectiveCamera(45, 1, 0.5, 20000);
const controls = new THREE.OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8478, 0.95));
const sun = new THREE.DirectionalLight(0xffffff, 0.7); sun.position.set(80, 200, 60); scene.add(sun);

// aircraft: nose along -z, right wing +x, up +y; ~11 m span
function makeAircraft(){
  const g = new THREE.Group(), body = new THREE.MeshLambertMaterial({color: 0xdedcd5}),
        wing = new THREE.MeshLambertMaterial({color: 0xf6f5f2}), dark = new THREE.MeshLambertMaterial({color: 0x5a6270});
  const box = (w, h, d, m, x, y, z) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); g.add(b); return b; };
  box(1.1, 1.3, 7.8, body, 0, 0, 0.2);                 // fuselage
  box(1.0, 0.7, 1.6, dark, 0, 0.6, -1.4);             // cabin glass
  box(11.0, 0.16, 1.6, wing, 0, 0.75, -0.8);          // wing
  box(3.6, 0.12, 1.0, wing, 0, 0.2, 3.7);             // stabiliser
  box(0.12, 1.7, 1.2, wing, 0, 1.05, 3.7);            // fin
  box(1.9, 0.12, 0.25, dark, 0, 0, -3.9);             // propeller
  const tip = (x, c) => { const s = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 8), new THREE.MeshBasicMaterial({color: c})); s.position.set(x, 0.75, -0.8); g.add(s); };
  tip(-5.55, 0xe34948); tip(5.55, 0x0ca30c);
  return g;
}
const aircraft = makeAircraft(); scene.add(aircraft);
let pathLine = null, trailLine = null, grid = null, north = null;

// ---- data
let P = null, Q = [], V = [], tMax = 1, t = 0, playing = false, lastFrame = null;
const sel = $('point');
D.points.forEach((p, i) => { const o = document.createElement('option'); o.value = i;
  o.textContent = `${p.label} · ${p.summary.kind || ''}${p.summary.direction ? ' ' + p.summary.direction : ''}${p.summary.mode ? ', ' + p.summary.mode : ''}`; sel.appendChild(o); });
const toRad = d => d * Math.PI / 180;

function load(i){
  P = D.points[i]; const d = P.data;
  V = d.t.map((_, k) => new THREE.Vector3(d.e[k], d.u[k], -d.n[k]));
  Q = d.t.map((_, k) => new THREE.Quaternion().setFromEuler(new THREE.Euler(toRad(d.pitch[k]), toRad(-d.hdg[k]), toRad(-d.bank[k]), 'YXZ')));
  tMax = d.t[d.t.length - 1]; t = d.t[0]; $('t').min = d.t[0]; $('t').max = tMax; $('t').value = t;
  [pathLine, trailLine, grid, north].forEach(o => o && scene.remove(o));
  const geo = new THREE.BufferGeometry().setFromPoints(V);
  pathLine = new THREE.Line(geo, new THREE.LineBasicMaterial({color: new THREE.Color(css('--path'))}));
  trailLine = new THREE.Line(geo.clone(), new THREE.LineBasicMaterial({color: new THREE.Color(css('--trail'))}));
  scene.add(pathLine, trailLine);
  const box = new THREE.Box3().setFromPoints(V), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
  const span = Math.max(80, size.x, size.z) * 1.6;
  grid = new THREE.GridHelper(span, 16, new THREE.Color(css('--grid')), new THREE.Color(css('--grid')));
  grid.position.set(c.x, box.min.y - 10, c.z); scene.add(grid);
  north = new THREE.ArrowHelper(new THREE.Vector3(0, 0, -1), new THREE.Vector3(c.x, box.min.y - 9.5, c.z), span * 0.35,
                                new THREE.Color(css('--accent')), span * 0.05, span * 0.025);
  scene.add(north);
  const p0 = V[0];
  controls.target.copy(p0); camera.position.set(p0.x + 45, p0.y + 25, p0.z + 55); controls.update();
  $('what').textContent = P.what;
  update(true);
}

function sampleAt(time){
  const d = P.data.t; let lo = 0, hi = d.length - 1;
  if (time <= d[0]) return [0, 0, 0]; if (time >= d[hi]) return [hi, hi, 0];
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (d[mid] <= time) lo = mid; else hi = mid; }
  return [lo, hi, (time - d[lo]) / (d[hi] - d[lo])];
}

const f = (v, nd=0) => v == null ? '–' : v.toFixed(nd);
function update(force){
  const [a, b, w] = sampleAt(t), d = P.data;
  const prev = aircraft.position.clone();
  aircraft.position.lerpVectors(V[a], V[b], w);
  aircraft.quaternion.slerpQuaternions(Q[a], Q[b], w);
  aircraft.scale.setScalar(+$('scale').value);
  trailLine.geometry.setDrawRange(0, a + 1);
  if ($('follow').checked && !force) { const dlt = aircraft.position.clone().sub(prev); controls.target.add(dlt); camera.position.add(dlt); }
  const k = w < 0.5 ? a : b;
  $('t').value = t; $('tout').textContent = t.toFixed(1) + ' s';
  const items = [['AoA', f(d.aoa[k], 1) + '°'], ['rotation', f(d.rot[k]) + '°/s'], ['pitch', f(d.pitch[k]) + '°'],
    ['bank', f(d.bank[k]) + '°'], ['heading', f(d.hdg[k]) + '°'], ['IAS', f(d.ias[k]) + ' kt'], ['altitude', f(d.alt[k]) + ' ft'],
    ['vertical speed', f(d.vs[k]) + ' fpm'], ['g', f(d.g[k], 2)], ['yoke (aft +)', f(d.yoke[k], 2)],
    ['pedals (right +)', f(d.ped[k], 2)], ['aileron (right +)', f(d.ail[k], 2)]];
  $('ro').innerHTML = items.map(([n, v]) => `<div><b>${v}</b><span>${n}</span></div>`).join('');
}

function resize(){ const r = canvas.getBoundingClientRect(); renderer.setSize(r.width, r.height, false);
  camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(canvas);

function frame(now){
  if (playing && lastFrame != null) {
    t += (now - lastFrame) / 1000 * +$('speed').value;
    if (t >= tMax) { t = tMax; playing = false; $('play').textContent = 'Play'; }
    update(false);
  }
  lastFrame = now; controls.update(); renderer.render(scene, camera); requestAnimationFrame(frame);
}

$('play').onclick = () => { if (t >= tMax) t = P.data.t[0]; playing = !playing; $('play').textContent = playing ? 'Pause' : 'Play'; };
$('t').oninput = e => { t = +e.target.value; update(false); };
$('scale').onchange = () => update(true);
sel.onchange = () => { playing = false; $('play').textContent = 'Play'; load(+sel.value); };
// start on the first spin, or on the point and time in the URL (#p=<index>&t=<seconds>), which is kept up to date
const h = new URLSearchParams(location.hash.slice(1));
const firstSpin = D.points.findIndex(p => p.summary.kind === 'spin');
sel.value = h.has('p') ? Math.min(D.points.length - 1, +h.get('p')) : Math.max(0, firstSpin);
load(+sel.value);
if (h.has('t')) { t = Math.min(tMax, Math.max(P.data.t[0], +h.get('t'))); update(true);
  controls.target.copy(aircraft.position); camera.position.copy(aircraft.position).add(new THREE.Vector3(45, 25, 55)); }
resize();
const keepHash = () => history.replaceState(null, '', `#p=${sel.value}&t=${t.toFixed(1)}`);
$('t').addEventListener('change', keepHash); $('play').addEventListener('click', keepHash); sel.addEventListener('change', keepHash);
requestAnimationFrame(frame);
})();
</script></body></html>"""
