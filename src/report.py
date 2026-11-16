"""Discrepancy report: Markdown and PDF (ReportLab), with the evidence images embedded.

A report covers one or more runs (a run = one image or video put through the pipeline).
"""
import os
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STATUS_INFO = {
    # status: (label, recommended action, PDF cell colour)
    "match": ("Verified", "No action needed.", "#d9ead3"),
    "minor": ("Minor shortage", "Recount by hand at the next cycle count; adjust the record if confirmed.", "#fff2cc"),
    "major": ("Major shortage", "Recount by hand now and investigate (unrecorded sales, damage, theft, misplacement).", "#f4cccc"),
    "stockout": ("Stockout", "Check other storage locations; if confirmed, correct the record and reorder.", "#ea9999"),
    "overcount": ("Overcount", "Check for unrecorded receipts or stock from another location; recount by hand.", "#cfe2f3"),
    "no_record": ("No inventory record", "Add the item to the inventory system or fix the sku in config.yaml.", "#e0e0e0"),
}


def status_label(status: str) -> str:
    return STATUS_INFO[status][0]


def _fmt(value, suffix="") -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"0.0{suffix}" if value == 0 else f"{value:+.1f}{suffix}"
    return f"{value}{suffix}"


def _signed(value) -> str:
    if value is None:
        return "-"
    return "0" if value == 0 else f"{value:+d}"


def _table_rows(run: dict) -> list:
    header = ["SKU", "Item", "Location", "Detected", "Recorded", "Variance", "Variance %", "Status"]
    body = [[r["sku"], r["item_name"], r["location"], str(r["detected"]), _fmt(r["recorded"]),
             _signed(r["variance"]), _fmt(r["variance_pct"], "%"), status_label(r["status"])]
            for r in run["rows"]]
    return [header] + body


def _totals(runs: list) -> dict:
    totals = {s: 0 for s in STATUS_INFO}
    for run in runs:
        for r in run["rows"]:
            totals[r["status"]] += 1
    return totals


def _method_text(run: dict) -> str:
    return {
        "image": "single image",
        "track": f"video, tracked across {run['frames_processed']} frames",
        "peak": f"video, peak frame of {run['frames_processed']}",
        "stub": "STUB DETECTOR - counts are fake, for pipeline testing only",
    }.get(run["count_method"], run["count_method"])


def build_markdown(runs: list, cfg: dict, md_dir=None) -> str:
    """Report text. md_dir is where the .md file will live, so image links can be relative."""
    project = cfg["project"]
    totals = _totals(runs)
    checks = sum(totals.values())
    lines = [
        "# Stock discrepancy report",
        "",
        f"**Project:** {project['name']}  ",
        f"**Client:** {project.get('client', '')}  ",
        f"**Location:** {project.get('location', '')}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Verification runs:** {len(runs)}",
        "",
        "## Summary",
        "",
        f"{totals['match']} of {checks} item checks matched the inventory records. "
        f"{checks - totals['match']} need attention.",
        "",
        "| Status | Item checks |",
        "|---|---|",
    ]
    lines += [f"| {STATUS_INFO[s][0]} | {n} |" for s, n in totals.items() if n]
    v = cfg["variance"]
    lines += [
        "",
        f"Thresholds: match within ±{v['match_pct']}%, minor shortage up to {v['minor_pct']}%, "
        "major shortage beyond that.",
    ]
    for i, run in enumerate(runs, 1):
        lines += ["", f"## Run {i}: {run['source_name']}", "",
                  f"Captured: {run['run_at']}. Counting method: {_method_text(run)}.", ""]
        table = _table_rows(run)
        lines.append("| " + " | ".join(table[0]) + " |")
        lines.append("|" + "---|" * len(table[0]))
        lines += ["| " + " | ".join(row) + " |" for row in table[1:]]
        actions = [r for r in run["rows"] if r["status"] != "match"]
        if actions:
            lines += ["", "**Actions**", ""]
            lines += [f"- **{r['item_name']}** ({r['sku']}): {status_label(r['status'])}. "
                      f"{STATUS_INFO[r['status']][1]}" for r in actions]
        image = Path(run["annotated_path"])
        link = os.path.relpath(image, md_dir).replace(os.sep, "/") if md_dir else image.as_posix()
        lines += ["", f"![Detections for {run['source_name']}]({link})"]
    lines += ["", "---", "", "Verified by: ____________________   Date: ____________", ""]
    return "\n".join(lines)


