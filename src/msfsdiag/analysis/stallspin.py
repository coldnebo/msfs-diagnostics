"""Stall and spin test points: event detection and measurements.

Reads a high-rate recording (msfsdiag.telemetry.recorder) and its .meta.json.
Each meta segment with a test-card "point" is one window. Only those windows
are kept in memory, so 100+ MB recordings are fine.

Signs are normalised here (MSFS raw values in brackets):
  pitch  + nose up        (pitch_deg + = nose down)
  bank   + right wing down (bank_deg + = left wing down)
  roll   + rolling right   (p_dps + = rolling left)
  yaw    + yawing right    (r_dps, unchanged)
  rot    rotation about the vertical, + clockwise seen from above (right).
         from body rates projected on the vertical; heading is useless near
         vertical and body yaw/roll split a spin's rotation between them.

Detected per point (all optional): warning, full_aft, peak_aoa, departure,
pro_rudder, yoke_fwd, opp_rudder, stop, level. Measurements: see measure().
"""

import gzip
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from pathlib import Path
from statistics import mean

DEPART_DPS = 30.0       # rotation rate that counts as departed
STOP_DPS = 15.0         # rotation stopped below this ...
STOP_HOLD_S = 0.5       # ... for this long, with AoA below the stall
SPIN_TURNS = 1.0        # at least this much rotation in total = a spin (less = a departure)
YOKE_FWD = 0.3          # yoke moved this far forward of its most-aft position = a recovery input
WINDOW_PAD_S = (5.0, 15.0)


def _num(v):
    return v if isinstance(v, (int, float)) else None


def norm(r):
    """One raw sample -> normalised sample (dict), or None if unusable."""
    need = ("ias_kt", "aoa_deg", "pitch_deg", "bank_deg", "p_dps", "q_dps", "r_dps", "alt_ft")
    if any(_num(r.get(k)) is None for k in need):
        return None
    th, ph = math.radians(-r["pitch_deg"]), math.radians(-r["bank_deg"])
    p, q, rr = -r["p_dps"], -r["q_dps"], r["r_dps"]
    rot = -p * math.sin(th) + q * math.sin(ph) * math.cos(th) + rr * math.cos(ph) * math.cos(th)
    return {
        "t": r["t"], "paused": bool(r.get("paused")), "on_ground": bool(r.get("on_ground")),
        "lat": r.get("lat"), "lon": r.get("lon"),
        "ias": r["ias_kt"], "aoa": r["aoa_deg"], "beta": _num(r.get("beta_deg")),
        "pitch": -r["pitch_deg"], "bank": -r["bank_deg"], "roll": p, "yaw": rr, "rot": rot,
        "g": _num(r.get("g")), "alt": r["alt_ft"], "vs": _num(r.get("vs_fpm")),
        "yoke": _num(r.get("yoke_y")) or 0.0, "ail": _num(r.get("yoke_x")) or 0.0, "ped": _num(r.get("pedals")) or 0.0,
        "thr": _num(r.get("throttle")), "rpm": _num(r.get("prop_rpm")),
        "flap": _num(r.get("flap_idx")), "flap_deg": _num(r.get("flap_l_deg")), "gear": _num(r.get("gear_pct")),
        "warn": bool(r.get("stall_warn")), "stall_aoa": _num(r.get("stall_aoa_deg")),
        "weight": _num(r.get("weight_lb")), "title": r.get("title", ""),
    }


def usable(s, prev):
    """Not paused, airborne, not frozen (exact repeat), not a slew (rates exactly zero at ~0 kt)."""
    if s is None or s["paused"] or s["on_ground"]:
        return False
    if prev is not None and (s["lat"], s["lon"], s["alt"]) == (prev["lat"], prev["lon"], prev["alt"]):
        return False
    if s["ias"] < 1 and s["roll"] == 0 and s["yaw"] == 0:
        return False
    if s["vs"] is not None and abs(s["vs"]) > 15000:
        return False
    return True


# ---------- loading

def meta_path(run_path):
    p = Path(run_path)
    return p.with_name(p.name.removesuffix(".gz").removesuffix(".jsonl") + ".meta.json")


