"""Write the discrepancy report (Markdown + PDF) from saved runs.

Usage: python scripts/make_report.py          # latest run only
       python scripts/make_report.py --all    # every run in the output folder
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import pipeline, report
from src.config import load_config


def main():
    cfg = load_config()
    runs = pipeline.list_runs(cfg)
    if not runs:
        sys.exit("No runs found. Run the dashboard or scripts/demo.py first.")
    if "--all" not in sys.argv:
        runs = runs[-1:]
    md_path, pdf_path = report.write_report(runs, cfg)
    print(f"Report covers {len(runs)} run(s)")
    print(f"  Markdown: {md_path}")
    print(f"  PDF:      {pdf_path}")


if __name__ == "__main__":
    main()
