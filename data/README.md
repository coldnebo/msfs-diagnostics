# data

performance reference data, parsed polars, and measured baselines.

```
data/
  sources/                 reference documents (PDFs gitignored, catalog committed)
    sources.json           catalog: url, issuer, issue, sha256, polar pages, fit
    manuals/<type>/        real-world flight manuals
    sim-manuals/<vendor>/  manuals for the sim aircraft
    tcds/                  EASA type certificate data sheets
  polars/                  polars parsed to json, one file per aircraft+config
  baselines/
    msfs2024-<build>/      measurements for one MSFS 2024 build
      <aircraft-id>/       e.g. gotfriends-as33me, gotfriends-discus2c, asobo-dg1001e
  raw/                     raw telemetry recordings (gitignored)
```

## sources

the PDFs are copyrighted, so only the catalog is committed. to download them:

```
python scripts/fetch_sources.py
```

| aircraft in sim | reference | fit |
|---|---|---|
| GotFriends AS 33 Me | Schleicher AS 33 **Es** flight manual, 01.11.2020 ([pdf](https://www.a-glider-for-renting.com/Dedicated/pdf/AS-33%20D-KTJL%20Flight%20Manual.pdf)) | proxy: same airframe, different weights. polars marked "preliminary estimate" |
| | Schleicher AS 33 Me list of applicable publications, issue 05 ([pdf](https://www.alexander-schleicher.de/wp-content/uploads/2024/07/335_99_0001_LOAP_05.pdf)) | citation for the real AS 33 Me manual (01.11.2022), not publicly hosted |
| | GotFriends AS 33 Me sim manual ([drive](https://drive.google.com/file/d/1oneeMS4Ybkh_CC5bptc1t3NnS3Gqjkb1/view)) | exact: developer's intended polar |
| GotFriends Discus 2C | Schempp-Hirth Discus-2c FES Flughandbuch, Jan 2016 rev 1, German ([pdf](https://sgbaselfricktal.ch/wp-content/uploads/2021/04/FHB_Discus_2cFES_kpl._inkl._Rev._1.pdf)) | exact: sim models the FES variant |
| | GotFriends Discus-2c sim manual ([drive](https://drive.google.com/file/d/1BPhNNgA1kJChjoVVdWNxKERqtgW_DfXd/view)) | exact: specs and weights |
| Asobo DG1001e Neo | DG Flugzeugbau DG-1000S flight manual, March 2002 ([pdf](https://adelaidesoaring.org.au/wp-content/uploads/2025/12/DG-1000s-Flight-Manual.pdf)) | proxy: same airframe; DG-1001E manual (Dec 2022) not publicly hosted |
| all | EASA TCDS [A.656](https://www.easa.europa.eu/en/downloads/119201/en) (AS 33), [A.050](https://www.easa.europa.eu/en/downloads/7425/en) (Discus), [A.072](https://www.easa.europa.eu/en/downloads/7380/en) (DG-1000) | approved masses, wing areas, manual editions |

the manufacturer polars are graphs, so `polars/*.json` will be digitized from them. each json cites its source `id` and page.

## baselines

a baseline is a measured result for one aircraft on one sim build: e.g. the still-air polar, or ridge/thermal test results. folders are named by the build string SimConnect reports (e.g. `msfs2024-12.2.282174.999`; the recorder writes it to each run's `.meta.json`), so results from different builds can be compared side by side. the store version (e.g. 1.9.21.0) isn't available over SimConnect, so add it to the meta by hand as `sim.store_version`.

## polars

One JSON file per aircraft in `polars/`. The analysis picks the file whose `match_titles` entry appears in the sim's aircraft `TITLE`.

```json
{
  "aircraft": "DG-1000 (20 m)",
  "match_titles": ["DG-1001", "DG-1000"],
  "status": "table",                       // table | provisional | ... (shown on reports)
  "source": { "id": "<sources.json id>", "page": "where the numbers came from", "read_on": "YYYY-MM-DD" },
  "valid_ias_kmh": [70, 130],              // predictions outside this range are left blank
  "flaps": false,                          // or "flap_index_names": {"4": "N"} for FLAPS HANDLE INDEX labels
  "sets": [                                // one per reference mass
    { "mass_kg": 736,
      "min_sink": { "ias_kmh": 98, "sink_ms": 0.62 },               // optional: becomes the curve's lowest point
      "points": [ { "ias_kmh": 120, "sink_ms": 0.715 } ] }           // IAS km/h, sink m/s, straight flight, sea level
  ]
}
```

Each set is fitted with a parabola (least squares through the points; with `min_sink`, the points are mirrored across it so the minimum sits there). Predictions use the set nearest the actual mass, scaled by √(m/m_ref), then corrected for bank (÷cos^1.5) and altitude (×TAS/IAS). Points read off a chart are recorded once and reused; changing them is a deliberate edit, logged in `design/WORKLOG.md`.
