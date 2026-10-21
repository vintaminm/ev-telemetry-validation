import pandas as pd

# gb/t 32960 status codes
CHARGING_PARKED = 0x01
CHARGING_DRIVING = 0x02
NOT_CHARGING = 0x03
CHARGE_COMPLETE = 0x04
VEHICLE_ON = 0x01
VEHICLE_OFF = 0x02
VEHICLE_OTHER = 0x03
INVALID = 0xFE

PLUG_CONNECTED = 2
GEAR_PARK = 8

STATE_LABELS = {
    "charging_state": {
        CHARGING_PARKED: "0x01 charging, parked",
        CHARGING_DRIVING: "0x02 charging, driving",
        NOT_CHARGING: "0x03 not charging",
        CHARGE_COMPLETE: "0x04 charge complete",
    },
    "vehicle_state": {
        VEHICLE_ON: "0x01 started",
        VEHICLE_OFF: "0x02 off",
        VEHICLE_OTHER: "0x03 other",
    },
}


def soc_state(raw):
    if raw == 4095:
        return INVALID
    if raw == 4094:
        return 0
    return max(0, min(100, int(raw)))


def charging_state(current, plug, gear, soc):
    # positive hv current means energy flows into the battery
    if current > 0:
        if plug == PLUG_CONNECTED or gear == GEAR_PARK:
            return CHARGING_PARKED
        return CHARGING_DRIVING
    if soc == 100 and plug == PLUG_CONNECTED:
        return CHARGE_COMPLETE
    return NOT_CHARGING


def vehicle_state(terminal_15, c_state):
    if terminal_15 == 1:
        return VEHICLE_ON
    return VEHICLE_OTHER if c_state == CHARGING_PARKED else VEHICLE_OFF


def derive(log):
    df = log.copy()
    df["soc"] = df["usable_soc"].map(soc_state)
    df["charging_state"] = [
        charging_state(c, p, g, s)
        for c, p, g, s in zip(df["hv_current"], df["plug_state"], df["gear_position"], df["soc"])
    ]
    df["vehicle_state"] = [vehicle_state(t, c) for t, c in zip(df["terminal_15"], df["charging_state"])]
    df["speed_kmh"] = (df["vehicle_speed"] * 3.6).round(1)
    return df


def label(kind, code):
    if pd.isna(code):
        return "missing"
    return STATE_LABELS[kind].get(int(code), hex(int(code)))
