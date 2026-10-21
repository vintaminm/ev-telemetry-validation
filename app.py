import os
import tempfile

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import pipeline
from checks import summarize, validate
from demo_data import cloud_records, local_log
from states import STATE_LABELS, derive, label

st.set_page_config(page_title="Vehicle Data Dashboard", layout="wide", initial_sidebar_state="collapsed")

BLUE, ORANGE, RED, GRID = "#0366D6", "#E36209", "#D73A49", "#EAECEF"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, .stApp, h1, h2, h3, p, label, li, button, input, textarea, select,
[data-testid="stMarkdownContainer"], [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { font-family: 'Inter', sans-serif !important; }
[data-testid="stDecoration"] { display: none; }
section[data-testid="stSidebar"] { border-right: 1px solid #E1E4E8; }
.stApp { background: #F6F8FA; }
#MainMenu, .stDeployButton, footer { visibility: hidden; }
h1, h2, h3 { color: #1F2328; font-weight: 600; letter-spacing: -0.01em; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 4px 0 18px; }
.card { background: #FFFFFF; border: 1px solid #E1E4E8; border-radius: 8px; padding: 10px 14px; }
.card .k { font-size: 12px; color: #6A737D; }
.card .v { font-size: 15px; color: #1F2328; font-weight: 500; margin-top: 2px; }
.stButton > button, .stFormSubmitButton > button { background: #0366D6; color: #FFFFFF; border: none; border-radius: 8px; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background: #024EA4; color: #FFFFFF; }
div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E1E4E8; border-radius: 8px; padding: 12px 16px; }
</style>
"""

DEFAULTS = {
    "page": "Dashboard",
    "test_type": "Log replay",
    "vin_number": "TESTVIN0000000001",
    "channel_number": "1",
    "dbc_file": "demo_vehicle.dbc",
    "data_source": "Synthetic demo",
}


@st.cache_data(show_spinner=False)
def load_demo():
    local = derive(local_log())
    return local, cloud_records(local)


@st.cache_data(show_spinner=False)
def convert(cloud, vin):
    return pipeline.run(cloud, os.path.join(tempfile.gettempdir(), "ev-telemetry-validation"), vin)


def style(fig, height):
    fig.update_layout(
        template="simple_white", height=height, margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Inter, sans-serif", size=13, color="#1F2328"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=True, gridcolor=GRID)
    return fig


def show_sidebar():
    st.sidebar.title("Navigation")
    pages = ["Configuration", "Dashboard"]
    page = st.sidebar.radio("Go to", pages, index=pages.index(st.session_state.page))
    st.sidebar.caption("All data in this demo is synthetic.")
    if page != st.session_state.page:
        st.session_state.page = page
        st.rerun()


def show_configuration():
    st.title("Test Configuration")
    st.caption("Live capture needs CAN hardware and access to the telematics platform. This demo replays synthetic data.")
    types = ["Live capture", "Log replay"]
    test_type = st.radio("Test type", types, index=types.index(st.session_state.test_type), horizontal=True)
    with st.form("config"):
        c1, c2, c3 = st.columns(3)
        vin = c1.text_input("Vehicle VIN", st.session_state.vin_number)
        channel = c2.text_input("CAN channel", st.session_state.channel_number)
        dbc = c3.text_input("DBC file", st.session_state.dbc_file)
        source = st.selectbox("Data source", ["Synthetic demo"])
        if st.form_submit_button("Start test"):
            st.session_state.update(
                test_type=test_type, vin_number=vin, channel_number=channel,
                dbc_file=dbc, data_source=source, page="Dashboard",
            )
            st.rerun()


def config_cards():
    s = st.session_state
    items = [("Test type", s.test_type), ("Vehicle VIN", s.vin_number), ("CAN channel", s.channel_number),
             ("DBC file", s.dbc_file), ("Data source", s.data_source)]
    html = "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in items)
    st.markdown(f'<div class="cards">{html}</div>', unsafe_allow_html=True)


def signal_chart(local):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                        subplot_titles=("Vehicle speed (km/h)", "HV battery current (A)"))
    fig.add_trace(go.Scatter(x=local["time"], y=local["speed_kmh"], name="Speed", line=dict(color=BLUE, width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=local["time"], y=local["hv_current"], name="Current", line=dict(color=ORANGE, width=1.5)), 2, 1)
    fig.update_layout(showlegend=False)
    return style(fig, 460)


def state_chart(local, cloud, results, column, field, title):
    codes = STATE_LABELS[column]
    flagged = results[(results["field"] == field) & (results["status"] == "flagged")]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=local["time"], y=local[column], name="Vehicle (CAN)",
                             line=dict(color=BLUE, width=2, shape="hv")))
    fig.add_trace(go.Scatter(x=cloud["actime"], y=cloud[field], name="Cloud (platform)", mode="markers",
                             marker=dict(color=ORANGE, size=8)))
    fig.add_trace(go.Scatter(x=flagged["time"], y=flagged["cloud"], name="Flagged", mode="markers",
                             marker=dict(color=RED, size=15, symbol="circle-open", line=dict(width=2.5)),
                             text=flagged["reason"], hovertemplate="%{text}<extra></extra>"))
    fig.update_layout(title=dict(text=title, x=0, font=dict(size=15)))
    fig.update_yaxes(tickvals=list(codes), ticktext=list(codes.values()), range=[0.5, max(codes) + 0.5], automargin=False)
    fig = style(fig, 300)
    fig.update_layout(margin=dict(l=160))
    return fig


def flagged_table(results):
    rows = results[results["status"] == "flagged"].copy()

    def fmt(field, value):
        if field in ("vehicleState", "chargingState"):
            return label("vehicle_state" if field == "vehicleState" else "charging_state", value)
        return "missing" if pd.isna(value) else f"{value:g}"

    return pd.DataFrame({
        "Time": rows["time"].dt.strftime("%H:%M:%S"),
        "Field": rows["field"],
        "Cloud": [fmt(f, v) for f, v in zip(rows["field"], rows["cloud"])],
        "Vehicle": [fmt(f, v) for f, v in zip(rows["field"], rows["local"])],
        "Reason": rows["reason"],
    })


def show_dashboard():
    st.title("Vehicle Data Dashboard")
    config_cards()
    local, cloud = load_demo()
    vin = st.session_state.vin_number
    capture, conversion, rtm, replay = st.tabs(["Data Capture", "Convert Data", "RTM Data Visualization", "Replay Test"])

    with capture:
        st.write(f"Decoded CAN signals, {len(local)} samples at 1 Hz, "
                 f"{local['time'].iloc[0]:%H:%M:%S} to {local['time'].iloc[-1]:%H:%M:%S}.")
        st.plotly_chart(signal_chart(local), use_container_width=True)
        raw = ["time", "vehicle_speed", "hv_current", "plug_state", "gear_position", "terminal_15", "usable_soc"]
        st.dataframe(local[raw].head(50), use_container_width=True, hide_index=True)

    with conversion:
        st.write("Platform export (JSON lines) → CSV → SQLite, one table per GB/T 32960 data type.")
        if st.button("Run conversion again"):
            convert.clear()
        paths = convert(cloud, vin)
        files = pd.DataFrame({
            "Step": ["Platform export", "CSV", "SQLite"],
            "File": [os.path.basename(paths[k]) for k in ("jsonl", "csv", "db")],
            "Size (KB)": [round(os.path.getsize(paths[k]) / 1024, 1) for k in ("jsonl", "csv", "db")],
        })
        st.dataframe(files, use_container_width=True, hide_index=True)
        tables = pipeline.list_tables(paths["db"])
        st.dataframe(pd.DataFrame({"Table": list(tables), "Rows": list(tables.values())}),
                     use_container_width=True, hide_index=True)

    with rtm:
        db_path = convert(cloud, vin)["db"]
        table = st.selectbox("Table", list(pipeline.list_tables(db_path)))
        df = pipeline.read_table(db_path, table)
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)
        st.download_button("Download as CSV", df.to_csv(index=False), file_name=f"{table}.csv", mime="text/csv")
        numeric = list(df.select_dtypes("number").columns)
        default = numeric.index("vehicleSpeed") if "vehicleSpeed" in numeric else 0
        column = st.selectbox("Column to plot", numeric, index=default)
        fig = go.Figure(go.Scatter(x=pd.to_datetime(df["actime"]), y=df[column], mode="lines+markers",
                                   line=dict(color=BLUE, width=2), marker=dict(size=5)))
        fig.update_layout(title=dict(text=f"{column} over time", x=0, font=dict(size=15)))
        st.plotly_chart(style(fig, 320), use_container_width=True)

    with replay:
        results = validate(local, cloud)
        s = summarize(results)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cloud records", s["records"])
        m2.metric("Field checks", s["checks"])
        m3.metric("Passed", f"{s['pass_rate']:.1%}")
        m4.metric("Flagged", s["flagged"])
        st.plotly_chart(state_chart(local, cloud, results, "charging_state", "chargingState", "Charging state"),
                        use_container_width=True)
        st.plotly_chart(state_chart(local, cloud, results, "vehicle_state", "vehicleState", "Vehicle state"),
                        use_container_width=True)
        st.subheader("Flagged records")
        st.dataframe(flagged_table(results), use_container_width=True, hide_index=True)


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    show_sidebar()
    if st.session_state.page == "Configuration":
        show_configuration()
    else:
        show_dashboard()


main()
