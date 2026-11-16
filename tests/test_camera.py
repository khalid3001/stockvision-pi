import sys
import time
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
def cam_cfg(cfg, monkeypatch):
    """Config for a fake webcam; the shared stream is closed again after each test."""
    cfg["camera"].update(backend="webcam", warmup_seconds=0)
    FakeWebcam.released = False
    monkeypatch.setattr(camera.cv2, "VideoCapture", FakeWebcam)
    yield cfg
    camera.close_stream()


def _rewrite_config(tmp_path, change):
    raw = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    change(raw)
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return tmp_path / "config.yaml"


def test_camera_section_is_optional(tmp_path, cfg):
    path = _rewrite_config(tmp_path, lambda raw: raw.pop("camera"))
    assert load_config(path)["camera"]["backend"] == "auto"


def test_unknown_backend_rejected(tmp_path, cfg):
    path = _rewrite_config(tmp_path, lambda raw: raw["camera"].update(backend="telescope"))
    with pytest.raises(ConfigError):
        load_config(path)


def test_auto_backend_follows_picamera2(cfg, monkeypatch):
    cfg["camera"]["backend"] = "auto"
    monkeypatch.setattr(camera.importlib.util, "find_spec", lambda name: None)
    assert camera.pick_backend(cfg) == "webcam"
    monkeypatch.setattr(camera.importlib.util, "find_spec", lambda name: object())
    assert camera.pick_backend(cfg) == "picamera"


def test_one_shot_photo_is_saved_and_camera_released(cam_cfg, tmp_path):
    path = camera.capture_photo(cam_cfg, tmp_path / "captures")
    assert path.suffix == ".jpg" and cv2.imread(str(path)).shape == (20, 40, 3)
    assert FakeWebcam.released and camera.current_stream() is None


def test_stream_gives_preview_pictures_then_saves_what_it_shows(cam_cfg, tmp_path):
    stream = camera.get_stream(cam_cfg)
    assert camera.get_stream(cam_cfg) is stream            # one camera, one shared stream
    assert stream.read().shape == (20, 40, 3)              # a preview picture
    assert not FakeWebcam.released                         # the camera stays open between pictures
    assert cv2.imread(str(stream.save_photo(tmp_path))).shape == (20, 40, 3)
    camera.close_stream()
    assert FakeWebcam.released and camera.current_stream() is None
    with pytest.raises(camera.CameraError):
        stream.read()


def test_rotate_turns_preview_and_photo(cam_cfg, tmp_path):
    cam_cfg["camera"]["rotate"] = 90
    stream = camera.get_stream(cam_cfg)
    assert stream.read().shape == (40, 20, 3)
    assert cv2.imread(str(stream.save_photo(tmp_path))).shape == (40, 20, 3)


def test_unwatched_camera_switches_itself_off(cam_cfg):
    cam_cfg["camera"]["idle_seconds"] = 0.1
    stream = camera.get_stream(cam_cfg)
    stream.read()
    time.sleep(0.6)  # nobody asks for a picture
    assert not stream.is_open and FakeWebcam.released and camera.current_stream() is None
    with pytest.raises(camera.CameraError, match="not used for a while"):
        stream.read()


def test_missing_webcam_gives_clear_error(cam_cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda index: FakeWebcam(index, opened=False))
    with pytest.raises(camera.CameraError, match="Could not open webcam"):
        camera.capture_photo(cam_cfg, tmp_path)
    assert FakeWebcam.released


def test_shrink_keeps_shape_ratio():
    assert camera.shrink(np.zeros((1080, 1920, 3), dtype=np.uint8), 960).shape == (540, 960, 3)
    assert camera.shrink(np.zeros((20, 40, 3), dtype=np.uint8), 960).shape == (20, 40, 3)


def test_picamera_backend_drives_picamera2(cfg, tmp_path, monkeypatch):
    """A fake picamera2 module checks the calls made to the Pi camera, in order."""
    calls = []

    class FakePicamera2:
        camera_controls = {"AfMode": None}

        def create_still_configuration(self, main):
            calls.append(("config", main["size"], main["format"]))
            return "still"

        def configure(self, config):
            calls.append("configure")

        def start(self):
            calls.append("start")

        def set_controls(self, controls):
            calls.append(("controls", controls))

        def capture_array(self):
            return np.zeros((20, 40, 3), dtype=np.uint8)

        def close(self):
            calls.append("close")

    monkeypatch.setitem(sys.modules, "picamera2", types.SimpleNamespace(Picamera2=FakePicamera2))
    cfg["camera"].update(backend="picamera", warmup_seconds=0, width=800, height=600)
    path = camera.capture_photo(cfg, tmp_path)
    assert cv2.imread(str(path)).shape == (20, 40, 3)
    assert calls == [("config", (800, 600), "RGB888"), "configure", "start",
                     ("controls", {"AfMode": camera.AF_CONTINUOUS}), "close"]


def test_picamera_backend_off_a_pi_gives_clear_error(cfg, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)  # makes `import picamera2` fail
    cfg["camera"]["backend"] = "picamera"
    with pytest.raises(camera.CameraError, match="only exists on a Raspberry Pi"):
        camera.capture_photo(cfg, tmp_path)
