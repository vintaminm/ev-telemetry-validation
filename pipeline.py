import json
import os
import sqlite3

import pandas as pd

TABLES = {
    "completeVehicleData": ["actime", "vehicleState", "chargingState", "vehicleSpeed", "soc"],
    "voltageData": ["actime", "totalVoltage", "totalCurrent"],
}


def export_json(cloud, path):
    # one json object per upload, like the platform log export
    with open(path, "w") as f:
        for record in cloud.to_dict("records"):
            record["actime"] = record["actime"].strftime("%Y-%m-%d %H:%M:%S")
            f.write(json.dumps({k: (None if pd.isna(v) else v) for k, v in record.items()}) + "\n")


def json_to_csv(json_path, csv_path):
    with open(json_path) as f:
        df = pd.DataFrame([json.loads(line) for line in f if line.strip()])
    df.to_csv(csv_path, index=False)
    return len(df)


def csv_to_sqlite(csv_path, db_path):
    df = pd.read_csv(csv_path)
    if os.path.exists(db_path):
        os.remove(db_path)
    with sqlite3.connect(db_path) as conn:
        for table, columns in TABLES.items():
            df[columns].to_sql(table, conn, index=False)


def run(cloud, out_dir, vin):
    os.makedirs(out_dir, exist_ok=True)
    paths = {ext: os.path.join(out_dir, f"{vin}.{ext}") for ext in ("jsonl", "csv", "db")}
    export_json(cloud, paths["jsonl"])
    json_to_csv(paths["jsonl"], paths["csv"])
    csv_to_sqlite(paths["csv"], paths["db"])
    return paths


def list_tables(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for (name,) in rows}


def read_table(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql(f"SELECT * FROM {table}", conn)
