"""Upload the images in data/roboflow_upload to a Roboflow object-detection project.

Run it yourself; it reads ROBOFLOW_API_KEY from your environment or from .env and never prints it.

    pip install roboflow
    python scripts/upload_roboflow.py --project stockvision-pilot --dry-run   # list what would be sent
    python scripts/upload_roboflow.py --project stockvision-pilot              # create project if needed, upload

Auto-labelling (Label Assist) is done afterwards in the Roboflow web app; the API does not offer it.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_key() -> str:
    key = os.environ.get("ROBOFLOW_API_KEY", "")
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ROBOFLOW_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key or key == "your_key_here":
        sys.exit("ROBOFLOW_API_KEY is not set (environment or .env).")
    return key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="Roboflow project id, e.g. stockvision-pilot")
    ap.add_argument("--folder", default=str(ROOT / "data" / "roboflow_upload"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    images = sorted(p for p in Path(args.folder).glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        sys.exit(f"No images in {args.folder}")
    print(f"{len(images)} images:")
    for p in images:
        print("  ", p.name)
    if args.dry_run:
        return

    from roboflow import Roboflow

    ws = Roboflow(api_key=load_key()).workspace()
    print("Workspace:", ws.url)
    try:
        project = ws.project(args.project)
        print("Using existing project:", args.project)
    except Exception:
        project = ws.create_project(
            project_name=args.project,
            project_type="object-detection",
            project_license="Private",
            annotation="objects",
        )
        print("Created project:", args.project)

    for p in images:
        project.upload(str(p), batch_name="batch1_16nov")
        print("uploaded", p.name)
    print(f"Done. Open the project in Roboflow, then use Label Assist and review the boxes.")


if __name__ == "__main__":
    main()
