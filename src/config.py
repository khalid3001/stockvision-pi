"""Load and validate config.yaml. Every other module receives the resulting dict."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"

REQUIRED_SECTIONS = ["project", "model", "classes", "inventory", "variance", "video", "output"]
VIDEO_MODES = ("track", "peak")
CAMERA_BACKENDS = ("auto", "picamera", "webcam")
# The camera section is optional, so a config.yaml written before the Raspberry Pi work still loads.
CAMERA_DEFAULTS = {"backend": "auto", "width": 2304, "height": 1296, "warmup_seconds": 2,
                   "autofocus": True, "rotate": 0, "webcam_index": 0}


class ConfigError(ValueError):
    pass


def load_config(path=None) -> dict:
    """Read the YAML file, check it, and turn relative paths into absolute ones."""
    path = Path(path) if path else DEFAULT_CONFIG
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate(cfg)

    base = path.resolve().parent
    cfg["model"]["weights"] = str(_abs(base, cfg["model"]["weights"]))
    cfg["inventory"]["source_csv"] = str(_abs(base, cfg["inventory"]["source_csv"]))
    cfg["inventory"]["database"] = str(_abs(base, cfg["inventory"]["database"]))
    cfg["output"]["dir"] = str(_abs(base, cfg["output"]["dir"]))
    return cfg


def _abs(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else base / p


def _validate(cfg: dict) -> None:
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ConfigError(f"config.yaml is missing section(s): {', '.join(missing)}")

    classes = cfg["classes"]
    if not isinstance(classes, dict) or not classes:
        raise ConfigError("config.yaml: 'classes' must list at least one product class")
    skus = []
    for name, info in classes.items():
        if not isinstance(info, dict) or "sku" not in info:
            raise ConfigError(f"config.yaml: class '{name}' needs a 'sku'")
        info.setdefault("display_name", name)
        skus.append(info["sku"])
    if len(skus) != len(set(skus)):
        raise ConfigError("config.yaml: two classes share the same sku")

    var = cfg["variance"]
    if not 0 <= var["match_pct"] <= var["minor_pct"]:
        raise ConfigError("config.yaml: need 0 <= variance.match_pct <= variance.minor_pct")

    video = cfg["video"]
    if video["mode"] not in VIDEO_MODES:
        raise ConfigError(f"config.yaml: video.mode must be one of {VIDEO_MODES}")
    video.setdefault("frame_stride", 3)
    video.setdefault("min_track_frames", 3)
    if video["frame_stride"] < 1:
        raise ConfigError("config.yaml: video.frame_stride must be 1 or more")

    for key in ("weights", "confidence"):
        if key not in cfg["model"]:
            raise ConfigError(f"config.yaml: model.{key} is required")
    cfg["model"].setdefault("iou", 0.5)
    cfg["model"].setdefault("image_size", 640)
    cfg["model"].setdefault("device", "cpu")

    camera = cfg.get("camera") or {}
    cfg["camera"] = {**CAMERA_DEFAULTS, **camera}
    if cfg["camera"]["backend"] not in CAMERA_BACKENDS:
        raise ConfigError(f"config.yaml: camera.backend must be one of {CAMERA_BACKENDS}")
    if cfg["camera"]["rotate"] not in (0, 90, 180, 270):
        raise ConfigError("config.yaml: camera.rotate must be 0, 90, 180 or 270")