def segments(meta, day):
    """Meta segments that are test points, as unix-time windows."""
    def ts(hms):
        h, m, s = (int(x) for x in hms.split(":"))
        return datetime.combine(day, dtime(h, m, s)).timestamp()
    out = []
    for seg in meta.get("segments", []):
        point = seg.get("point", "")
        if not point or point == "-":
            continue
        out.append({"point": point, "what": seg.get("what", ""), "t0": ts(seg["from"]), "t1": ts(seg["to"]),
                    "label": f"{seg['from']} {point}"})
    return out


def load_windows(run_path, windows):
    """Usable normalised samples for each (t0, t1) window, reading the file once."""
    p = Path(run_path)
    opener = gzip.open if p.name.endswith(".gz") else open
    lo = min(w[0] for w in windows) if windows else 0
    hi = max(w[1] for w in windows) if windows else 0
    out = [[] for _ in windows]
    prev = None
    with opener(p, "rt", encoding="utf-8") as f:
        for line in f:
            # cheap pre-filter on the timestamp before parsing the whole line
            t = float(line[5:line.index(",")]) if line.startswith('{"t":') else None
            if t is not None and (t < lo or t > hi):
                continue
            s = norm(json.loads(line))
            ok = usable(s, prev)
            prev = s if s is not None else prev
            if not ok:
                continue
            for i, (a, b) in enumerate(windows):
                if a <= s["t"] <= b:
                    out[i].append(s)
    return out


def first_day(run_path):
    p = Path(run_path)
    opener = gzip.open if p.name.endswith(".gz") else open
    with opener(p, "rt", encoding="utf-8") as f:
        return datetime.fromtimestamp(json.loads(f.readline())["t"]).date()


# ---------- detection

@dataclass
class Point:
    point: str
    label: str
    what: str
    samples: list
    t_start: float = 0.0                             # segment start (samples begin WINDOW_PAD_S earlier)
    events: dict = field(default_factory=dict)      # name -> index into samples
    m: dict = field(default_factory=dict)            # measurements


def _first(samples, start, cond):
    for i in range(start, len(samples)):
        if cond(samples[i]):
            return i
    return None


def _integrate(samples, i0, i1, key="rot"):
    return sum(samples[i][key] * (samples[i + 1]["t"] - samples[i]["t"]) for i in range(i0, min(i1, len(samples) - 1)))


def _turn_marks(samples, i0, i1):
    """Indices where each full turn (360°) about the vertical completes, from i0 to i1."""
    marks, acc = [i0], 0.0
    for i in range(i0, min(i1, len(samples) - 1)):
        acc += abs(samples[i]["rot"]) * (samples[i + 1]["t"] - samples[i]["t"])
        if acc >= 360 * len(marks):
            marks.append(i + 1)
    return marks


