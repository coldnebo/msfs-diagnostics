"""Build the showcase in examples/: selected run reports, the polars page, an index.

The pages are self-contained HTML (data and chart library inside), so they open
from disk or any static host. Screenshots for the README are taken separately:
  python scripts/build_examples.py --screenshots    (needs Microsoft Edge)

usage: python scripts/build_examples.py [--screenshots]
"""

import argparse
import html
import shutil
import subprocess
import time
from pathlib import Path

from msfsdiag import __version__
from msfsdiag.analysis import polar, polar_report, report
from msfsdiag.analysis import stallspin as ss
from msfsdiag.analysis import stallspin_report as ssr
from msfsdiag.config import load as load_config

BUILD = "msfs2024-12.2.282174.999"

# (baseline run, example file name, title, what it shows)
EXAMPLES = [
    ("asobo-dg1001e/runs/2026-10-30_run03_dg1001e_ridge-thermal", "dg1001e-ridge-and-thermals",
     "DG-1001e: ridge, cumulus and thermals",
     "One 40-minute session in five weather setups. Ridge lift, cumulus lift and default thermals: the climb line "
     "tracks the polar prediction throughout. Includes the pass where the thermal visualization vanished ~1 km "
     "before its apparent centre (pause markers), and a climb from 250 m to 900 m above ground."),
    ("gotfriends-as33me/runs/2026-10-30_ridge02_as33me", "as33me-ridge-flaps",
     "AS 33 Me: ridge lift and the flap lesson",
     "Bald Eagle Mountain, PA. The first two minutes fly 175 km/h with the flap lever at 6 (landing range): the "
     "glider climbs ~1 m/s less than predicted, which looked like 'lift not working'. After moving to flap N at "
     "~110 km/h, climb and prediction overlap."),
    ("asobo-dg1001e/runs/2026-10-30_andes01_dg1001e_spje-ridge", "dg1001e-andes-lee-side",
     "DG-1001e: Andes slope, west wind vs east wind",
     "Near SPJE, Peru. The same slope with the original west wind is the lee side: −0.4 to −1.4 m/s of sinking air. "
     "Switching the preset to an east wind turns it into ridge lift of +0.5 to +2.1 m/s. This explained the "
     "'no lift, very low' flights that started the investigation."),
    ("asobo-dg1001e/runs/2026-10-30_andes02_dg1001e_spje-india-time-live", "dg1001e-sim-time-vs-live-weather",
     "DG-1001e: sim clock, real clock and Live weather",
     "India at sim noon while it was 1 am there in real life: +4 m/s cumulus lift with a preset. Live weather "
     "(real night-time atmosphere) gave almost none, even with the sim clock at noon. Applying the preset again "
     "brought the lift back within a minute."),
]

REPO = "https://github.com/coldnebo/msfs-diagnostics"

# (path in the repo, title, what it covers). linked to GitHub, which renders markdown.
DOCS = [
    ("README.md", "Overview", "What the tools do, what we found, setup."),
    ("doc/GUIDE.md", "Guide", "Recording, markers, keeping runs, reading every report."),
    ("doc/TELEMETRY.md", "Telemetry format", "Every recorded field, units, sign conventions and quirks."),
    ("doc/TESTCARD-stall-spin.md", "Stall/spin test card", "The profile flown in every aircraft."),
    ("design/PLAN.md", "Glider investigation plan", "Hypotheses, decision tree, phases."),
    ("design/stall-spin/PLAN.md", "Stall/spin plan", "What we compare, phases, risks."),
    ("design/WORKLOG.md", "Worklog", "Findings and caveats, session by session."),
    ("data/README.md", "Data", "Manual sources, polar file format, baselines by sim build."),
    ("AGENTS.md", "For AI agents", "Commands, rules, live-session workflow, gotchas."),
]

SECTIONS = [
    ("gliders", "Gliders: is the lift reaching the glider?",
     "After SU7, thermals and ridge lift seemed to stop working. The sim's reported vertical air, the glider's "
     "total-energy climb and its published polar say otherwise: both gliders climbed as their polars predict, and "
     "the problems traced to setup (flap position, a lee-side wind) and a misleading visualization."),
    ("stall-spin", "Stalls and spins: three flight models, one test card",
     "The C172SP Classic, WBSim C152 and A2A Comanche 250 flown through the same stalls and spins at 60 Hz. "
     "The C172 spins steep and stops on forward yoke, the C152 drifts into a spiral, the Comanche spins fast and flat "
     "and needs opposite rudder."),
]

INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>msfs-diagnostics examples</title>
<style>
:root{color-scheme:light;--bg:#f9f9f7;--card:#fcfcfb;--fg:#0b0b0b;--mute:#52514e;--faint:#898781;
  --line:rgba(11,11,11,.10);--link:#2457b3;--shot:#eceae4}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--card:#1a1a19;
  --fg:#f0efec;--mute:#c3c2b7;--faint:#898781;--line:rgba(255,255,255,.10);--link:#8fb3f5;--shot:#26261f}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--card:#1a1a19;--fg:#f0efec;--mute:#c3c2b7;--faint:#898781;
  --line:rgba(255,255,255,.10);--link:#8fb3f5;--shot:#26261f}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0}
main{max-width:1160px;margin:0 auto;padding:36px 16px 56px}
a{color:var(--link)}
header h1{font-size:26px;margin:0 0 8px;letter-spacing:-.01em}
header p{color:var(--mute);margin:0 0 10px;max-width:760px}
.toplinks{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:14px;margin:4px 0 0}
section{margin:38px 0 0}
section h2{font-size:19px;margin:0 0 6px}
section > p{color:var(--mute);margin:0 0 16px;max-width:820px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:12px;
  overflow:hidden;text-decoration:none;color:inherit;transition:transform .12s ease,box-shadow .12s ease}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 22px rgba(0,0,0,.10)}
