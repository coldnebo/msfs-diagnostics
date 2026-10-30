import json

import pytest

import msfsdiag
from msfsdiag import config


def test_version_is_semver():
    parts = msfsdiag.__version__.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_defaults_when_no_local_config(tmp_path):
    cfg = config.load(tmp_path / "missing.json")
    assert cfg.community_folder is None
    assert cfg.data_dir == config.REPO_ROOT / "data"
    assert cfg.raw_dir == config.REPO_ROOT / "data" / "raw"


def test_relative_and_absolute_paths(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"data_dir": "elsewhere", "community_folder": str(tmp_path)}))
    cfg = config.load(p)
    assert cfg.data_dir == config.REPO_ROOT / "elsewhere"
    assert cfg.community_folder == tmp_path


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"comunity_folder": "typo"}))
    with pytest.raises(ValueError, match="comunity_folder"):
        config.load(p)


def test_example_config_has_only_known_keys():
    example = json.loads((config.REPO_ROOT / "config.example.json").read_text())
    assert set(example) <= {f for f in config.Config.__dataclass_fields__}