def _slope(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


def detect(pt: Point):
    s, ev = pt.samples, pt.events
    if len(s) < 10:
        return pt
    stall_aoa = next((x["stall_aoa"] for x in s if x["stall_aoa"]), 14.0)
    seg0 = _first(s, 0, lambda x: x["t"] >= pt.t_start) or 0
    ev["warning"] = _first(s, seg0, lambda x: x["warn"])
    start = ev["warning"] if ev["warning"] is not None else seg0
    ev["full_aft"] = _first(s, start, lambda x: x["yoke"] >= 0.95)
    ev["departure"] = _first(s, start, lambda x: abs(x["rot"]) >= DEPART_DPS and x["aoa"] > stall_aoa * 0.8)
    pro = _first(s, start, lambda x: abs(x["ped"]) >= 0.9)
    ev["pro_rudder"] = pro
    end_break = ev["departure"] if ev["departure"] is not None else min(len(s) - 1, start + 60 * 8)
    ev["peak_aoa"] = max(range(start, end_break + 1), key=lambda i: s[i]["aoa"]) if end_break >= start else None

    dep = ev["departure"]
    if dep is not None:
        direction = 1 if _integrate(s, dep, min(len(s), dep + 120)) > 0 else -1
        # recovery inputs: yoke well forward of full aft, and rudder against the rotation
        # yoke forward: a real forward movement from the most-aft position so far
        ev["yoke_fwd"] = None
        aft = max(x["yoke"] for x in s[start:dep + 1])
        for i in range(dep, len(s)):
            aft = max(aft, s[i]["yoke"])
            if s[i]["yoke"] < min(0.6, aft - YOKE_FWD):
                ev["yoke_fwd"] = i
                break
        ev["opp_rudder"] = _first(s, dep, lambda x: x["ped"] * direction < -0.4)
        # stop: rotation below STOP_DPS, unstalled, held for STOP_HOLD_S
        i = dep
        while i < len(s):
            if abs(s[i]["rot"]) < STOP_DPS and s[i]["aoa"] < stall_aoa:
                j = i
                while j < len(s) and abs(s[j]["rot"]) < STOP_DPS and s[j]["t"] - s[i]["t"] < STOP_HOLD_S:
                    j += 1
                if j >= len(s) or s[j]["t"] - s[i]["t"] >= STOP_HOLD_S:
                    ev["stop"] = i
                    break
                i = j
            i += 1
        pt.m["direction"] = "right" if direction > 0 else "left"
    after = ev.get("stop") or ev.get("peak_aoa") or start
    ev["level"] = _first(s, after, lambda x: x["vs"] is not None and abs(x["vs"]) < 500 and abs(x["pitch"]) < 10
                         and x["ias"] > 50)
    measure(pt, stall_aoa)
    return pt


def measure(pt: Point, stall_aoa):
    s, ev, m = pt.samples, pt.events, pt.m
    t = lambda k: s[ev[k]]["t"] if ev.get(k) is not None else None
    w = ev.get("warning")
    if w is not None:
        m["warn_ias_kt"], m["warn_aoa_deg"] = round(s[w]["ias"], 1), round(s[w]["aoa"], 1)
    ref = w if w is not None else 0
    m["flaps_deg"] = round(s[ref]["flap_deg"], 0) if s[ref]["flap_deg"] is not None else None
    m["gear_pct"] = s[ref]["gear"]
    m["throttle_pct"] = round(s[ref]["thr"], 0) if s[ref]["thr"] is not None else None
    m["weight_lb"] = round(s[ref]["weight"], 0) if s[ref]["weight"] else None
    m["entry_alt_ft"] = round(s[ref]["alt"])
    m["stall_aoa_sim_deg"] = round(stall_aoa, 2)
    pk = ev.get("peak_aoa")
    if pk is not None:
        m["peak_aoa_deg"] = round(s[pk]["aoa"], 1)
        m["min_ias_kt"] = round(min(x["ias"] for x in s[ref:pk + 1]), 1)
        m["yoke_at_peak"] = round(s[pk]["yoke"], 2)
        # break: what the aircraft did in the 4 s after peak AoA (or until departure)
        hi = _first(s, pk, lambda x: x["t"] > s[pk]["t"] + 4.0) or len(s) - 1
        if ev.get("departure") is not None:
            hi = min(hi, ev["departure"])
        win = s[pk:hi + 1]
        m["pitch_break_deg"] = round(s[pk]["pitch"] - min(x["pitch"] for x in win), 1)
        m["wing_drop_deg"] = round(max(abs(x["bank"]) for x in win), 1)
        m["max_roll_rate_dps"] = round(max(abs(x["roll"]) for x in win), 0)
    dep = ev.get("departure")
    first_input = min([i for i in (ev.get("yoke_fwd"), ev.get("opp_rudder")) if i is not None], default=None)
    if dep is not None:
        m["departure_s_after_warning"] = round(s[dep]["t"] - s[ref]["t"], 1)
        pro = ev.get("pro_rudder")
        m["pro_rudder_before_departure"] = pro is not None and pro <= dep + 6   # within ~0.1 s
        stop = ev.get("stop")
        last = stop if stop is not None else len(s) - 1
        turns_total = abs(_integrate(s, dep, last)) / 360
        m["turns_total"] = round(turns_total, 2)
        if first_input is not None:
            m["turns_before_first_input"] = round(abs(_integrate(s, dep, first_input)) / 360, 2)
        # the spin's own phase ends at the input that stopped it: the first input if the
        # rotation died within half a turn of it, else opposite rudder (or the stop)
        end = first_input if first_input is not None else last
        if first_input is not None and abs(_integrate(s, first_input, last)) / 360 > 0.5:
            opp = ev.get("opp_rudder")
            end = opp if opp is not None and opp > first_input else last
        marks = _turn_marks(s, dep, end)
        m["per_turn"] = [{"s": round(s[b]["t"] - s[a]["t"], 1), "ft": round(s[a]["alt"] - s[b]["alt"])}
                         for a, b in zip(marks, marks[1:])]
        if stop is not None:
            if first_input is not None:
                m["turns_after_first_input"] = round(abs(_integrate(s, first_input, stop)) / 360, 2)
            if ev.get("opp_rudder") is not None and ev["opp_rudder"] < stop:
                m["turns_after_opp_rudder"] = round(abs(_integrate(s, ev["opp_rudder"], stop)) / 360, 2)
                m["s_after_opp_rudder"] = round(s[stop]["t"] - s[ev["opp_rudder"]]["t"], 1)
            m["stopped_by"] = _stopped_by(s, ev, first_input, stop)
        # developed spin: after the first full turn, until the first recovery input
        if len(marks) >= 3:
            dev = s[marks[1]:end]
            ts = [x["t"] - dev[0]["t"] for x in dev]
            m["developed"] = {
                "s_per_turn": round(mean(p["s"] for p in m["per_turn"][1:]), 2),
                "ft_per_turn": round(mean(p["ft"] for p in m["per_turn"][1:])),
                "rot_dps": round(mean(abs(x["rot"]) for x in dev)),
                "aoa_deg": [round(min(x["aoa"] for x in dev), 1), round(mean(x["aoa"] for x in dev), 1),
                            round(max(x["aoa"] for x in dev), 1)],
                "pitch_deg": [round(min(x["pitch"] for x in dev)), round(max(x["pitch"] for x in dev))],
                "ias_kt": [round(dev[0]["ias"]), round(dev[-1]["ias"])],
                "ias_slope_kt_s": round(_slope(ts, [x["ias"] for x in dev]) or 0, 2),
                "g_slope_per_s": round(_slope(ts, [x["g"] or 1 for x in dev]) or 0, 3),
                "sideslip_deg": round(mean(abs(x["beta"] or 0) for x in dev), 1),
            }
            d = m["developed"]
            m["mode"] = ("flat" if d["aoa_deg"][1] >= 35 else
                         "spiral-like" if d["ias_slope_kt_s"] > 0.8 and d["aoa_deg"][1] < 22 else "steep")
        m["kind"] = "spin" if turns_total >= SPIN_TURNS else "departure"
        if m["kind"] == "departure":
            # under a turn of rotation: the direction is the wing that dropped
            drop = max(s[dep:last + 1], key=lambda x: abs(x["bank"]))
            m["direction"] = "right" if drop["bank"] > 0 else "left"
    else:
        m["kind"] = "stall"
    lv = ev.get("level")
    span = s[ref:(lv + 1) if lv is not None else len(s)]
    m["height_lost_ft"] = round(s[ref]["alt"] - min(x["alt"] for x in span))
    m["max_g"] = round(max((x["g"] or 0) for x in span), 2)
    m["max_ias_kt"] = round(max(x["ias"] for x in span))
    for k in ("warning", "full_aft", "peak_aoa", "departure", "pro_rudder", "yoke_fwd", "opp_rudder", "stop", "level"):
        if t(k) is not None:
            m.setdefault("times", {})[k] = datetime.fromtimestamp(t(k)).strftime("%H:%M:%S.%f")[:-4]


def _stopped_by(s, ev, first_input, stop):
    """Which input the rotation stop followed: the one in effect over the last 0.5 s before the stop."""
    yf, opp = ev.get("yoke_fwd"), ev.get("opp_rudder")
    cands = [(k, i) for k, i in (("yoke forward", yf), ("opposite rudder", opp)) if i is not None and i <= stop]
    if not cands:
        return "none recorded"
    if len(cands) == 2 and abs(s[cands[0][1]]["t"] - s[cands[1][1]]["t"]) < 0.5:
        return "yoke forward + opposite rudder"
    return max(cands, key=lambda c: c[1])[0]


# ---------- run level

def analyze(run_path):
    run_path = Path(run_path)
    meta = json.loads(meta_path(run_path).read_text(encoding="utf-8"))
    segs = segments(meta, first_day(run_path))
    windows = [(g["t0"] - WINDOW_PAD_S[0], g["t1"] + WINDOW_PAD_S[1]) for g in segs]
    data = load_windows(run_path, windows)
    points = [detect(Point(g["point"], g["label"], g["what"], d, g["t0"])) for g, d in zip(segs, data)]
    return meta, points


def results(run_path, meta, points):
    """The committed, small summary of a run."""
    return {
        "run": Path(run_path).name.removesuffix(".gz").removesuffix(".jsonl"),
        "aircraft_title": meta.get("aircraft_title"),
        "sim": meta.get("sim"),
        "points": [{"label": p.label, "point": p.point, "what": p.what, **p.m} for p in points],
    }
