import json
import math

import pytest

from msfsdiag.analysis import legs, polar, report, run
from msfsdiag.config import REPO_ROOT


def write_polar(tmp_path, sets, **extra):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"aircraft": "Test", "match_titles": ["TEST"], "sets": sets, **extra}))
    return polar.load_polar(p)


def test_parabola_through_three_points_is_exact(tmp_path):
    # sink = 0.0001 v² − 0.02 v + 1.6  →  0.6 at 100
    pts = [{"ias_kmh": v, "sink_ms": 0.0001 * v * v - 0.02 * v + 1.6} for v in (80, 100, 150)]
    p = write_polar(tmp_path, [{"mass_kg": 500, "points": pts}])
    assert p.sink(120, 500) == pytest.approx(0.0001 * 120 ** 2 - 0.02 * 120 + 1.6, abs=1e-9)


def test_min_sink_point_is_the_vertex(tmp_path):
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 90, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 110, "sink_ms": 0.7}]}])
    assert p.sink(90, 600) == pytest.approx(0.6)
    assert p.sink(80, 600) > 0.6 and p.sink(100, 600) > 0.6
    assert p.sink(110, 600) == pytest.approx(0.7)


def test_mass_bank_and_altitude_corrections(tmp_path):
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 90, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 110, "sink_ms": 0.7}]}])
    # 4x mass: speeds and sinks scale by 2
    assert p.sink(180, 2400) == pytest.approx(1.2)
    # 60° bank: load factor 2, sink × 2^1.5
    assert p.sink(90, 600, bank_deg=60) == pytest.approx(0.6 * 2 ** 1.5)
    # TAS 10% above IAS: true sink 10% higher
    assert p.sink(90, 600, tas_kmh=99) == pytest.approx(0.66)


def test_valid_range(tmp_path):
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 90, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 110, "sink_ms": 0.7}]}], valid_ias_kmh=[70, 130])
    assert p.sink(140, 600) is None
    assert p.sink(120, 600) is not None


def test_repo_polars_load_and_match():
    ps = polar.load_polars(REPO_ROOT / "data" / "polars")
    assert polar.for_title(ps, "AS 33 Me (18m)").name.startswith("AS 33")
    assert polar.for_title(ps, "DG-1001-E Neo").name.startswith("DG-1000")
    dg = polar.for_title(ps, "DG-1001-E Neo")
    assert dg.sink(98, 736) == pytest.approx(0.62, abs=0.01)  # table value at 42 kg/m²


T0 = 1793385000.0  # a real date: local-time conversion of 1970 fails on Windows


def sample(t, alt, tas=100.0, air_w=0.0, bank=0.0, **kw):
    r = {"t": T0 + t, "lat": 40 + t * 1e-5, "lon": -77 + t * 1e-5, "alt_m": alt, "agl_m": 500.0, "ias_kmh": tas,
         "tas_kmh": tas, "vs_ms": 0.0, "air_w_ms": air_w, "bank_deg": bank, "weight_kg": 600.0,
         "title": "TEST", "paused": False}
    r.update(kw)
    return r


def write_run(tmp_path, rows, meta=None):
    p = tmp_path / "run.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    if meta:
        (tmp_path / "run.meta.json").write_text(json.dumps(meta))
    return p


def test_total_energy_counts_speed_as_height(tmp_path):
    # trade speed for height at constant energy: TE climb ≈ 0 though altitude rises
    rows, e = [], 1000 + (100 / 3.6) ** 2 / (2 * 9.81)
    for i in range(40):
        tas = 100 - i
        rows.append(sample(i * 0.5, e - (tas / 3.6) ** 2 / (2 * 9.81), tas=tas))
    r = run.load(write_run(tmp_path, rows))
    mid = [x["te_ms"] for x in r.rows[10:30]]
    assert all(abs(v) < 1e-6 for v in mid)


def test_paused_frozen_slew_and_brakes_are_excluded(tmp_path):
    rows = [sample(i * 0.5, 1000 - i * 0.3) for i in range(10)]
    rows[3]["paused"] = True
    rows[5] = dict(rows[4], t=rows[5]["t"])          # exact repeat → frozen
    rows[7]["ias_kmh"] = 0                            # slew
    rows[8]["spoilers"] = 100                         # airbrakes
    r = run.load(write_run(tmp_path, rows))
    assert [x["ok"] for x in r.rows][:8] == [True, True, True, False, True, False, True, False]
    assert r.rows[8]["ok"] and r.rows[8]["brakes"]


def test_steady_leg_measures_sink_against_air(tmp_path, monkeypatch):
    # air rises 1.5 m/s, glider climbs 0.9 m/s → sink 0.6
    rows = [sample(i * 0.5, 1000 + 0.9 * i * 0.5, air_w=1.5) for i in range(60)]
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 100, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 120, "sink_ms": 0.7}]}])
    r = run.load(write_run(tmp_path, rows), [p])
    (g,) = legs.find_legs(r.rows, min_s=15)
    assert g.sink_ms == pytest.approx(0.6, abs=1e-6)
    assert g.pred_sink_ms == pytest.approx(0.6, abs=1e-6)
    assert g.delta_ms == pytest.approx(0.0, abs=1e-6)


def test_report_html_is_self_contained(tmp_path):
    rows = [sample(i * 0.5, 1000 + 0.5 * i, air_w=1.0) for i in range(80)]
    meta = {"sim": {"version": "1.2.3"}, "segments": [{"from": "12:00:00", "to": "end", "weather": "W"}]}
    out, r, lg = report.build(write_run(tmp_path, rows, meta), tmp_path / "out.html", [])
    html = out.read_text(encoding="utf-8")
    assert "uPlot" in html and '"name":"run"' in html
    assert "<script src=" not in html and "<link" not in html  # nothing loaded from outside
    assert len(lg) == 1
