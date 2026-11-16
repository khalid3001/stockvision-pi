"""Take a photo with the attached camera (Raspberry Pi camera or webcam) and verify the stock in it.

Usage:
    python scripts/capture.py                 one photo, counted and compared with the inventory
    python scripts/capture.py --every 30      the same every 30 minutes until stopped (fixed camera)
    python scripts/capture.py --photo-only    only save the photo (collecting training pictures)

Photos are saved in outputs/captures. Every verification also appears in the dashboard's History tab.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import camera, inference, pipeline
from src.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Capture a photo and verify the stock in it.")
    parser.add_argument("--every", type=float, metavar="MINUTES",
                        help="repeat every MINUTES minutes until stopped with Ctrl+C")
    parser.add_argument("--photo-only", action="store_true", help="save the photo without counting")
    args = parser.parse_args()

    cfg = load_config()
    capture_dir = Path(cfg["output"]["dir"]) / "captures"
    print(f"Camera: {camera.BACKEND_LABELS[camera.pick_backend(cfg)]}")
    model = None if args.photo_only else inference.load_model(cfg)

    try:
        while True:
            try:
                run_once(cfg, capture_dir, model)
            except camera.CameraError as error:
                if not args.every:
                    sys.exit(f"Camera error: {error}")
                print(f"Camera error, will try again next time: {error}")
            if not args.every:
                break
            time.sleep(args.every * 60)
    except KeyboardInterrupt:
        print("\nStopped.")


def run_once(cfg: dict, capture_dir: Path, model) -> None:
    photo = camera.capture_photo(cfg, capture_dir)
    print(f"\n{time.strftime('%H:%M:%S')}  photo saved: {photo}")
    if model is None:
        return
    started = time.monotonic()
    run = pipeline.run_verification(
        photo, cfg, detector=lambda s, c, out: inference.detect(s, c, out, model=model))
    print(f"  counted in {time.monotonic() - started:.1f} s")
    for row in run["rows"]:
        recorded = "-" if row["recorded"] is None else row["recorded"]
        print(f"  {row['item_name']:<25} detected {row['detected']:>4}   recorded {recorded:>4}   {row['status']}")
    print(f"  evidence image: {run['annotated_path']}")


if __name__ == "__main__":
    main()
