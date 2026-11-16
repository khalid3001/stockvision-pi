"""Inference: image or video in, per-class counts + confidences + boxes out.

detect() returns a plain dict (JSON-friendly):
    source            path of the input file
    kind              "image" or "video"
    count_method      "image", "track" or "peak"
    counts            {class_name: count} for every class in config.yaml
    avg_confidence    {class_name: mean confidence, or None when nothing was found}
    detections        [{class_name, confidence, box: [x1, y1, x2, y2]}] for the evidence image
    annotated_path    evidence image with boxes drawn
    frames_processed  1 for images
"""
from pathlib import Path

import cv2

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

# BGR colours, one per class in config order
COLOURS = [(40, 160, 40), (200, 120, 0), (30, 30, 220), (160, 40, 160), (0, 160, 200)]


def kind_of(path) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    raise ValueError(f"Unsupported file type '{ext}'. Use an image {sorted(IMAGE_EXTS)} or video {sorted(VIDEO_EXTS)}.")


def load_model(cfg: dict):
    """Load YOLO weights and check the model knows every class in the config."""
    weights = Path(cfg["model"]["weights"])
    if not weights.exists():
        raise FileNotFoundError(
            f"Weights file not found: {weights}\n"
            "Train with notebooks/train_colab.ipynb and put best.pt in the weights/ folder."
        )
    from ultralytics import YOLO  # imported here so the rest of the project works without torch

    model = YOLO(str(weights))
    model_classes = set(model.names.values())
    unknown = [c for c in cfg["classes"] if c not in model_classes]
    if unknown:
        raise ValueError(
            f"config.yaml lists class(es) {unknown} that this model was not trained on.\n"
            f"The model knows: {sorted(model_classes)}. Fix the 'classes' block in config.yaml."
        )
    return model


def detect(source, cfg: dict, out_dir, model=None) -> dict:
    """Run detection on one image or video and save an annotated evidence image in out_dir."""
    source = Path(source)
    kind = kind_of(source)
    if model is None:
        model = load_model(cfg)
    if kind == "image":
        image = cv2.imread(str(source))
        if image is None:
            raise ValueError(f"Could not read image: {source}")
        detections = _detect_image(model, image, cfg)
        counts = count_by_class(detections, cfg)
        confidence = mean_confidence(detections, cfg)
        method, frames = "image", 1
    else:
        image, detections, counts, confidence, method, frames = _detect_video(model, source, cfg)
    return build_result(source, kind, method, counts, confidence, detections, image, frames, cfg, out_dir)


