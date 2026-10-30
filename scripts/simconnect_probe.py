"""Phase 1 spike: read glider/air-mass simvars from MSFS 2024 and print them.

Answers: can we connect, what rate do we get, and does AMBIENT WIND Y (vertical
air movement) show ridge/thermal lift?

usage:
  python scripts/simconnect_probe.py                  # print ~2 lines/s
  python scripts/simconnect_probe.py --out run.jsonl  # also record every sample
  python scripts/simconnect_probe.py --once           # one sample, all vars, then exit
"""

import argparse
import json
import math
import sys
import time

from ctypes import POINTER, cast

from SimConnect import SimConnect
from SimConnect.Enum import SIMCONNECT_RECV_ID, SIMCONNECT_RECV_OPEN
from SimConnect.RequestList import Request

import msfsdiag


class VersionedSimConnect(SimConnect):
    """SimConnect that keeps the sim's version from the connection message."""

    sim_info = None

    def my_dispatch_proc(self, pData, cbData, pContext):
        if pData.contents.dwID == SIMCONNECT_RECV_ID.SIMCONNECT_RECV_ID_OPEN:
            o = cast(pData, POINTER(SIMCONNECT_RECV_OPEN)).contents
            self.sim_info = {
                "app": o.szApplicationName.decode(errors="replace"),
                "version": f"{o.dwApplicationVersionMajor}.{o.dwApplicationVersionMinor}"
                           f".{o.dwApplicationBuildMajor}.{o.dwApplicationBuildMinor}",
                "simconnect": f"{o.dwSimConnectVersionMajor}.{o.dwSimConnectVersionMinor}"
                              f".{o.dwSimConnectBuildMajor}.{o.dwSimConnectBuildMinor}",
            }
        return super().my_dispatch_proc(pData, cbData, pContext)

# (key, simvar, unit). units chosen so the analysis is SI where it matters.
VARS = [
    ("lat", b"PLANE LATITUDE", b"Degrees"),
    ("lon", b"PLANE LONGITUDE", b"Degrees"),
    ("alt_m", b"PLANE ALTITUDE", b"Meters"),
    ("agl_m", b"PLANE ALT ABOVE GROUND", b"Meters"),
    ("ias_kmh", b"AIRSPEED INDICATED", b"Kilometers per hour"),
    ("tas_kmh", b"AIRSPEED TRUE", b"Kilometers per hour"),
    ("vs_ms", b"VERTICAL SPEED", b"Meters per second"),
    ("vario_ms", b"VARIOMETER RATE", b"Meters per second"),
    ("air_w_ms", b"AMBIENT WIND Y", b"Meters per second"),
    ("air_e_ms", b"AMBIENT WIND X", b"Meters per second"),
    ("air_n_ms", b"AMBIENT WIND Z", b"Meters per second"),
    ("wind_dir", b"AMBIENT WIND DIRECTION", b"Degrees"),
    ("wind_kt", b"AMBIENT WIND VELOCITY", b"Knots"),
    ("acft_wind_y_ms", b"AIRCRAFT WIND Y", b"Meters per second"),
    ("bank_deg", b"PLANE BANK DEGREES", b"Degrees"),
    ("pitch_deg", b"PLANE PITCH DEGREES", b"Degrees"),
    ("hdg_true", b"PLANE HEADING DEGREES TRUE", b"Degrees"),
    ("weight_kg", b"TOTAL WEIGHT", b"Kilograms"),
    ("flap_idx", b"FLAPS HANDLE INDEX", b"Number"),
    ("flap_l_deg", b"TRAILING EDGE FLAPS LEFT ANGLE", b"Degrees"),
    ("spoilers", b"SPOILERS HANDLE POSITION", b"Percent"),
    ("sim_rate", b"SIMULATION RATE", b"Number"),
    # sim clock, to tell sim time from real-world time
    ("sim_local_s", b"LOCAL TIME", b"Seconds"),
    ("sim_zulu_s", b"ZULU TIME", b"Seconds"),
    ("sim_day_of_year", b"LOCAL DAY OF YEAR", b"Number"),
    ("sim_time_of_day", b"TIME OF DAY", b"Enum"),  # 0 dawn, 1 day, 2 dusk, 3 night
    ("on_ground", b"SIM ON GROUND", b"Bool"),
]
STRING_VARS = [("title", b"TITLE", b"String")]


def make_requests(sm):
    reqs = {k: Request((name, unit), sm, _time=0) for k, name, unit in VARS}
    reqs.update({k: Request((name, unit), sm, _time=0) for k, name, unit in STRING_VARS})
    return reqs


def sample(reqs, sm):
    out = {"t": time.time(), "paused": bool(sm.paused)}
    for k, r in reqs.items():
        v = r.value
        if isinstance(v, bytes):
            v = v.decode(errors="replace").rstrip("\x00")
        elif isinstance(v, float) and not math.isfinite(v):
            v = None
        out[k] = v
    return out


def fmt(s):
    def f(k, n=2):
        v = s.get(k)
        return "   n/a" if v is None else f"{v:6.{n}f}"
    return (f"ias {f('ias_kmh',0)} km/h  vs {f('vs_ms')}  vario {f('vario_ms')}  "
            f"AIR_W {f('air_w_ms')}  acftY {f('acft_wind_y_ms')}  "
            f"wind {f('wind_dir',0)}/{f('wind_kt',0)}kt  agl {f('agl_m',0)} m  bank {f('bank_deg',0)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write every sample as JSON Lines")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--print-every", type=float, default=0.5, help="seconds between printed lines")
    ap.add_argument("--note", default="", help="test conditions, saved in the .meta.json sidecar")
    args = ap.parse_args()

    sm = VersionedSimConnect()
    reqs = make_requests(sm)
    first = sample(reqs, sm)
    if args.once:
        print(json.dumps({"sim": sm.sim_info, **first}, indent=2))
        sm.exit()
        return
    print(f"connected: {sm.sim_info} {first.get('title')}")
    if args.out:
        meta = {
            "tool": "simconnect_probe",
            "tool_version": msfsdiag.__version__,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "sim": sm.sim_info,
            "aircraft_title": first.get("title"),
            "note": args.note,
            "vars": {k: [n.decode(), u.decode()] for k, n, u in VARS},
        }
        with open(args.out.removesuffix(".jsonl") + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    # line-buffered, so a killed process still leaves every sample on disk
    out = open(args.out, "a", encoding="utf-8", buffering=1) if args.out else None
    n, t0, last_print = 0, time.time(), time.time()
    try:
        while True:
            s = sample(reqs, sm)
            n += 1
            if out:
                out.write(json.dumps(s) + "\n")
            if s["t"] - last_print >= args.print_every:
                rate = n / (s["t"] - t0)
                print(f"{fmt(s)}  [{rate:4.1f} Hz]", flush=True)
                last_print = s["t"]
    except KeyboardInterrupt:
        pass
    finally:
        if out:
            out.close()
        sm.exit()


if __name__ == "__main__":
    sys.exit(main())
