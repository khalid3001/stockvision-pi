"""Run detection only and print the counts.

Usage: python scripts/infer.py <image | video | folder>
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import inference
from src.config import load_config


def find_sources(path: Path) -> list:
    if path.is_dir():
        exts = inference.IMAGE_EXTS | inference.VIDEO_EXTS
        return sorted(p for p in path.iterdir() if p.suffix.lower() in exts)
    return [path]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cfg = load_config()
    sources = find_sources(Path(sys.argv[1]))
    if not sources:
        sys.exit(f"No images or videos found in {sys.argv[1]}")
    model = inference.load_model(cfg)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for i, source in enumerate(sources, 1):
        out_dir = Path(cfg["output"]["dir"]) / f"infer-{stamp}-{i:02d}"
        result = inference.detect(source, cfg, out_dir, model=model)
        print(f"\n{source.name}  ({result['count_method']}, {result['frames_processed']} frame(s))")
        for name, count in result["counts"].items():
            conf = result["avg_confidence"][name]
            conf_text = f"avg confidence {conf:.2f}" if conf is not None else "none found"
            print(f"  {cfg['classes'][name]['display_name']:<25} {count:>4}   {conf_text}")
        print(f"  evidence image: {result['annotated_path']}")


if __name__ == "__main__":
    main()
