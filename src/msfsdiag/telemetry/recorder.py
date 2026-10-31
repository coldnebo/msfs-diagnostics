"""High-rate SimConnect recorder.

All numeric fields go in one data definition, delivered every sim frame
(SIMCONNECT_PERIOD_SIM_FRAME), so a sample is one consistent snapshot of the
aircraft. That's 20-60 samples/s depending on frame rate, versus ~2-3/s for
one-request-per-variable polling. --hz thins the output if wanted.

Field keys match the earlier probe (scripts/simconnect_probe.py), so the glider
analysis reads both. Added for stall/spin work: angle of attack, sideslip, body
rates, g, stall warning, control inputs and surfaces, engine, CG, and the landing
light, which a pilot can flip to mark a moment without touching the controls.

usage:
  python -m msfsdiag.telemetry.recorder --once
  python -m msfsdiag.telemetry.recorder --out data/raw/<name>.jsonl --note "..." [--hz 30]
"""

import argparse
import collections
import json
import math
import threading
import time
from ctypes import POINTER, addressof, c_double, cast

from SimConnect import SimConnect
from SimConnect.Constants import SIMCONNECT_OBJECT_ID_USER
from SimConnect.Enum import (SIMCONNECT_DATA_REQUEST_FLAG, SIMCONNECT_DATATYPE, SIMCONNECT_EXCEPTION,
                             SIMCONNECT_PERIOD, SIMCONNECT_RECV_EXCEPTION, SIMCONNECT_RECV_ID,
                             SIMCONNECT_RECV_OPEN, SIMCONNECT_RECV_SIMOBJECT_DATA)
from SimConnect.RequestList import Request

import msfsdiag

# (key, simvar, unit). keep keys stable: recordings and analysis depend on them.
FIELDS = [
    # position and height
    ("lat", "PLANE LATITUDE", "degrees"),
    ("lon", "PLANE LONGITUDE", "degrees"),
    ("alt_m", "PLANE ALTITUDE", "meters"),
    ("agl_m", "PLANE ALT ABOVE GROUND", "meters"),
    ("alt_ft", "PLANE ALTITUDE", "feet"),
    ("on_ground", "SIM ON GROUND", "bool"),
    # airspeed and vertical
    ("ias_kmh", "AIRSPEED INDICATED", "kilometers per hour"),
    ("tas_kmh", "AIRSPEED TRUE", "kilometers per hour"),
    ("ias_kt", "AIRSPEED INDICATED", "knots"),
    ("vs_ms", "VERTICAL SPEED", "meters per second"),
    ("vs_fpm", "VERTICAL SPEED", "feet per minute"),
    ("vario_ms", "VARIOMETER RATE", "meters per second"),
    # attitude, rates, loads
    ("pitch_deg", "PLANE PITCH DEGREES", "degrees"),
    ("bank_deg", "PLANE BANK DEGREES", "degrees"),
    ("hdg_true", "PLANE HEADING DEGREES TRUE", "degrees"),
    ("aoa_deg", "INCIDENCE ALPHA", "degrees"),
    ("beta_deg", "INCIDENCE BETA", "degrees"),
    ("p_dps", "ROTATION VELOCITY BODY Z", "degrees per second"),   # roll rate
    ("q_dps", "ROTATION VELOCITY BODY X", "degrees per second"),   # pitch rate
    ("r_dps", "ROTATION VELOCITY BODY Y", "degrees per second"),   # yaw rate
    ("g", "G FORCE", "gforce"),
    ("stall_warn", "STALL WARNING", "bool"),
    ("stall_aoa_deg", "STALL ALPHA", "degrees"),
    ("ball", "TURN COORDINATOR BALL", "position"),
    # controls: pilot inputs and surface positions (-1..1)
    ("yoke_x", "YOKE X POSITION", "position"),
    ("yoke_y", "YOKE Y POSITION", "position"),
    ("pedals", "RUDDER PEDAL POSITION", "position"),
    ("elevator", "ELEVATOR POSITION", "position"),
    ("aileron", "AILERON POSITION", "position"),
    ("rudder", "RUDDER POSITION", "position"),
    ("elev_trim", "ELEVATOR TRIM POSITION", "degrees"),
    ("flap_idx", "FLAPS HANDLE INDEX", "number"),
    ("flap_l_deg", "TRAILING EDGE FLAPS LEFT ANGLE", "degrees"),
    ("spoilers", "SPOILERS HANDLE POSITION", "percent"),
    # engine 1
    ("throttle", "GENERAL ENG THROTTLE LEVER POSITION:1", "percent"),
    ("rpm", "GENERAL ENG RPM:1", "rpm"),
    ("prop_rpm", "PROP RPM:1", "rpm"),
    ("map_inhg", "RECIP ENG MANIFOLD PRESSURE:1", "inhg"),
    # mass
    ("weight_kg", "TOTAL WEIGHT", "kilograms"),
    ("weight_lb", "TOTAL WEIGHT", "pounds"),
    ("cg_pct_mac", "CG PERCENT", "percent"),
    ("fuel_lb", "FUEL TOTAL QUANTITY WEIGHT", "pounds"),
    # air mass
    ("air_w_ms", "AMBIENT WIND Y", "meters per second"),
    ("air_e_ms", "AMBIENT WIND X", "meters per second"),
    ("air_n_ms", "AMBIENT WIND Z", "meters per second"),
    ("wind_dir", "AMBIENT WIND DIRECTION", "degrees"),
    ("wind_kt", "AMBIENT WIND VELOCITY", "knots"),
    ("acft_wind_y_ms", "AIRCRAFT WIND Y", "meters per second"),
    ("oat_c", "AMBIENT TEMPERATURE", "celsius"),
    ("baro_inhg", "KOHLSMAN SETTING HG", "inhg"),
    # markers and sim state
    ("light_landing", "LIGHT LANDING", "bool"),
    ("light_taxi", "LIGHT TAXI", "bool"),
    ("sim_rate", "SIMULATION RATE", "number"),
    ("sim_local_s", "LOCAL TIME", "seconds"),
    ("sim_zulu_s", "ZULU TIME", "seconds"),
    ("sim_day_of_year", "LOCAL DAY OF YEAR", "number"),
    ("sim_time_of_day", "TIME OF DAY", "enum"),
]


