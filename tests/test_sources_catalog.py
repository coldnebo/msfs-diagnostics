import json
import re

from msfsdiag.config import REPO_ROOT

REQUIRED = {"id", "kind", "aircraft", "title", "issuer", "issue", "url", "path", "sha256"}


def test_catalog_entries_are_complete_and_unique():
    sources = json.loads((REPO_ROOT / "data/sources/sources.json").read_text(encoding="utf-8"))["sources"]
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    for s in sources:
        assert REQUIRED <= set(s), s["id"]
        assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), s["id"]
        assert s["path"].startswith("data/sources/"), s["id"]
