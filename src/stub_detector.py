"""A fake detector with the same interface as inference.detect().

It needs no model and no torch. It exists so the rest of the pipeline (comparison, database,
report, dashboard) can be tested and shown before trained weights are available.
The counts are invented: never present stub output as a real result.
"""
import random
from pathlib import Path

import cv2

from src import inference


def detect(source, cfg: dict, out_dir, model=None) -> dict:
    source = Path(source)
    kind = inference.kind_of(source)
    if kind == "image":
        image = cv2.imread(str(source))
    else:
        cap = cv2.VideoCapture(str(source))
        ok, image = cap.read()
        cap.release()
        image = image if ok else None
    if image is None:
        raise ValueError(f"Could not read: {source}")

    records = _recorded_quantities(cfg)
    rng = random.Random(source.name)  # same file -> same fake result
    height, width = image.shape[:2]
    detections = []
    for i, name in enumerate(cfg["classes"]):
        recorded = records.get(cfg["classes"][name]["sku"], 10)
        # first class matches, second is a little short, third finds nothing, then repeat
        count = [recorded, max(recorded - 2, 0), 0][i % 3]
        for _ in range(count):
            w, h = int(width * 0.06), int(height * 0.08)
            x, y = rng.randint(0, width - w - 1), rng.randint(20, height - h - 1)
            detections.append({"class_name": name, "confidence": round(rng.uniform(0.55, 0.95), 3),
                               "box": [x, y, x + w, y + h]})

    cv2.putText(image, "STUB DETECTOR - FAKE COUNTS", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    return inference.build_result(
        source, kind, "stub", inference.count_by_class(detections, cfg),
        inference.mean_confidence(detections, cfg), detections, image, 1, cfg, out_dir,
    )


def _recorded_quantities(cfg: dict) -> dict:
    from src import inventory

    inventory.ensure_db(cfg)
    return {sku: r["recorded_qty"] for sku, r in inventory.get_records(cfg["inventory"]["database"]).items()}
