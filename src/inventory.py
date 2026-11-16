"""Data layer: a SQLite database standing in for the client's inventory system.

Two tables:
  inventory      - recorded quantities, rebuilt from the CSV named in config.yaml
  verifications  - one row per item per verification run (history for the dashboard)
"""
import csv
import hashlib
import sqlite3
from pathlib import Path

CSV_COLUMNS = ["sku", "item_name", "location", "recorded_qty", "unit", "last_counted"]


def _connect(db_path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS inventory (
               sku TEXT PRIMARY KEY, item_name TEXT, location TEXT,
               recorded_qty INTEGER NOT NULL, unit TEXT, last_counted TEXT)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS verifications (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               run_id TEXT, run_at TEXT, source TEXT, sku TEXT, item_name TEXT,
               detected INTEGER, recorded INTEGER, variance INTEGER,
               variance_pct REAL, status TEXT)"""
    )
    return conn


def init_db(csv_path, db_path) -> int:
    """(Re)load the inventory table from the CSV. Verification history is kept. Returns row count."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Inventory CSV not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path.name} is missing column(s): {', '.join(missing)}")
        rows = [
            (r["sku"].strip(), r["item_name"].strip(), r["location"].strip(),
             int(float(r["recorded_qty"])), r["unit"].strip(), r["last_counted"].strip())
            for r in reader if r["sku"].strip()
        ]
    conn = _connect(db_path)
    with conn:
        conn.execute("DELETE FROM inventory")
        conn.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.close()
    return len(rows)


def ensure_db(cfg: dict) -> None:
    """Load the inventory from the CSV when there is no database yet, or the CSV has changed since.

    A deployed app keeps its database between updates, so without the second check an edited
    CSV would never reach it. The CSV's fingerprint is stored in the database and compared;
    file dates are not reliable on a server. Verification history is kept either way.
    """
    inv = cfg["inventory"]
    db, source = Path(inv["database"]), Path(inv["source_csv"])
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
    if db.exists() and (fingerprint is None or _loaded_fingerprint(db) == fingerprint):
        return
    init_db(source, db)
    conn = _connect(db)
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('csv_sha256', ?)", (fingerprint,))
    conn.close()


def _loaded_fingerprint(db_path):
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'csv_sha256'").fetchone()
    except sqlite3.OperationalError:  # database made before the meta table existed
        row = None
    conn.close()
    return row["value"] if row else None


def get_records(db_path, skus=None) -> dict:
    """Return {sku: {item_name, location, recorded_qty, unit, last_counted}}."""
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    records = {r["sku"]: dict(r) for r in rows}
    if skus is not None:
        records = {s: records[s] for s in skus if s in records}
    return records


def save_verification(db_path, run_id: str, run_at: str, source: str, rows: list) -> None:
    """Store the comparison rows of one run."""
    conn = _connect(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO verifications
               (run_id, run_at, source, sku, item_name, detected, recorded, variance, variance_pct, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(run_id, run_at, source, r["sku"], r["item_name"], r["detected"], r["recorded"],
              r["variance"], r["variance_pct"], r["status"]) for r in rows],
        )
    conn.close()


def get_history(db_path, limit: int = 200) -> list:
    """Most recent verification rows first."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT run_id, run_at, source, sku, item_name, detected, recorded, variance, variance_pct, status "
        "FROM verifications ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
