import pytest

from src import comparison


@pytest.mark.parametrize("detected, recorded, expected", [
    (100, 100, "match"),
    (98, 100, "match"),       # -2 % is inside match_pct
    (102, 100, "match"),
    (97, 100, "minor"),
    (90, 100, "minor"),       # exactly -10 %
    (89, 100, "major"),
    (0, 100, "stockout"),
    (103, 100, "overcount"),
    (5, 0, "overcount"),
    (0, 0, "match"),
    (5, None, "no_record"),
])
def test_classify(detected, recorded, expected):
    assert comparison.classify(detected, recorded, match_pct=2, minor_pct=10) == expected


def test_compare_rows(cfg):
    """Uses whatever classes config.yaml lists, with made-up records of 100 each."""
    cfg["variance"] = {"match_pct": 2, "minor_pct": 10}
    names = list(cfg["classes"])
    skus = [cfg["classes"][n]["sku"] for n in names]
    records = {s: {"item_name": s, "location": "", "unit": "pcs", "recorded_qty": 100} for s in skus}
    counts = {names[0]: 100}
    if len(names) > 1:
        counts[names[1]] = 95
    rows = comparison.compare(counts, cfg, records, {names[0]: 0.9})
    by_sku = {r["sku"]: r for r in rows}

    assert len(rows) == len(names)
    assert by_sku[skus[0]]["status"] == "match" and by_sku[skus[0]]["variance"] == 0
    assert by_sku[skus[0]]["confidence"] == 0.9
    if len(names) > 1:
        assert by_sku[skus[1]]["variance"] == -5 and by_sku[skus[1]]["variance_pct"] == -5.0
        assert by_sku[skus[1]]["status"] == "minor"
    if len(names) > 2:
        assert by_sku[skus[2]]["status"] == "stockout"
    assert comparison.summarise(rows)["match"] == 1


def test_class_without_inventory_record(cfg):
    first = next(iter(cfg["classes"]))
    rows = comparison.compare({first: 3}, cfg, records={})
    assert all(r["status"] == "no_record" and r["variance"] is None for r in rows)
