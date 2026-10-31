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


def test_to_reference_undoes_sink_corrections(tmp_path):
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 90, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 110, "sink_ms": 0.7}]}])
    s = p.sink(150, 700, bank_deg=30, tas_kmh=165)
    v_ref, s_ref = polar.to_reference(p.sets[0], 150, s, 700, bank_deg=30, tas_kmh=165)
    assert s_ref == pytest.approx(p.sets[0].sink(v_ref))


def test_polar_page_builds(tmp_path):
    from msfsdiag.analysis import polar_report
    runs = tmp_path / "baselines" / "x"
    runs.mkdir(parents=True)
    rows = [sample(i * 0.5, 1000 + 0.9 * i * 0.5, air_w=1.5, ias_kmh=100) for i in range(60)]
    write_run(runs, rows, {"note": "flaps were at index 6 throughout"})
    p = write_polar(tmp_path, [{"mass_kg": 600, "min_sink": {"ias_kmh": 100, "sink_ms": 0.6},
                                "points": [{"ias_kmh": 120, "sink_ms": 0.7}]}])
    out, groups = polar_report.build(tmp_path / "polars.html", tmp_path / "baselines", [p])
    (leg,) = groups["Test"]["legs"]
    assert polar_report.category(leg, p) == "flap index 6 (pilot note)"
    page = out.read_text(encoding="utf-8")
    assert "<svg" in page and "1 / 1" in page


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


def spin_rows(turn_dps=120.0, spin_s=6.0, rec_s=1.0, hz=60):
    """Synthetic right spin: wings level, nose level (so rotation = yaw rate), then recovery."""
    rows, t = [], T0
    for i in range(int(hz * 2)):                          # 2 s of stalled entry, warning on
        rows.append(dict(t=t, ias_kt=45.0, aoa_deg=12 + i / hz * 4, pitch_deg=0.0, bank_deg=0.0, p_dps=0.0, q_dps=0.0,
                         r_dps=0.0, alt_ft=5000 - i * 0.5, vs_fpm=-500.0, g=1.0, yoke_y=0.8, pedals=0.0,
                         stall_warn=1, stall_aoa_deg=14.0, lat=40 + i * 1e-6, lon=-77.0, paused=False, on_ground=0))
        t += 1 / hz
    for i in range(int(hz * spin_s)):                     # spin: full right rudder, full aft
        rows.append(dict(rows[-1], t=t, aoa_deg=30.0, r_dps=turn_dps, yoke_y=1.0, pedals=1.0,
                         alt_ft=rows[-1]["alt_ft"] - 1.5, lat=rows[-1]["lat"] + 1e-6, vs_fpm=-5000.0))
        t += 1 / hz
    for i in range(int(hz * rec_s)):                      # recovery: opposite rudder + yoke forward, decay
        f = 1 - i / (hz * rec_s)
        rows.append(dict(rows[-1], t=t, aoa_deg=8.0, r_dps=turn_dps * f, yoke_y=0.1, pedals=-1.0,
                         alt_ft=rows[-1]["alt_ft"] - 1.5, lat=rows[-1]["lat"] + 1e-6))
        t += 1 / hz
    for i in range(int(hz * 3)):                          # level off
        rows.append(dict(rows[-1], t=t, aoa_deg=3.0, r_dps=0.0, yoke_y=0.0, pedals=0.0, ias_kt=80.0, vs_fpm=0.0,
                         stall_warn=0, lat=rows[-1]["lat"] + 1e-6))
        t += 1 / hz
    return rows


def test_stallspin_detects_spin_turns_and_recovery(tmp_path):
    from datetime import datetime
    from msfsdiag.analysis import stallspin as ss
    rows = spin_rows()
    run = tmp_path / "x_stall-spin.jsonl"
    run.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows))
    t0 = datetime.fromtimestamp(T0).strftime("%H:%M:%S")
    t1 = datetime.fromtimestamp(rows[-1]["t"]).strftime("%H:%M:%S")
    (tmp_path / "x_stall-spin.meta.json").write_text(json.dumps({"segments": [{"from": t0, "to": t1, "point": "E"}]}))
    meta, (p,) = ss.analyze(run)
    m = p.m
    assert m["kind"] == "spin" and m["direction"] == "right"
    assert m["turns_before_first_input"] == pytest.approx(2.0, abs=0.05)   # 120 deg/s for 6 s
    assert m["turns_after_first_input"] == pytest.approx(1 / 6, abs=0.05)  # linear decay over 1 s
    assert m["stopped_by"] == "yoke forward + opposite rudder"
    assert m["per_turn"][0]["s"] == pytest.approx(3.0, abs=0.05)


def test_stallspin_sign_normalisation():
    from msfsdiag.analysis import stallspin as ss
    raw = dict(t=T0, ias_kt=50, aoa_deg=10, pitch_deg=-5.0, bank_deg=-20.0, p_dps=-10.0, q_dps=0.0, r_dps=3.0,
               alt_ft=5000)
    s = ss.norm(raw)
    assert s["pitch"] == 5.0 and s["bank"] == 20.0 and s["roll"] == 10.0 and s["yaw"] == 3.0


def test_3d_payload_positions_and_page(tmp_path):
    from msfsdiag.analysis import stallspin as ss, stallspin_3d
    s0 = dict(t=T0, lat=40.0, lon=-77.0, alt=5000.0, hdg=90.0, pitch=0.0, bank=0.0, aoa=5.0, rot=0.0, ias=60.0,
              vs=0.0, g=1.0, yoke=0.0, ped=0.0, ail=0.0)
    s1 = dict(s0, t=T0 + 1, lat=40.001, lon=-76.999, alt=5000.0 + 1 / 0.3048)
    pt = ss.Point("E", "12:00:00 E", "test", [s0, s1], T0)
    d = stallspin_3d.point_payload(pt)["data"]
    assert d["e"][1] == pytest.approx(111320 * 0.001 * math.cos(math.radians(40)), rel=1e-3)   # east, m
    assert d["n"][1] == pytest.approx(110.54, rel=1e-3)                                         # north, m
    assert d["u"][1] == pytest.approx(1.0, abs=0.01)                                            # up, m
    page = stallspin_3d.render(stallspin_3d.payload({"aircraft_title": "X"}, [pt]), back_href="x.html")
    assert "THREE.OrbitControls" in page and "<script src=" not in page