def build_result(source, kind, method, counts, confidence, detections, image, frames, cfg, out_dir) -> dict:
    """Draw the evidence image and assemble the result dict (also used by the stub detector)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = out_dir / "annotated.jpg"
    cv2.imwrite(str(annotated_path), draw_boxes(image, detections, cfg))
    return {
        "source": str(source),
        "kind": kind,
        "count_method": method,
        "counts": counts,
        "avg_confidence": confidence,
        "detections": detections,
        "annotated_path": str(annotated_path),
        "frames_processed": frames,
    }


def count_by_class(detections: list, cfg: dict) -> dict:
    counts = {name: 0 for name in cfg["classes"]}
    for d in detections:
        counts[d["class_name"]] += 1
    return counts


def mean_confidence(detections: list, cfg: dict) -> dict:
    result = {}
    for name in cfg["classes"]:
        confs = [d["confidence"] for d in detections if d["class_name"] == name]
        result[name] = round(sum(confs) / len(confs), 3) if confs else None
    return result


def draw_boxes(image, detections: list, cfg: dict):
    """Return a copy of the image with one labelled box per detection."""
    out = image.copy()
    names = list(cfg["classes"])
    thickness = max(2, round(min(out.shape[:2]) / 400))
    scale = max(0.5, min(out.shape[:2]) / 1200)
    for d in detections:
        colour = COLOURS[names.index(d["class_name"]) % len(COLOURS)]
        x1, y1, x2, y2 = (int(v) for v in d["box"])
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, thickness)
        label = f"{cfg['classes'][d['class_name']]['display_name']} {d['confidence']:.2f}"
        cv2.putText(out, label, (x1, max(y1 - 6, 15)), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, thickness)
    return out


# ---- Tiling: scan a large photo in overlapping pieces --------------------------
#
# The model looks at 640 px images. A 12-megapixel shelf photo squeezed down to 640 px turns
# each small item into a few pixels and most are missed. So a large photo is cut into
# overlapping tiles, each tile is scanned at full detail, and the results are stitched together.

def tile_origins(width: int, height: int, size: int, overlap: float) -> list:
    """Top-left (x, y) of each tile so the tiles cover the whole image, overlapping by `overlap`."""
    step = max(1, int(size * (1 - overlap)))

    def starts(length):
        if length <= size:
            return [0]
        positions = list(range(0, length - size, step))
        positions.append(length - size)  # last tile sits flush against the edge
        return positions

    return [(x, y) for y in starts(height) for x in starts(width)]


def merge_detections(detections: list, threshold: float = 0.5) -> list:
    """Remove duplicates of the same item found in more than one tile.

    Two boxes of the same class are the same item when their overlap covers more than
    `threshold` of the SMALLER box. Measuring against the smaller box (not plain IoU) is what
    catches an item cut in half by a tile edge: the half box sits inside the whole box.
    The higher-confidence box is kept.
    """
    kept = []
    for d in sorted(detections, key=lambda d: d["confidence"], reverse=True):
        if not any(k["class_name"] == d["class_name"] and _overlap_of_smaller(k["box"], d["box"]) > threshold
                   for k in kept):
            kept.append(d)
    return kept


def _overlap_of_smaller(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (w * h) / smaller if smaller > 0 else 0.0


def _detect_image(model, image, cfg: dict) -> list:
    """Detections for one image: whole-image pass, plus a tiled pass when the photo is large."""
    m = cfg["model"]
    size = m.get("tile_size") or m["image_size"]
    height, width = image.shape[:2]
    detections = _parse(_predict(model, image, cfg), cfg)  # catches items bigger than one tile
    tiling = m.get("tiling", True)
    if not tiling or max(width, height) <= size * 1.25:
        return detections
    allowed = None
    if tiling == "auto":
        if not needs_tiling(detections, width, height, m):
            return detections
        allowed = main_classes(detections)
    for x, y in tile_origins(width, height, size, m.get("tile_overlap", 0.2)):
        for d in _parse(_predict(model, image[y:y + size, x:x + size], cfg), cfg):
            if allowed and d["class_name"] not in allowed:
                continue  # a cropped tile can look like another product; trust the whole-photo view
            d["box"] = [d["box"][0] + x, d["box"][1] + y, d["box"][2] + x, d["box"][3] + y]
            detections.append(d)
    if allowed:
        detections = [d for d in detections if d["class_name"] in allowed]
    return merge_detections(detections)


def needs_tiling(detections: list, width: int, height: int, m: dict) -> bool:
    """tiling: auto. Tile only when the items are small once the photo is shrunk to the model size.

    Large items (cement bags) are counted best in one pass; tiling them adds duplicates.
    Small items (tube ends in a big stack) are lost in one pass and need the tiles.
    """
    if not detections:
        return True  # nothing seen in the shrunk photo: the items may simply be too small
    scale = m["image_size"] / max(width, height)
    sides = sorted(min(d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]) * scale for d in detections)
    return sides[len(sides) // 2] < m.get("small_item_px", 40)


def main_classes(detections: list, share: float = 0.2) -> set:
    """Classes that make up at least `share` of the whole-photo detections (empty set = no filter)."""
    totals = {}
    for d in detections:
        totals[d["class_name"]] = totals.get(d["class_name"], 0) + 1
    return {name for name, n in totals.items() if n >= share * len(detections)}


# ---- YOLO-specific code below ------------------------------------------------

def _model_args(cfg: dict) -> dict:
    m = cfg["model"]
    return {"conf": m["confidence"], "iou": m["iou"], "imgsz": m["image_size"],
            "device": m["device"], "verbose": False,
            "max_det": m.get("max_detections", 1000)}  # Ultralytics stops at 300 by default; dense stacks exceed it


def _predict(model, image, cfg):
    return model.predict(image, **_model_args(cfg))[0]


def _parse(result, cfg: dict) -> list:
    """Ultralytics result -> list of detection dicts, keeping only classes named in the config."""
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(boxes)
    detections = []
    for cls_index, conf, xyxy, track_id in zip(
        boxes.cls.int().tolist(), boxes.conf.tolist(), boxes.xyxy.tolist(), ids
    ):
        name = result.names[cls_index]
        if name not in cfg["classes"]:
            continue
        det = {"class_name": name, "confidence": round(float(conf), 3),
               "box": [round(float(v), 1) for v in xyxy]}
        if track_id is not None:
            det["track_id"] = track_id
        detections.append(det)
    return detections


def _detect_video(model, source: Path, cfg: dict):
    """Count items in a video.

    track mode: ByteTrack gives each physical item an id; an item counts once it has been
                seen in `min_track_frames` processed frames. Stops double counting while panning.
    peak mode:  the counts of the single frame with the most detections (fixed camera).
    The evidence image is always the frame with the most detections.
    """
    video = cfg["video"]
    mode, stride, min_frames = video["mode"], video["frame_stride"], video["min_track_frames"]
    if mode == "track":
        # A fresh model per video so track ids from a previous video do not carry over.
        model = load_model(cfg)

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {source}")

    tracks = {}  # (class_name, track_id) -> {"frames": n, "conf_sum": x}
    best_frame, best_detections = None, []
    index = processed = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if index % stride == 0:
            if mode == "track":
                result = model.track(frame, persist=True, tracker="bytetrack.yaml", **_model_args(cfg))[0]
            else:
                result = _predict(model, frame, cfg)
            detections = _parse(result, cfg)
            processed += 1
            for d in detections:
                if "track_id" in d:
                    t = tracks.setdefault((d["class_name"], d["track_id"]), {"frames": 0, "conf_sum": 0.0})
                    t["frames"] += 1
                    t["conf_sum"] += d["confidence"]
            if best_frame is None or len(detections) > len(best_detections):
                best_frame, best_detections = frame.copy(), detections
        index += 1
    cap.release()
    if best_frame is None:
        raise ValueError(f"Video has no readable frames: {source}")

    confirmed = {k: t for k, t in tracks.items() if t["frames"] >= min_frames}
    if mode == "track" and confirmed:
        counts = {name: 0 for name in cfg["classes"]}
        conf_lists = {name: [] for name in cfg["classes"]}
        for (name, _), t in confirmed.items():
            counts[name] += 1
            conf_lists[name].append(t["conf_sum"] / t["frames"])
        confidence = {n: (round(sum(v) / len(v), 3) if v else None) for n, v in conf_lists.items()}
        return best_frame, best_detections, counts, confidence, "track", processed

    # peak mode, or tracking produced nothing usable (e.g. a very short clip)
    return (best_frame, best_detections, count_by_class(best_detections, cfg),
            mean_confidence(best_detections, cfg), "peak", processed)
