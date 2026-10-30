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
from pathlib import Path

from msfsdiag import __version__
from msfsdiag.analysis import polar, polar_report, report
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

INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>msfs-diagnostics examples</title>
<style>
:root{--bg:#f9f9f7;--card:#fcfcfb;--fg:#0b0b0b;--mute:#52514e;--line:rgba(11,11,11,.10);--link:#2457b3}
@media (prefers-color-scheme:dark){:root{--bg:#0d0d0d;--card:#1a1a19;--fg:#f0efec;--mute:#c3c2b7;--line:rgba(255,255,255,.10);--link:#8fb3f5}}
body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0}
main{max-width:860px;margin:0 auto;padding:32px 16px 48px}
h1{font-size:22px;margin:0 0 6px} p{color:var(--mute);margin:0 0 16px}
a{color:var(--link)} .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 12px}
.card h2{font-size:16px;margin:0 0 4px} .card p{margin:0}
</style></head><body><main>
<h1>msfs-diagnostics examples</h1>
<p>Glider telemetry from MSFS 2024 (store 1.9.21.0), recorded over SimConnect and compared with each glider's
published polar. Question: after SU7, do thermals and ridge lift still reach the glider? Answer from these runs: yes;
the problems traced to setup. Each page is self-contained: data and charts inside, works offline.
Built with msfsdiag %%VERSION%%.</p>
%%CARDS%%
</main></body></html>"""


def build(out_dir: Path):
    cfg = load_config()
    polars = polar.load_polars(cfg.data_dir / "polars")
    base = cfg.data_dir / "baselines" / BUILD
    out_dir.mkdir(parents=True, exist_ok=True)

    cards = []
    p, groups = polar_report.build(out_dir / "polars.html", cfg.data_dir / "baselines", polars)
    n = sum(len(d["legs"]) for d in groups.values())
    cards.append(("polars.html", "Polars vs measured",
                  f"All {n} steady legs from every run against the manual polars, per aircraft and combined. "
                  "Start here."))
    for run_rel, name, title, what in EXAMPLES:
        out, _, legs = report.build(base / (run_rel + ".jsonl"), out_dir / (name + ".html"), polars)
        cards.append((out.name, title, what))
        print(f"{out}  ({len(legs)} steady legs)")
    print(p)

    body = "\n".join(f'<div class="card"><h2><a href="{html.escape(f)}">{html.escape(t)}</a></h2>'
                     f"<p>{html.escape(w)}</p></div>" for f, t, w in cards)
    (out_dir / "index.html").write_text(INDEX.replace("%%CARDS%%", body).replace("%%VERSION%%", __version__),
                                        encoding="utf-8")
    print(out_dir / "index.html")


def screenshots(out_dir: Path):
    edge = next((Path(p) for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)
    edge = edge or (shutil.which("msedge") and Path(shutil.which("msedge")))
    if not edge:
        raise SystemExit("Microsoft Edge not found; skip --screenshots")
    img = out_dir / "img"
    img.mkdir(exist_ok=True)
    shots = [("polars.html", "polars.png", (1300, 1650)),
             ("dg1001e-ridge-and-thermals.html", "dg1001e-ridge-and-thermals.png", (1300, 1520)),
             ("as33me-ridge-flaps.html", "as33me-ridge-flaps.png", (1300, 900))]
    for page, png, (w, h) in shots:
        subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--blink-settings=preferredColorScheme=1", f"--window-size={w},{h}",
                        "--virtual-time-budget=3000", f"--screenshot={img / png}",
                        (out_dir / page).resolve().as_uri()], check=True, capture_output=True, timeout=120)
        print(img / png)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--screenshots", action="store_true")
    args = ap.parse_args()
    out = load_config().data_dir.parent / "examples"
    build(out)
    if args.screenshots:
        screenshots(out)
