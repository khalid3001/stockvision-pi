from pathlib import Path

from src import pipeline, report, stub_detector

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "samples" / "placeholder_shelf.jpg"


def test_pipeline_saves_run(cfg):
    run = pipeline.run_verification(SAMPLE, cfg, detector=stub_detector.detect)
    statuses = [r["status"] for r in run["rows"]]
    assert statuses[0] == "match"            # stub: first class matches its record
    if len(statuses) > 2:
        assert statuses[2] == "stockout"      # stub: third class finds nothing
    run_dir = Path(cfg["output"]["dir"]) / run["run_id"]
    for name in ("annotated.jpg", "results.csv", "run.json"):
        assert (run_dir / name).exists()
    assert pipeline.list_runs(cfg)[0]["run_id"] == run["run_id"]


def test_report_files(cfg):
    runs = [pipeline.run_verification(SAMPLE, cfg, detector=stub_detector.detect) for _ in range(2)]
    md_path, pdf_path = report.write_report(runs, cfg)

    text = md_path.read_text(encoding="utf-8")
    assert "Stock discrepancy report" in text
    assert "Verified" in text
    assert "## Run 2" in text
    assert "../run-" in text  # evidence image linked relative to the report

    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert pdf_path.stat().st_size > 5000
