"""Load the inventory CSV named in config.yaml into SQLite.  Usage: python scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import inventory
from src.config import load_config


def main():
    cfg = load_config()
    inv = cfg["inventory"]
    n = inventory.init_db(inv["source_csv"], inv["database"])
    print(f"Loaded {n} inventory records from {inv['source_csv']} into {inv['database']}")
    records = inventory.get_records(inv["database"])
    for name, info in cfg["classes"].items():
        if info["sku"] not in records:
            print(f"  WARNING: class '{name}' points to sku {info['sku']}, which is not in the CSV")


if __name__ == "__main__":
    main()
