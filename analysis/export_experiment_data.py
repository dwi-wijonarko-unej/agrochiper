"""
export_experiment_data.py — Ekspor log eksperimen AgroCipher ke CSV siap artikel.

Membaca database SQLite per-service yang ditulis oleh instrumentasi eksperimen
(feature-service, selector-service, encryption-service) serta JSONL gateway, lalu
mengekspor lima file CSV:

  experiment_requests.csv     -> detail fitur ekstraksi (feature_logs)
  experiment_selector.csv     -> keputusan AI Selector (selector_logs)
  experiment_encryption.csv   -> proses enkripsi/dekripsi (crypto_logs)
  experiment_gateway.csv      -> latensi end-to-end + error gateway (JSONL)
  experiment_failures.csv     -> gabungan baris gagal dari semua sumber

Sumber lokal default (dari docker-compose volume):
  data/experiment/feature/experiment_logs.db
  data/experiment/selector/experiment_logs.db
  data/experiment/encryption/experiment_logs.db
  data/experiment/gateway/gateway_experiment.jsonl

Usage:
  python analysis/export_experiment_data.py [--db-dir data/experiment] [--out-dir results/exported]
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DB_DIR = REPO_ROOT / "data" / "experiment"
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "exported"

FEATURE_DB_REL = ("feature", "experiment_logs.db")
SELECTOR_DB_REL = ("selector", "experiment_logs.db")
ENCRYPTION_DB_REL = ("encryption", "experiment_logs.db")
GATEWAY_LOG_REL = ("gateway", "gateway_experiment.jsonl")


def read_table(db_path: Path, table: str) -> list:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def write_csv(rows: list, out_path: Path, drop_cols: tuple = ()) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out_path.write_text("")  # headerless empty output
        return
    cols = [c for c in rows[0].keys() if c not in drop_cols]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main() -> None:
    ap = argparse.ArgumentParser(description="Ekspor data eksperimen AgroCipher")
    ap.add_argument("--db-dir", default=str(DEFAULT_DB_DIR), help="Root vol data eksperimen")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Folder output CSV")
    args = ap.parse_args()

    db_root = Path(args.db_dir)
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    feature_rows = read_table(db_root.joinpath(*FEATURE_DB_REL), "feature_logs")
    selector_rows = read_table(db_root.joinpath(*SELECTOR_DB_REL), "selector_logs")
    crypto_rows = read_table(db_root.joinpath(*ENCRYPTION_DB_REL), "crypto_logs")
    gateway_rows = read_jsonl(db_root.joinpath(*GATEWAY_LOG_REL))

    write_csv(feature_rows, out_root / "experiment_requests.csv", drop_cols=("id",))
    write_csv(selector_rows, out_root / "experiment_selector.csv", drop_cols=("id",))
    write_csv(crypto_rows, out_root / "experiment_encryption.csv", drop_cols=("id",))
    write_csv(gateway_rows, out_root / "experiment_gateway.csv")

    failures = []
    for r in feature_rows:
        if r.get("status") != "ok" or r.get("error_message"):
            failures.append({"source": "feature", **r})
    for r in selector_rows:
        if r.get("status") != "ok" or r.get("error_message"):
            failures.append({"source": "selector", **r})
    for r in crypto_rows:
        if r.get("status") != "ok" or r.get("error_message"):
            failures.append({"source": "encryption", **r})
    for r in gateway_rows:
        if r.get("error_type") or (r.get("http_status") and r.get("http_status") >= 400):
            failures.append({"source": "gateway", **r})

    write_csv(failures, out_root / "experiment_failures.csv")

    print("Ekspor selesai:")
    print(f"  experiment_requests.csv    : {len(feature_rows)} baris")
    print(f"  experiment_selector.csv    : {len(selector_rows)} baris")
    print(f"  experiment_encryption.csv  : {len(crypto_rows)} baris")
    print(f"  experiment_gateway.csv     : {len(gateway_rows)} baris")
    print(f"  experiment_failures.csv    : {len(failures)} baris")
    print(f"  Output dir                 : {out_root.resolve()}")


if __name__ == "__main__":
    main()