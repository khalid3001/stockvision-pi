"""Comparison: computer-vision counts vs recorded inventory quantities.

variance     = detected - recorded
variance_pct = variance / recorded * 100

Status rules (thresholds from config.yaml):
  no_record  the sku is not in the inventory records
  stockout   records say there is stock, nothing was detected
  match      |variance_pct| <= match_pct
  overcount  more detected than recorded (beyond match_pct)
  minor      short by up to minor_pct
  major      short by more than minor_pct
"""

STATUSES = ["match", "minor", "major", "stockout", "overcount", "no_record"]


def classify(detected: int, recorded, match_pct: float, minor_pct: float) -> str:
    if recorded is None:
        return "no_record"
    if recorded == 0:
        return "match" if detected == 0 else "overcount"
    if detected == 0:
        return "stockout"
    pct = (detected - recorded) / recorded * 100
    if abs(pct) <= match_pct:
        return "match"
    if pct > 0:
        return "overcount"
    return "minor" if abs(pct) <= minor_pct else "major"


def compare(counts: dict, cfg: dict, records: dict, avg_confidence: dict = None) -> list:
    """One row per class in the config.

    counts:  {class_name: detected count}
    records: {sku: {item_name, location, recorded_qty, ...}} from inventory.get_records()
    """
    thresholds = cfg["variance"]
    avg_confidence = avg_confidence or {}
    rows = []
    for name, info in cfg["classes"].items():
        detected = int(counts.get(name, 0))
        record = records.get(info["sku"])
        recorded = record["recorded_qty"] if record else None
        variance = detected - recorded if recorded is not None else None
        variance_pct = round(variance / recorded * 100, 1) if recorded else None
        rows.append({
            "class_name": name,
            "sku": info["sku"],
            "item_name": record["item_name"] if record else info["display_name"],
            "location": record["location"] if record else "",
            "unit": record["unit"] if record else "",
            "detected": detected,
            "recorded": recorded,
            "variance": variance,
            "variance_pct": variance_pct,
            "confidence": avg_confidence.get(name),
            "status": classify(detected, recorded, thresholds["match_pct"], thresholds["minor_pct"]),
        })
    return rows


def summarise(rows: list) -> dict:
    """Count of rows per status, plus whether everything matched."""
    summary = {s: 0 for s in STATUSES}
    for r in rows:
        summary[r["status"]] += 1
    summary["all_match"] = summary["match"] == len(rows)
    return summary
