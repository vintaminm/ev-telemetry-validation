import numpy as np
import pandas as pd

from states import CHARGING_DRIVING, GEAR_PARK, NOT_CHARGING, PLUG_CONNECTED

START = pd.Timestamp("2024-07-02 12:32:00")
DRIVE = (120, 360)
CHARGE_FROM = 420


def local_log(seconds=600, seed=7):
    # park, drive with two slow-downs, park, then plug in and charge
    t = np.arange(seconds)
    kmh = np.interp(t, [0, 120, 150, 202, 220, 240, 322, 360], [0, 0, 60, 60, 30, 50, 50, 0])
    dv = np.diff(kmh, append=kmh[-1])
    driving = (t >= DRIVE[0]) & (t < DRIVE[1])
    charging = t >= CHARGE_FROM

    current = np.where(dv > 0.05, -80.0, np.where(dv < -0.05, 25.0, -30.0))
    current = np.where(driving, current, -5.0)
    current = np.where(charging, 40.0, current)
    current = current + np.random.default_rng(seed).normal(0, 0.8, seconds).round(1)

    soc = np.clip(63 + np.cumsum(current) * 0.0004, 0, 100).round()

    return pd.DataFrame({
        "time": START + pd.to_timedelta(t, unit="s"),
        "vehicle_speed": (kmh / 3.6).round(2),
        "hv_current": current.round(1),
        "plug_state": np.where(charging, PLUG_CONNECTED, 0),
        "gear_position": np.where(driving, 4, GEAR_PARK),
        "terminal_15": np.where(t < CHARGE_FROM, 1, 0),
        "usable_soc": soc.astype(int),
    })


def cloud_records(local, every=10):
    rows = local.iloc[::every]
    cloud = pd.DataFrame({
        "actime": rows["time"].values,
        "vehicleState": rows["vehicle_state"].values,
        "chargingState": rows["charging_state"].values,
        "vehicleSpeed": rows["speed_kmh"].values,
        "soc": rows["soc"].astype(float).values,
        "totalVoltage": (400 - 0.05 * rows["hv_current"]).round(1).values,
        "totalCurrent": rows["hv_current"].values,
    })

    # telematics box reports regen current as not charging
    cloud.loc[cloud["chargingState"] == CHARGING_DRIVING, "chargingState"] = NOT_CHARGING

    # states sampled 3 s late when the ignition turns off
    t_off = START + pd.Timedelta(seconds=CHARGE_FROM)
    late = local.loc[local["time"] == t_off - pd.Timedelta(seconds=3)].iloc[0]
    cloud.loc[cloud["actime"] == t_off, ["vehicleState", "chargingState"]] = [late["vehicle_state"], late["charging_state"]]

    # two uploads lose the soc field
    dropped = [START + pd.Timedelta(seconds=s) for s in (480, 540)]
    cloud.loc[cloud["actime"].isin(dropped), "soc"] = np.nan
    return cloud
