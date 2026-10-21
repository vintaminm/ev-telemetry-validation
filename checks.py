import pandas as pd

# cloud field -> local column, allowed difference
FIELDS = {
    "vehicleState": ("vehicle_state", 0),
    "chargingState": ("charging_state", 0),
    "vehicleSpeed": ("speed_kmh", 1.0),
    "soc": ("soc", 0),
}
ALIGN_TOLERANCE = pd.Timedelta(seconds=1)
OFFSET_WINDOW = pd.Timedelta(seconds=5)


def find_offset(local, column, t, value, tol):
    # closest local sample near t that carries the cloud value
    near = local[(local["time"] - t).abs() <= OFFSET_WINDOW]
    hits = near[(near[column] - value).abs() <= tol]
    if hits.empty:
        return None
    lags = (hits["time"] - t).dt.total_seconds().astype(int)
    return int(lags.iloc[lags.abs().argmin()])


def validate(local, cloud):
    local = local.sort_values("time")
    merged = pd.merge_asof(
        cloud.sort_values("actime"), local.add_prefix("local_"),
        left_on="actime", right_on="local_time", direction="nearest", tolerance=ALIGN_TOLERANCE,
    )
    rows = []
    for _, r in merged.iterrows():
        for field, (column, tol) in FIELDS.items():
            cloud_value, local_value = r[field], r[f"local_{column}"]
            if pd.isna(r["local_time"]):
                reason = "no local sample within 1 s"
            elif pd.isna(cloud_value):
                reason = "missing field"
            elif abs(cloud_value - local_value) <= tol:
                reason = ""
            else:
                lag = find_offset(local, column, r["actime"], cloud_value, tol)
                reason = "value mismatch" if lag is None else f"timestamp offset ({lag:+d} s)"
            rows.append({
                "time": r["actime"],
                "field": field,
                "cloud": cloud_value,
                "local": local_value,
                "status": "flagged" if reason else "ok",
                "reason": reason,
            })
    return pd.DataFrame(rows)


def summarize(results):
    flagged = results[results["status"] == "flagged"]
    return {
        "records": results["time"].nunique(),
        "checks": len(results),
        "pass_rate": 1 - len(flagged) / len(results),
        "flagged": len(flagged),
    }
