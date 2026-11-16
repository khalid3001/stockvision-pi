"""Inventory tests. They read the CSV and config, so they keep working after Tuesday's data swap."""
import csv

import pytest

from src import inventory


def _csv_rows(cfg):
    with open(cfg["inventory"]["source_csv"], newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["sku"].strip()]


def test_init_and_query(cfg):
    inv = cfg["inventory"]
    rows = _csv_rows(cfg)
    assert inventory.init_db(inv["source_csv"], inv["database"]) == len(rows)
    records = inventory.get_records(inv["database"])
    first = rows[0]
    assert records[first["sku"]]["recorded_qty"] == int(float(first["recorded_qty"]))
    only = inventory.get_records(inv["database"], skus=[first["sku"], "NOPE"])
    assert list(only) == [first["sku"]]


def test_every_config_class_has_an_inventory_record(cfg):
    """Catches a sku typo in config.yaml or a missing row in the inventory CSV."""
    inv = cfg["inventory"]
    inventory.init_db(inv["source_csv"], inv["database"])
    records = inventory.get_records(inv["database"])
    missing = [name for name, info in cfg["classes"].items() if info["sku"] not in records]
    assert not missing, f"config.yaml classes with no row in the inventory CSV: {missing}"


def test_reload_keeps_history(cfg):
    inv = cfg["inventory"]
    inventory.init_db(inv["source_csv"], inv["database"])
    row = {"sku": "X-1", "item_name": "Test item", "detected": 22, "recorded": 24,
           "variance": -2, "variance_pct": -8.3, "status": "minor"}
    inventory.save_verification(inv["database"], "run1", "2026-11-16T09:00:00", "a.jpg", [row])
    inventory.init_db(inv["source_csv"], inv["database"])
    history = inventory.get_history(inv["database"])
    assert len(history) == 1 and history[0]["status"] == "minor"


def test_missing_column_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("sku,item_name\nX,Y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        inventory.init_db(bad, tmp_path / "x.db")


def test_ensure_db_reloads_when_the_csv_changes(tmp_path):
    """A deployed app keeps its old database; an edited CSV must still reach it."""
    header = "sku,item_name,location,recorded_qty,unit,last_counted\n"
    row_a, row_b = "A,Item A,Bay 1,5,pcs,2026-01-01\n", "B,Item B,Bay 2,7,pcs,2026-01-01\n"
    source, db = tmp_path / "inv.csv", tmp_path / "inv.db"
    cfg = {"inventory": {"source_csv": str(source), "database": str(db)}}
    source.write_text(header + row_a, encoding="utf-8")
    inventory.init_db(source, db)          # an old database, made before fingerprints existed
    source.write_text(header + row_a + row_b, encoding="utf-8")
    inventory.ensure_db(cfg)
    assert sorted(inventory.get_records(db)) == ["A", "B"]

    conn = inventory._connect(db)
    with conn:
        conn.execute("DELETE FROM inventory WHERE sku = 'B'")
    conn.close()
    inventory.ensure_db(cfg)               # CSV unchanged: the database is left alone
    assert sorted(inventory.get_records(db)) == ["A"]