.card:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.shot{aspect-ratio:16/10;background:var(--shot);border-bottom:1px solid var(--line);overflow:hidden}
.shot img{width:100%;height:100%;object-fit:cover;object-position:top left;display:block}
.body{padding:12px 14px 14px}
.body h3{font-size:15px;margin:0 0 4px;color:var(--fg)}
.body p{font-size:13.5px;color:var(--mute);margin:0}
.card.lead{grid-column:span 2} .card.lead .shot{aspect-ratio:33/10}
@media (max-width:700px){.card.lead{grid-column:auto} .card.lead .shot{aspect-ratio:16/10}}
.docs{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.doc{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none}
.doc b{display:block;color:var(--link);font-weight:600;font-size:14.5px}
.doc span{display:block;color:var(--mute);font-size:13px}
.doc code{font-size:11.5px;color:var(--faint)}
footer{margin:44px 0 0;color:var(--faint);font-size:13px}
</style></head><body><main>
<header>
<h1>msfs-diagnostics</h1>
<p>Recording MSFS 2024 over SimConnect and comparing what the aircraft does with what it should do. Each page below is a
single self-contained file (data and charts inside) that also works offline.</p>
<div class="toplinks"><a href="%%REPO%%">Source on GitHub</a><a href="%%REPO%%/blob/main/README.md">README</a>
<a href="%%REPO%%/blob/main/doc/GUIDE.md">How to read the reports</a></div>
</header>
%%SECTIONS%%
<section id="docs"><h2>Documentation</h2><p>Markdown in the repository, rendered by GitHub.</p>
<div class="docs">%%DOCS%%</div></section>
<footer>Built with msfsdiag %%VERSION%% · MIT · charts by uPlot (MIT) · MSFS 2024 store 1.9.21.0 / SimConnect build 12.2.282174.999</footer>
</main></body></html>"""


def thumb_name(page):
    return "img/thumb/" + page.removesuffix(".html") + ".png"


def write_index(out_dir, cards):
    """cards: (section, href, title, description, lead?)."""
    parts = []
    for key, title, intro in SECTIONS:
        items = []
        for sec, href, t, desc, lead in cards:
            if sec != key:
                continue
            thumb = thumb_name(href)
            img = (f'<div class="shot"><img src="{thumb}" alt="" loading="lazy"></div>'
                   if (out_dir / thumb).exists() else "")
            items.append(f'<a class="card{" lead" if lead else ""}" href="{html.escape(href)}">{img}'
                         f'<div class="body"><h3>{html.escape(t)}</h3><p>{html.escape(desc)}</p></div></a>')
        parts.append(f'<section id="{key}"><h2>{html.escape(title)}</h2><p>{html.escape(intro)}</p>'
                     f'<div class="grid">{"".join(items)}</div></section>')
    docs = "".join(f'<a class="doc" href="{REPO}/blob/main/{path}"><b>{html.escape(t)}</b>'
                   f'<span>{html.escape(d)}</span><code>{html.escape(path)}</code></a>' for path, t, d in DOCS)
    page = (INDEX.replace("%%SECTIONS%%", "".join(parts)).replace("%%DOCS%%", docs)
            .replace("%%REPO%%", REPO).replace("%%VERSION%%", __version__))
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(out_dir / "index.html")


def build(out_dir: Path):
    cfg = load_config()
    polars = polar.load_polars(cfg.data_dir / "polars")
    base = cfg.data_dir / "baselines" / BUILD
    out_dir.mkdir(parents=True, exist_ok=True)

    cards = []
    p, groups = polar_report.build(out_dir / "polars.html", cfg.data_dir / "baselines", polars)
    n = sum(len(d["legs"]) for d in groups.values())
    cards.append(("gliders", "polars.html", "Polars vs measured",
                  f"All {n} steady legs from every run against the manual polars, per aircraft and combined. "
                  "Start here.", True))
    print(p)
    for run_rel, name, title, what in EXAMPLES:
        out, _, legs = report.build(base / (run_rel + ".jsonl"), out_dir / (name + ".html"), polars)
        cards.append(("gliders", out.name, title, what, False))
        print(f"{out}  ({len(legs)} steady legs)")

    cards += [("stall-spin", href, t, d, href == "stall-spin.html") for href, t, d in build_stallspin(cfg, out_dir)]
    write_index(out_dir, cards)
    return cards


def build_stallspin(cfg, out_dir):
    """Stall/spin comparison + one page per aircraft. Needs the local 60 Hz recordings
    (not in git); without them the existing stall/spin examples are kept."""
    runs = ssr.ordered_runs(cfg.data_dir / "baselines")
    if not runs:
        print("no stall-spin recordings found locally; keeping existing stall/spin examples")
        found = {f.name for f in out_dir.glob("stall-spin*.html")}
        return [(n, *STALLSPIN_CARDS[n]) for n in STALLSPIN_CARDS if n in found]
    built = []
    for run in runs:
        meta, points = ss.analyze(run)
        name = "stall-spin-" + run.parent.parent.name + ".html"
        pl = ssr.run_payload(run, meta, points)
        (out_dir / name).write_text(ssr.render_run(pl, back_href="stall-spin.html"), encoding="utf-8")
        built.append((meta.get("aircraft_title"), name, pl))
        print(out_dir / name)
    (out_dir / "stall-spin.html").write_text(ssr.compare_page(built), encoding="utf-8")
    print(out_dir / "stall-spin.html")
    return [("stall-spin.html", *STALLSPIN_CARDS["stall-spin.html"])] + \
        [(n, *STALLSPIN_CARDS.get(n, (a, ""))) for a, n, _ in built]


STALLSPIN_CARDS = {
    "stall-spin.html": ("Stalls and spins: C172, C152 and Comanche compared",
                        "Second project: the same stall/spin test card in three aircraft, recorded at 60 Hz. "
                        "Spin rate, height per turn, AoA in the spin, and what it takes to stop the rotation."),
    "stall-spin-asobo-c172sp-classic.html": (
        "C172SP Classic: stalls and spins",
        "Wings-level mush in the clean stall; a steep spin at 2.5-2.8 s per turn that stops as soon as the yoke goes "
        "forward."),
    "stall-spin-wbsim-c152.html": (
        "WBSim C152: stalls and spins",
        "A clean pitch break; clean spins drift into a spiral (AoA ~16°, airspeed and g climbing). One full-flap entry "
        "rolled against the rudder."),
    "stall-spin-a2a-pa24-250.html": (
        "A2A Comanche 250: stalls and spins",
        "Wing drops of up to 92° at the break; a fast, flat spin (~2 s per turn, AoA 44-53°) that keeps going with the yoke "
        "eased and stops only with opposite rudder."),
}


def _edge():
    edge = next((Path(p) for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)
    edge = edge or (shutil.which("msedge") and Path(shutil.which("msedge")))
    if not edge:
        raise SystemExit("Microsoft Edge not found; skip --screenshots")
    return edge


def _shot(edge, page, png, w, h, scale=1.0):
    png = Path(png)
    png.unlink(missing_ok=True)
    subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--blink-settings=preferredColorScheme=1", f"--window-size={w},{h}",
                    f"--force-device-scale-factor={scale}", "--virtual-time-budget=3000", f"--screenshot={png}",
                    page.resolve().as_uri()], check=True, capture_output=True, timeout=120)
    # msedge.exe can return before its browser process has written the file
    deadline = time.time() + 20
    while not (png.exists() and png.stat().st_size > 0) and time.time() < deadline:
        time.sleep(0.2)
    print(png if png.exists() else f"{png} NOT WRITTEN")


def screenshots(out_dir: Path, cards):
    edge = _edge()
    img = out_dir / "img"
    (img / "thumb").mkdir(parents=True, exist_ok=True)
    # full-size images used in the READMEs
    for page, png, (w, h) in [("polars.html", "polars.png", (1300, 1650)),
                              ("dg1001e-ridge-and-thermals.html", "dg1001e-ridge-and-thermals.png", (1300, 1520)),
                              ("as33me-ridge-flaps.html", "as33me-ridge-flaps.png", (1300, 900)),
                              ("stall-spin.html", "stall-spin.png", (1300, 1080)),
                              ("stall-spin-a2a-pa24-250.html", "stall-spin-a2a-pa24-250.png", (1300, 1700))]:
        if (out_dir / page).exists():
            _shot(edge, out_dir / page, img / png, w, h)
    # thumbnails for the index: the top of each page, 16:10, rendered at half scale
    for _, href, *_ in cards:
        _shot(edge, out_dir / href, out_dir / thumb_name(href), 1280, 800, scale=0.5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--screenshots", action="store_true")
    args = ap.parse_args()
    out = load_config().data_dir.parent / "examples"
    cards = build(out)
    if args.screenshots:
        screenshots(out, cards)
        write_index(out, cards)   # again, now that every thumbnail exists