def write_pdf(runs: list, cfg: dict, pdf_path) -> Path:
    pdf_path = Path(pdf_path)
    styles = getSampleStyleSheet()
    normal, small = styles["BodyText"], styles["BodyText"].clone("small", fontSize=8, leading=10)
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title="Stock discrepancy report")
    project = cfg["project"]
    totals = _totals(runs)
    checks = sum(totals.values())
    story = [
        Paragraph("Stock discrepancy report", styles["Title"]),
        Paragraph(
            f"<b>Project:</b> {escape(project['name'])}<br/>"
            f"<b>Client:</b> {escape(project.get('client', ''))}<br/>"
            f"<b>Location:</b> {escape(project.get('location', ''))}<br/>"
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
            f"<b>Verification runs:</b> {len(runs)}", normal),
        Spacer(1, 0.4 * cm),
        Paragraph("Summary", styles["Heading2"]),
        Paragraph(f"{totals['match']} of {checks} item checks matched the inventory records. "
                  f"{checks - totals['match']} need attention.", normal),
        Spacer(1, 0.2 * cm),
    ]
    summary = [["Status", "Item checks"]] + [[STATUS_INFO[s][0], str(n)] for s, n in totals.items() if n]
    summary_table = Table(summary, colWidths=[6 * cm, 3 * cm], hAlign="LEFT")
    style = _base_table_style()
    for i, (s, n) in enumerate([(s, n) for s, n in totals.items() if n], 1):
        style.add("BACKGROUND", (0, i), (0, i), colors.HexColor(STATUS_INFO[s][2]))
    summary_table.setStyle(style)
    v = cfg["variance"]
    story += [summary_table, Spacer(1, 0.2 * cm),
              Paragraph(f"Thresholds: match within ±{v['match_pct']}%, minor shortage up to "
                        f"{v['minor_pct']}%, major shortage beyond that.", small)]

    widths = [1.7 * cm, 4.3 * cm, 3.2 * cm, 1.6 * cm, 1.6 * cm, 1.5 * cm, 1.7 * cm, 2.4 * cm]
    for i, run in enumerate(runs, 1):
        rows = _table_rows(run)
        data = [rows[0]] + [[Paragraph(escape(c), small) if j in (1, 2, 7) else c for j, c in enumerate(row)]
                            for row in rows[1:]]
        table = Table(data, colWidths=widths, repeatRows=1)
        style = _base_table_style()
        for k, r in enumerate(run["rows"], 1):
            style.add("BACKGROUND", (7, k), (7, k), colors.HexColor(STATUS_INFO[r["status"]][2]))
        table.setStyle(style)
        story += [
            Spacer(1, 0.5 * cm),
            KeepTogether([
                Paragraph(f"Run {i}: {escape(run['source_name'])}", styles["Heading2"]),
                Paragraph(f"Captured: {run['run_at']}. Counting method: {escape(_method_text(run))}.", normal),
                Spacer(1, 0.2 * cm),
                table,
            ]),
            Spacer(1, 0.3 * cm),
        ]
        actions = [r for r in run["rows"] if r["status"] != "match"]
        if actions:
            story.append(KeepTogether(
                [Paragraph("<b>Actions</b>", normal)]
                + [Paragraph(f"• <b>{escape(r['item_name'])}</b> ({escape(r['sku'])}): "
                             f"{status_label(r['status'])}. {STATUS_INFO[r['status']][1]}", normal)
                   for r in actions]
                + [Spacer(1, 0.3 * cm)]))
        if Path(run["annotated_path"]).exists():
            story.append(_fit_image(run["annotated_path"], max_w=17 * cm, max_h=10 * cm))
    story += [Spacer(1, 1 * cm), Paragraph("Verified by: ____________________   Date: ____________", normal)]
    doc.build(story)
    return pdf_path


def _base_table_style() -> TableStyle:
    return TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def _fit_image(path, max_w: float, max_h: float) -> Image:
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return Image(str(path), width=w * scale, height=h * scale)


def write_report(runs: list, cfg: dict, out_dir=None) -> tuple:
    """Write report-<timestamp>.md and .pdf. Returns (md_path, pdf_path)."""
    if not runs:
        raise ValueError("No verification runs to report on. Run the pipeline first.")
    out_dir = Path(out_dir) if out_dir else Path(cfg["output"]["dir"]) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"discrepancy-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(build_markdown(runs, cfg, md_dir=out_dir), encoding="utf-8")
    pdf_path = write_pdf(runs, cfg, out_dir / f"{stem}.pdf")
    return md_path, pdf_path
