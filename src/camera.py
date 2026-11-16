"""Take a photo with the camera attached to this computer.

Backends (config.yaml -> camera.backend):
    picamera  the Raspberry Pi camera, through the picamera2 library (only exists on a Raspberry Pi)
    webcam    any built-in or USB camera, through OpenCV (laptop development, or a USB camera on a Pi)
    auto      picamera when picamera2 is installed, otherwise webcam

The same code therefore runs on a laptop (webcam stands in for the Pi camera) and on the Pi.
"""
import importlib.util
import time
from datetime import datetime
from pathlib import Path

import cv2

BACKENDS = ("auto", "picamera", "webcam")
BACKEND_LABELS = {"picamera": "Raspberry Pi camera", "webcam": "Webcam"}
ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


class CameraError(RuntimeError):
    """The camera could not be opened or gave no picture."""


def pick_backend(cfg: dict) -> str:
    """The backend that will be used: 'picamera' or 'webcam'."""
    backend = cfg["camera"]["backend"]
    if backend != "auto":
        return backend
    return "picamera" if importlib.util.find_spec("picamera2") else "webcam"


def capture_photo(cfg: dict, out_dir) -> Path:
    """Take one photo, save it as a JPEG in out_dir and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"capture-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
    backend = pick_backend(cfg)
    if backend == "picamera":
        _capture_picamera(cfg["camera"], path)
    else:
        _capture_webcam(cfg["camera"], path)
    _rotate(path, cfg["camera"]["rotate"])
    return path


def _capture_picamera(cam_cfg: dict, path: Path) -> None:
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
        cam.configure(cam.create_still_configuration(main={"size": (cam_cfg["width"], cam_cfg["height"])}))
        cam.start()
        time.sleep(cam_cfg["warmup_seconds"])  # lets exposure and white balance settle
        if cam_cfg["autofocus"] and "AfMode" in cam.camera_controls:  # Camera Module 3 only
            try:
                cam.autofocus_cycle()
            except Exception:
                pass  # a failed focus run should not lose the photo
        cam.capture_file(str(path))
    except Exception as error:
        raise CameraError(f"The Raspberry Pi camera failed to take a photo: {error}") from error
    finally:
        cam.close()


def _capture_webcam(cam_cfg: dict, path: Path) -> None:
    cap = cv2.VideoCapture(cam_cfg["webcam_index"])
    try:
        if not cap.isOpened():
            raise CameraError(
                f"Could not open webcam {cam_cfg['webcam_index']}. Is a camera connected, "
                "and is another program (Teams, Zoom, the browser) using it? "
                "The hosted website has no camera of its own: use the upload or phone camera tab there.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["width"])   # the webcam picks its nearest supported size
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["height"])
        frame = None
        deadline = time.monotonic() + cam_cfg["warmup_seconds"]
        while True:  # the first frames of a webcam are dark; keep the last one after the warm-up
            ok, latest = cap.read()
            if ok:
                frame = latest
            if time.monotonic() >= deadline:
                break
        if frame is None:
            raise CameraError("The webcam opened but returned no picture.")
        cv2.imwrite(str(path), frame)
    finally:
        cap.release()


def _rotate(path: Path, degrees: int) -> None:
    """Turn the saved photo, for a camera that is mounted sideways or upside down."""
    if degrees in ROTATIONS:
        cv2.imwrite(str(path), cv2.rotate(cv2.imread(str(path)), ROTATIONS[degrees]))
