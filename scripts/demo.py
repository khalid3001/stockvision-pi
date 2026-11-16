"""End-to-end smoke test: capture -> identify -> count -> compare -> discrepancy report.

Usage: python scripts/demo.py           # real model (needs weights/best.pt)
       python scripts/demo.py --stub    # fake detector, no model needed
       python scripts/demo.py [--stub] path/to/folder_or_file

Exits with a non-zero code if any step fails.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import inference, inventory, pipeline, report, stub_detector
from src.config import ROOT, load_config


def main():
    args = [a for a in sys.argv[1:] if a != "--stub"]
    use_stub = "--stub" in sys.argv
    source = Path(args[0]) if args else ROOT / "data" / "samples"

    print("1/5 Loading config")
    cfg = load_config()
    print(f"    classes: {', '.join(cfg['classes'])}")

    print("2/5 Loading inventory records")
    n = inventory.init_db(cfg["inventory"]["source_csv"], cfg["inventory"]["database"])
    print(f"    {n} records")

    print("3/5 Finding input files")
    if source.is_dir():
        exts = inference.IMAGE_EXTS | inference.VIDEO_EXTS
        sources = sorted(p for p in source.iterdir() if p.suffix.lower() in exts)
    else:
        sources = [source]
    if not sources:
        sys.exit(f"    FAILED: no images or videos in {source}")
    print(f"    {len(sources)} file(s)")

    print(f"4/5 Detecting, counting and comparing ({'STUB detector' if use_stub else 'YOLO model'})")
    if use_stub:
        detector = stub_detector.detect
    else:
        try:
            model = inference.load_model(cfg)
        except (FileNotFoundError, ValueError) as error:
            sys.exit(f"    FAILED: {error}\n    To test everything except the model, add --stub")
        detector = lambda s, c, out: inference.detect(s, c, out, model=model)
    runs = []
    for path in sources:
        run = pipeline.run_verification(path, cfg, detector=detector)
        runs.append(run)
        print(f"    {path.name}")
        for r in run["rows"]:
            variance = "-" if r["variance"] is None else f"{r['variance']:+d}" if r["variance"] else "0"
            print(f"      {r['item_name']:<28} detected {r['detected']:>4}  recorded {str(r['recorded']):>4}"
                  f"  variance {variance:>4}  {report.status_label(r['status'])}")

    print("5/5 Writing discrepancy report")
    md_path, pdf_path = report.write_report(runs, cfg)
    print(f"    {md_path}\n    {pdf_path}")

    for run in runs:
        assert Path(run["annotated_path"]).exists(), "evidence image missing"
    assert md_path.exists() and pdf_path.stat().st_size > 0, "report missing"
    print("\nDEMO PASSED" + ("  (stub detector: counts are fake)" if use_stub else ""))


if __name__ == "__main__":
    main()
