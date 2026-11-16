import sys
import types

import cv2
import numpy as np
import pytest
import yaml

from src import camera
from src.config import ConfigError, load_config


class FakeWebcam:
    """Stands in for cv2.VideoCapture: returns a plain 40 x 20 picture."""
    released = False

    def __init__(self, index, opened=True):
        self.opened = opened

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        return True

    def read(self):
        return True, np.full((20, 40, 3), 128, dtype=np.uint8)

    def release(self):
        FakeWebcam.released = True


@pytest.fixture
def cam_cfg(cfg):
    cfg["camera"].update(backend="webcam", warmup_seconds=0)
    return cfg


def test_camera_section_is_optional(tmp_path, cfg):
    raw = yaml.safe_load(open(tmp_path / "config.yaml", encoding="utf-8"))
    del raw["camera"]
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    assert load_config(tmp_path / "config.yaml")["camera"]["backend"] == "auto"


def test_unknown_backend_rejected(tmp_path, cfg):
    raw = yaml.safe_load(open(tmp_path / "config.yaml", encoding="utf-8"))
    raw["camera"]["backend"] = "telescope"
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "config.yaml")


def test_auto_backend_follows_picamera2(cfg, monkeypatch):
    cfg["camera"]["backend"] = "auto"
    monkeypatch.setattr(camera.importlib.util, "find_spec", lambda name: None)
    assert camera.pick_backend(cfg) == "webcam"
    monkeypatch.setattr(camera.importlib.util, "find_spec", lambda name: object())
    assert camera.pick_backend(cfg) == "picamera"


def test_webcam_photo_is_saved_and_camera_released(cam_cfg, tmp_path, monkeypatch):
    FakeWebcam.released = False
    monkeypatch.setattr(camera.cv2, "VideoCapture", FakeWebcam)
    path = camera.capture_photo(cam_cfg, tmp_path / "captures")
    assert path.suffix == ".jpg" and cv2.imread(str(path)).shape == (20, 40, 3)
    assert FakeWebcam.released


def test_rotate_turns_the_photo(cam_cfg, tmp_path, monkeypatch):
    cam_cfg["camera"]["rotate"] = 90
    monkeypatch.setattr(camera.cv2, "VideoCapture", FakeWebcam)
    path = camera.capture_photo(cam_cfg, tmp_path)
    assert cv2.imread(str(path)).shape == (40, 20, 3)


def test_missing_webcam_gives_clear_error(cam_cfg, tmp_path, monkeypatch):
    FakeWebcam.released = False
    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda index: FakeWebcam(index, opened=False))
    with pytest.raises(camera.CameraError, match="Could not open webcam"):
        camera.capture_photo(cam_cfg, tmp_path)
    assert FakeWebcam.released


def test_picamera_backend_drives_picamera2(cfg, tmp_path, monkeypatch):
    """A fake picamera2 module checks the calls made to the Pi camera, in order."""
    calls = []

    class FakePicamera2:
        camera_controls = {"AfMode": None}

        def create_still_configuration(self, main):
            calls.append(("size", main["size"]))
            return "still"

        def configure(self, config):
            calls.append("configure")

        def start(self):
            calls.append("start")

        def autofocus_cycle(self):
            calls.append("focus")

        def capture_file(self, path):
            calls.append("capture")
            cv2.imwrite(path, np.zeros((20, 40, 3), dtype=np.uint8))

        def close(self):
            calls.append("close")

    monkeypatch.setitem(sys.modules, "picamera2", types.SimpleNamespace(Picamera2=FakePicamera2))
    cfg["camera"].update(backend="picamera", warmup_seconds=0, width=800, height=600)
    path = camera.capture_photo(cfg, tmp_path)
    assert path.exists()
    assert calls == [("size", (800, 600)), "configure", "start", "focus", "capture", "close"]


def test_picamera_backend_off_a_pi_gives_clear_error(cfg, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)  # makes `import picamera2` fail
    cfg["camera"]["backend"] = "picamera"
    with pytest.raises(camera.CameraError, match="only exists on a Raspberry Pi"):
        camera.capture_photo(cfg, tmp_path)
