"""Download the reference documents listed in data/sources/sources.json.

The PDFs are copyrighted, so they're not committed. This script fetches each
one to its catalog path and checks its sha256. Existing files that already
match are skipped.

usage: python scripts/fetch_sources.py [--force]
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "sources" / "sources.json"
USER_AGENT = "Mozilla/5.0 (msfs-diagnostics fetch_sources)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    force = "--force" in sys.argv
    sources = json.loads(CATALOG.read_text(encoding="utf-8"))["sources"]
    failed = 0
    for src in sources:
        dest = ROOT / src["path"]
        if dest.exists() and not force and sha256(dest) == src["sha256"]:
            print(f"ok       {src['id']}")
            continue
        url = src.get("download_url", src["url"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
        except OSError as e:
            print(f"FAILED   {src['id']}: {e}")
            failed += 1
            continue
        if sha256(dest) == src["sha256"]:
            print(f"fetched  {src['id']}")
        else:
            # the host may have published a new revision; keep it, but flag it
            print(f"CHANGED  {src['id']}: sha256 differs from catalog, check the document revision")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
