"""Tests for the parts of inference that do not need a YOLO model."""
from pathlib import Path

import cv2
import pytest

from src import inference, inventory, stub_detector

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "samples" / "placeholder_shelf.jpg"


def test_kind_of():
    assert inference.kind_of("a.JPG") == "image"
    assert inference.kind_of("b.mp4") == "video"
    with pytest.raises(ValueError):
        inference.kind_of("c.pdf")


def test_counts_and_confidence(cfg):
    names = list(cfg["classes"])
    dets = [{"class_name": names[0], "confidence": 0.8, "box": [0, 0, 10, 10]},
            {"class_name": names[0], "confidence": 0.6, "box": [5, 5, 20, 20]}]
    expected = {n: 0 for n in names}
    expected[names[0]] = 2
    assert inference.count_by_class(dets, cfg) == expected
    conf = inference.mean_confidence(dets, cfg)
    assert conf[names[0]] == 0.7
    assert all(conf[n] is None for n in names[1:])


def test_tiles_cover_the_whole_image():
    assert inference.tile_origins(600, 400, 640, 0.2) == [(0, 0)]  # small image: one tile
    origins = inference.tile_origins(2000, 1300, 640, 0.2)
    assert max(x for x, _ in origins) == 2000 - 640  # reaches the right edge
    assert max(y for _, y in origins) == 1300 - 640  # reaches the bottom edge
    xs = sorted({x for x, _ in origins})
    assert all(b - a <= 512 for a, b in zip(xs, xs[1:]))  # neighbours overlap, no gaps


def test_merge_removes_item_seen_in_two_tiles():
    whole = {"class_name": "a", "confidence": 0.9, "box": [100, 100, 200, 200]}
    half = {"class_name": "a", "confidence": 0.5, "box": [100, 100, 150, 200]}   # cut by a tile edge
    neighbour = {"class_name": "a", "confidence": 0.8, "box": [195, 100, 295, 200]}  # separate item
    other_class = {"class_name": "b", "confidence": 0.7, "box": [100, 100, 200, 200]}
    merged = inference.merge_detections([half, neighbour, whole, other_class])
    assert merged == [whole, neighbour, other_class]


def test_auto_tiling_only_for_small_items():
    m = {"image_size": 640, "small_item_px": 40}
    box = lambda side: {"class_name": "a", "confidence": 0.9, "box": [0, 0, side, side]}
    assert inference.needs_tiling([], 2000, 1000, m)                 # nothing seen: try tiles
    assert inference.needs_tiling([box(60)] * 5, 2000, 1000, m)      # 60 px shrinks to 19 px: small
    assert not inference.needs_tiling([box(300)] * 5, 2000, 1000, m)  # 300 px shrinks to 96 px: large


def test_main_classes_drops_rare_ones():
    dets = [{"class_name": "tube"}] * 9 + [{"class_name": "pipe"}]
    assert inference.main_classes(dets) == {"tube"}
    assert inference.main_classes([]) == set()


def test_missing_weights_gives_clear_error(cfg):
    cfg["model"]["weights"] = str(Path(cfg["model"]["weights"]).with_name("does_not_exist.pt"))
    with pytest.raises(FileNotFoundError, match="best.pt"):
        inference.load_model(cfg)


def test_stub_detector_writes_evidence_image(cfg, tmp_path):
    inventory.ensure_db(cfg)
    records = inventory.get_records(cfg["inventory"]["database"])
    result = stub_detector.detect(SAMPLE, cfg, tmp_path / "run")
    for i, (name, info) in enumerate(cfg["classes"].items()):
        recorded = records.get(info["sku"], {"recorded_qty": 10})["recorded_qty"]
        assert result["counts"][name] == [recorded, max(recorded - 2, 0), 0][i % 3]
    assert cv2.imread(result["annotated_path"]) is not None
