"""Local settings (paths), read from config.local.json at the repo root.

config.local.json is gitignored. Copy config.example.json to create it.
Any key it leaves out falls back to the default below.
"""

import json
from dataclasses import dataclass, fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_CONFIG = REPO_ROOT / "config.local.json"


@dataclass(frozen=True)
class Config:
    # MSFS 2024 Community folder, used to find installed aircraft and presets
    community_folder: Path | None = None
    data_dir: Path = REPO_ROOT / "data"
    reports_dir: Path = REPO_ROOT / "reports"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


def load(path: Path = LOCAL_CONFIG) -> Config:
    if not path.exists():
        return Config()
    values = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"unknown keys in {path.name}: {', '.join(sorted(unknown))}")
    # relative paths are relative to the repo root
    resolved = {
        k: (REPO_ROOT / v if not Path(v).is_absolute() else Path(v)) if v is not None else None
        for k, v in values.items()
    }
    return Config(**resolved)