class Recorder(SimConnect):
    """SimConnect connection that streams FIELDS every sim frame into a queue."""

    def __init__(self):
        self.sim_info = None
        self.samples = collections.deque(maxlen=100_000)
        self.exceptions = []
        self.frames = 0
        self._req = None
        self._ready = threading.Event()
        super().__init__()

    def my_dispatch_proc(self, pData, cbData, pContext):
        rid = pData.contents.dwID
        if rid == SIMCONNECT_RECV_ID.SIMCONNECT_RECV_ID_SIMOBJECT_DATA:
            d = cast(pData, POINTER(SIMCONNECT_RECV_SIMOBJECT_DATA)).contents
            if self._req is not None and d.dwRequestID == self._req.value:
                vals = cast(addressof(d.dwData), POINTER(c_double * len(FIELDS))).contents
                self.samples.append((time.time(), tuple(vals)))
                self.frames += 1
                return
        elif rid == SIMCONNECT_RECV_ID.SIMCONNECT_RECV_ID_OPEN:
            o = cast(pData, POINTER(SIMCONNECT_RECV_OPEN)).contents
            self.sim_info = {
                "app": o.szApplicationName.decode(errors="replace"),
                "version": f"{o.dwApplicationVersionMajor}.{o.dwApplicationVersionMinor}"
                           f".{o.dwApplicationBuildMajor}.{o.dwApplicationBuildMinor}",
                "simconnect": f"{o.dwSimConnectVersionMajor}.{o.dwSimConnectVersionMinor}"
                              f".{o.dwSimConnectBuildMajor}.{o.dwSimConnectBuildMinor}",
            }
        elif rid == SIMCONNECT_RECV_ID.SIMCONNECT_RECV_ID_EXCEPTION:
            e = cast(pData, POINTER(SIMCONNECT_RECV_EXCEPTION)).contents
            try:
                name = SIMCONNECT_EXCEPTION(e.dwException).name
            except ValueError:
                name = str(e.dwException)
            self.exceptions.append({"exception": name, "send_id": e.dwSendID, "index": e.dwIndex})
            return
        return super().my_dispatch_proc(pData, cbData, pContext)

    def start(self):
        """Define FIELDS and ask for them every sim frame."""
        did = self.new_def_id()
        for _, name, unit in FIELDS:
            self.dll.AddToDataDefinition(self.hSimConnect, did.value, name.encode(), unit.encode(),
                                         SIMCONNECT_DATATYPE.SIMCONNECT_DATATYPE_FLOAT64, 0, 0xFFFFFFFF)
        self._req = self.new_request_id()
        self.dll.RequestDataOnSimObject(self.hSimConnect, self._req.value, did.value, SIMCONNECT_OBJECT_ID_USER,
                                        SIMCONNECT_PERIOD.SIMCONNECT_PERIOD_SIM_FRAME,
                                        SIMCONNECT_DATA_REQUEST_FLAG.SIMCONNECT_DATA_REQUEST_FLAG_DEFAULT, 0, 0, 0)
        self._title = Request((b"TITLE", b"String"), self, _time=2000)

    def title(self):
        v = self._title.value
        return v.decode(errors="replace").rstrip("\x00") if isinstance(v, bytes) else v


