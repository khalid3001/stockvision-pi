from pathlib import Path

import pytest
import yaml

from src.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent


def test_real_config_loads_with_absolute_paths():
    cfg = load_config()
    assert Path(cfg["model"]["weights"]).is_absolute()
    assert Path(cfg["inventory"]["database"]).is_absolute()
    assert len(cfg["classes"]) >= 1


def _write(tmp_path, change):
    raw = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    change(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_bad_thresholds_rejected(tmp_path):
    path = _write(tmp_path, lambda c: c["variance"].update(match_pct=20, minor_pct=10))
    with pytest.raises(ConfigError):
        load_config(path)


def test_duplicate_sku_rejected(tmp_path):
    def change(c):
        for info in c["classes"].values():
            info["sku"] = "SAME"
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, change))


def test_unknown_video_mode_rejected(tmp_path):
    path = _write(tmp_path, lambda c: c["video"].update(mode="guess"))
    with pytest.raises(ConfigError):
        load_config(path)
