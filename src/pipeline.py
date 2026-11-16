"""Glue: capture -> identify -> count -> compare -> save. Used by the dashboard and the demo script.

Each run gets its own folder under the output dir:
    outputs/run-YYYYMMDD-HHMMSS/annotated.jpg, results.csv, run.json
"""
import csv
import json
from datetime import datetime
from pathlib import Path

from src import comparison, inference, inventory

RESULT_COLUMNS = ["sku", "item_name", "location", "detected", "recorded",
                  "variance", "variance_pct", "confidence", "status"]


def run_verification(source, cfg: dict, detector=None) -> dict:
    """Run the whole pipeline on one image or video and return the run dict.

    detector: a function (source, cfg, out_dir) -> detection dict. Defaults to the real
              YOLO detector; tests and the stub demo pass stub_detector.detect.
    """
    detector = detector or inference.detect
    now = datetime.now()
    run_dir = _new_run_dir(Path(cfg["output"]["dir"]), now)

    detection = detector(source, cfg, run_dir)

    inventory.ensure_db(cfg)
    db = cfg["inventory"]["database"]
    records = inventory.get_records(db)
    rows = comparison.compare(detection["counts"], cfg, records, detection["avg_confidence"])

    run = {
        "run_id": run_dir.name,
        "run_at": now.isoformat(timespec="seconds"),
        "source": str(source),
        "source_name": Path(source).name,
        "kind": detection["kind"],
        "count_method": detection["count_method"],
        "frames_processed": detection["frames_processed"],
        "annotated_path": detection["annotated_path"],
        "rows": rows,
        "summary": comparison.summarise(rows),
        "detections": detection["detections"],
    }
    (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    inventory.save_verification(db, run["run_id"], run["run_at"], run["source_name"], rows)
    return run


def list_runs(cfg: dict) -> list:
    """All saved runs, oldest first."""
    out = Path(cfg["output"]["dir"])
    runs = []
    for path in sorted(out.glob("run-*/run.json")):
        runs.append(json.loads(path.read_text(encoding="utf-8")))
    return runs


def _new_run_dir(out: Path, now: datetime) -> Path:
    base = out / f"run-{now.strftime('%Y%m%d-%H%M%S')}"
    run_dir, n = base, 1
    while run_dir.exists():
        n += 1
        run_dir = base.with_name(f"{base.name}-{n}")
    run_dir.mkdir(parents=True)
    return run_dir