def to_row(t, vals, paused, title):
    row = {"t": round(t, 3), "paused": paused}
    for (k, _, _), v in zip(FIELDS, vals):
        row[k] = v if math.isfinite(v) else None
    row["title"] = title
    return row


def fmt(r):
    def f(k, spec):
        v = r.get(k)
        return format(v, spec) if isinstance(v, (int, float)) else "-"
    return (f"ias {f('ias_kt', '5.1f')} kt  aoa {f('aoa_deg', '5.1f')}  pitch {f('pitch_deg', '5.1f')}  "
            f"bank {f('bank_deg', '6.1f')}  yaw-rate {f('r_dps', '6.1f')}  g {f('g', '4.2f')}  "
            f"vs {f('vs_fpm', '6.0f')} fpm  alt {f('alt_ft', '6.0f')} ft  stall {f('stall_warn', '.0f')}  "
            f"ldg-light {f('light_landing', '.0f')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write samples as JSON Lines (+ .meta.json sidecar)")
    ap.add_argument("--note", default="", help="test conditions, saved in the .meta.json")
    ap.add_argument("--hz", type=float, default=0, help="max samples/s to write (0 = every sim frame)")
    ap.add_argument("--once", action="store_true", help="print one sample and exit")
    ap.add_argument("--print-every", type=float, default=1.0)
    args = ap.parse_args(argv)

    sm = Recorder()
    sm.start()
    deadline = time.time() + 10
    while not sm.samples and time.time() < deadline:
        time.sleep(0.02)
    if not sm.samples:
        raise SystemExit(f"no data from the sim (exceptions: {sm.exceptions})")
    title = sm.title()

    if args.once:
        t, vals = sm.samples[-1]
        print(json.dumps({"sim": sm.sim_info, "exceptions": sm.exceptions, **to_row(t, vals, bool(sm.paused), title)},
                         indent=2))
        sm.exit()
        return

    print(f"connected: {sm.sim_info} {title}")
    out = None
    if args.out:
        meta = {"tool": "msfsdiag.telemetry.recorder", "tool_version": msfsdiag.__version__,
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sim": sm.sim_info, "aircraft_title": title,
                "note": args.note, "rate": "sim frame" + (f", max {args.hz:g} Hz" if args.hz else ""),
                "vars": {k: [n, u] for k, n, u in FIELDS}}
        with open(args.out.removesuffix(".jsonl") + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        out = open(args.out, "a", encoding="utf-8", buffering=1)

    min_dt = 1.0 / args.hz if args.hz else 0.0
    last_w = last_p = 0.0
    n_written, t0 = 0, None
    try:
        while True:
            if not sm.samples:
                time.sleep(0.005)
                continue
            t, vals = sm.samples.popleft()
            if t - last_w < min_dt:
                continue
            last_w = t
            t0 = t if t0 is None else t0
            if t - last_p > 2.0:
                title = sm.title() or title
            row = to_row(t, vals, bool(sm.paused), title)
            if out:
                out.write(json.dumps(row, separators=(",", ":")) + "\n")
            n_written += 1
            if t - last_p >= args.print_every:
                rate = n_written / max(t - t0, 1.0)
                print(f"{fmt(row)}  [{rate:4.1f} Hz]", flush=True)
                last_p = t
    except KeyboardInterrupt:
        pass
    finally:
        if out:
            out.close()
        if sm.exceptions:
            print("simconnect exceptions:", sm.exceptions)
        sm.exit()


if __name__ == "__main__":
    main()
