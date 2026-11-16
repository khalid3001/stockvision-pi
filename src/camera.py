"""The camera attached to this computer: live preview and photos.

Backends (config.yaml -> camera.backend):
    picamera  the Raspberry Pi camera, through the picamera2 library (only exists on a Raspberry Pi)
    webcam    any built-in or USB camera, through OpenCV (laptop development, or a USB camera on a Pi)
    auto      picamera when picamera2 is installed, otherwise webcam

The same code therefore runs on a laptop (webcam stands in for the Pi camera) and on the Pi.

A CameraStream keeps the camera open and always holds the newest picture, so the dashboard can show
a live preview and save exactly what the preview shows. capture_photo() is the one-shot version
used by scripts/capture.py.
"""
import importlib.util
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

BACKENDS = ("auto", "picamera", "webcam")
BACKEND_LABELS = {"picamera": "Raspberry Pi camera", "webcam": "Webcam"}
ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
AF_CONTINUOUS = 2  # libcamera's AfModeEnum.Continuous: keep refocusing while the preview runs


class CameraError(RuntimeError):
    """The camera could not be opened or gave no picture."""


def pick_backend(cfg: dict) -> str:
    """The backend that will be used: 'picamera' or 'webcam'."""
    backend = cfg["camera"]["backend"]
    if backend != "auto":
        return backend
    return "picamera" if importlib.util.find_spec("picamera2") else "webcam"


class CameraStream:
    """An open camera. A background thread keeps reading it so read() always returns the newest picture.

    The stream closes itself when nobody has asked for a picture for camera.idle_seconds, so a
    browser tab that is closed without pressing "Close camera" does not leave the camera on.
    """

    def __init__(self, cfg: dict):
        self._cfg = cfg["camera"]
        self.backend = pick_backend(cfg)
        self._lock = threading.Lock()
        self._frame = None
        self._error = None
        self._stop = threading.Event()
        self._last_used = time.monotonic()
        self._device = self._open_picamera() if self.backend == "picamera" else self._open_webcam()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def is_open(self) -> bool:
        return not self._stop.is_set()

    def read(self, timeout: float = 8.0):
        """The newest picture as an OpenCV image (BGR), already rotated."""
        self._last_used = time.monotonic()
        deadline = self._last_used + timeout
        while True:
            if self._stop.is_set():
                raise CameraError(self._error or "The camera is closed.")
            with self._lock:
                frame = self._frame
            if frame is not None:
                break
            if time.monotonic() > deadline:
                raise CameraError("The camera opened but returned no picture.")
            time.sleep(0.05)
        rotation = ROTATIONS.get(self._cfg["rotate"])
        return cv2.rotate(frame, rotation) if rotation is not None else frame.copy()

    def save_photo(self, out_dir) -> Path:
        """Save the newest picture as a JPEG in out_dir and return its path."""
        frame = self.read()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"capture-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
        cv2.imwrite(str(path), frame)
        return path

    def close(self) -> None:
        self._stop.set()
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=5)

    # ---- background thread -----------------------------------------------------

    def _run(self) -> None:
        failures = 0
        try:
            while not self._stop.is_set():
                frame = self._grab()
                if frame is None:
                    failures += 1
                    if failures > 40:
                        self._error = "The camera stopped sending pictures."
                        break
                else:
                    failures = 0
                    with self._lock:
                        self._frame = frame
                if time.monotonic() - self._last_used > self._cfg["idle_seconds"]:
                    self._error = "The camera was closed because it was not used for a while."
                    break
                time.sleep(0.02)
        except Exception as error:  # a camera unplugged mid-stream must not kill the app
            self._error = f"The camera failed: {error}"
        finally:
            self._stop.set()
            self._release()

    def _grab(self):
        if self.backend == "picamera":
            return self._device.capture_array()
        ok, frame = self._device.read()
        return frame if ok else None

    def _release(self) -> None:
        try:
            self._device.close() if self.backend == "picamera" else self._device.release()
        except Exception:
            pass

    # ---- opening each kind of camera ---------------------------------------------

    def _open_webcam(self):
        cap = cv2.VideoCapture(self._cfg["webcam_index"])
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Could not open webcam {self._cfg['webcam_index']}. Is a camera connected, "
                "and is another program (Teams, Zoom, the browser) using it? "
                "The hosted website has no camera of its own: use the upload or phone camera tab there.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cfg["width"])   # the webcam picks its nearest supported size
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cfg["height"])
        return cap

    def _open_picamera(self):
        try:
            from picamera2 import Picamera2  # installed with Raspberry Pi OS, not available elsewhere
        except ImportError as error:
            raise CameraError(
                "The picamera2 library is not installed. It only exists on a Raspberry Pi "
                "(sudo apt install python3-picamera2). On a laptop set camera.backend to 'webcam' or 'auto'."
            ) from error
        try:
            cam = Picamera2()
        except Exception as error:
            raise CameraError(f"No Raspberry Pi camera found. Check the ribbon cable. ({error})") from error
        try:
            # picamera2's "RGB888" format gives pixels in blue-green-red order, which is what OpenCV expects.
            cam.configure(cam.create_still_configuration(
                main={"size": (self._cfg["width"], self._cfg["height"]), "format": "RGB888"}))
            cam.start()
            if self._cfg["autofocus"] and "AfMode" in cam.camera_controls:  # Camera Module 3 only
                cam.set_controls({"AfMode": AF_CONTINUOUS})
        except Exception as error:
            cam.close()
            raise CameraError(f"The Raspberry Pi camera failed to start: {error}") from error
        return cam


# ---- one shared stream per program -------------------------------------------------
# A camera can only be opened once, so the dashboard's browser sessions share a single stream.

_shared = None
_shared_lock = threading.Lock()


def current_stream():
    """The shared stream if it is open, otherwise None. Never opens the camera."""
    return _shared if _shared is not None and _shared.is_open else None


def get_stream(cfg: dict) -> CameraStream:
    """The shared stream, opening the camera if it is not open yet."""
    global _shared
    with _shared_lock:
        if _shared is None or not _shared.is_open:
            _shared = CameraStream(cfg)
        return _shared


def close_stream() -> None:
    """Close the shared stream and release the camera."""
    global _shared
    with _shared_lock:
        if _shared is not None:
            _shared.close()
            _shared = None


def capture_photo(cfg: dict, out_dir) -> Path:
    """Take one photo without a preview: open the camera, let it settle, save, close."""
    was_open = current_stream() is not None
    stream = get_stream(cfg)
    try:
        if not was_open:
            stream.read()                               # wait for the first picture
            time.sleep(cfg["camera"]["warmup_seconds"])  # then let brightness, colour and focus settle
        return stream.save_photo(out_dir)
    finally:
        if not was_open:
            close_stream()


def shrink(image, max_width: int = 960):
    """A smaller copy for the live preview, so each refresh sends a small picture to the browser."""
    height, width = image.shape[:2]
    if width <= max_width:
        return image
    return cv2.resize(image, (max_width, round(height * max_width / width)), interpolation=cv2.INTER_AREA)
