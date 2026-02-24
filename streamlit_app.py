import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time, date
from dataclasses import dataclass
from typing import List, Dict, Optional

# –––––––––––––––––––––––––––––––––––

# Page config

# –––––––––––––––––––––––––––––––––––

st.set_page_config(
page_title=“UCITS NAV Lifecycle – Timeline Modeler”,
page_icon=“🏦”,
layout=“wide”,
initial_sidebar_state=“expanded”,
)

st.markdown(”””

<style>
    .main-header {
        background: linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d2137 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
        border-left: 4px solid #00d4aa;
    }
    .main-header h1 {
        color: #ffffff; font-size: 1.6rem; margin: 0 0 0.3rem 0;
        font-weight: 700; letter-spacing: -0.02em;
    }
    .main-header p { color: #8899aa; font-size: 0.85rem; margin: 0; }

    .sla-card {
        padding: 1.1rem 1.3rem; border-radius: 10px;
        text-align: center; font-weight: 600;
    }
    .sla-met {
        background: linear-gradient(135deg, #0a2e1a, #0d3d22);
        border: 1px solid #00d4aa; color: #00d4aa;
    }
    .sla-breach {
        background: linear-gradient(135deg, #3d0a0a, #4d1111);
        border: 1px solid #ff4444; color: #ff4444;
    }
    .sla-card .sla-label {
        font-size: 0.70rem; text-transform: uppercase;
        letter-spacing: 0.08em; opacity: 0.7; margin-bottom: 0.2rem;
    }
    .sla-card .sla-value { font-size: 1.35rem; }

    .info-card {
        background: #0e1a2e; border: 1px solid #1e2d44;
        border-radius: 8px; padding: 0.85rem 1rem; text-align: center;
    }
    .info-card .label {
        font-size: 0.66rem; text-transform: uppercase;
        letter-spacing: 0.06em; color: #667788; margin-bottom: 0.15rem;
    }
    .info-card .value { font-size: 1rem; font-weight: 600; color: #c8d8e8; }
    .info-card .sub { font-size: 0.72rem; color: #ff8844; margin-top: 0.1rem; }

    /* TZ clock strip */
    .tz-strip {
        display: flex; gap: 0; border-radius: 10px;
        overflow: hidden; border: 1px solid #1e2d44; margin-bottom: 1rem;
    }
    .tz-cell {
        flex: 1; padding: 0.7rem 0.6rem; text-align: center;
        background: #0e1a2e; border-right: 1px solid #1e2d44;
    }
    .tz-cell:last-child { border-right: none; }
    .tz-cell.active { background: rgba(0,212,170,0.06); }
    .tz-city {
        font-size: 0.62rem; text-transform: uppercase;
        letter-spacing: 0.07em; color: #667788; margin-bottom: 0.15rem;
    }
    .tz-time { font-size: 1.05rem; font-weight: 700; color: #c8d8e8; }
    .tz-offset { font-size: 0.62rem; color: #556677; }
    .tz-window { font-size: 0.55rem; color: #445566; margin-top: 0.1rem; }
    .tz-dot {
        display: inline-block; width: 6px; height: 6px;
        border-radius: 50%; margin-right: 4px; vertical-align: middle;
    }
    .tz-dot.on { background: #00d4aa; }
    .tz-dot.off { background: #ff4444; opacity: 0.5; }

    section[data-testid="stSidebar"] { background: #0a1020; }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #00d4aa; font-size: 0.82rem; text-transform: uppercase;
        letter-spacing: 0.08em; border-bottom: 1px solid #1a2a40;
        padding-bottom: 0.4rem;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>

“””, unsafe_allow_html=True)

# –––––––––––––––––––––––––––––––––––

# Hub & Timezone Definitions

# –––––––––––––––––––––––––––––––––––

@dataclass
class HubInfo:
short: str
tz_name: str
gmt_offset: float        # hours from GMT
window_start_gmt: int    # operating window start in minutes from T 00:00 GMT
window_end_gmt: int      # operating window end in minutes from T 00:00 GMT
city: str

HUB_DATA: Dict[str, HubInfo] = {
“EMEA – Dublin”:       HubInfo(“EMEA-DUB”,  “GMT”,  0,    7*60,      19*60,     “Dublin”),
“EMEA – Luxembourg”:   HubInfo(“EMEA-LUX”,  “CET”,  +1,   6*60,      18*60,     “Luxembourg”),
“APAC – India”:        HubInfo(“APAC-IND”,  “IST”,  +5.5, 3*60+30,   14*60+30,  “Mumbai”),
“APAC – Philippines”:  HubInfo(“APAC-PHL”,  “PHT”,  +8,   1*60,      12*60,     “Manila”),
“NAM – New York”:      HubInfo(“NAM-NYC”,   “EST”,  -5,   13*60,     24*60,     “New York”),
“NAM – US East”:       HubInfo(“NAM-USE”,   “EST”,  -5,   13*60,     29*60,     “US East”),
}

HUBS = list(HUB_DATA.keys())

CATEGORY_COLORS = {
“Data Ingestion”: “#3b82f6”,
“Batch Run”: “#8b5cf6”,
“Trade Date Processing”: “#f59e0b”,
“Reconciliation”: “#06b6d4”,
“Valuation”: “#ec4899”,
“T+1 Review”: “#10b981”,
“Publication”: “#00d4aa”,
}

T_DATE = date(2025, 1, 15)
T1_DATE = T_DATE + timedelta(days=1)

VALUATION_POINT = datetime.combine(T_DATE, time(16, 0))
NAV_DEADLINE = datetime.combine(T1_DATE, time(9, 0))
TIMELINE_START = datetime.combine(T_DATE, time(8, 0))
TIMELINE_END = datetime.combine(T1_DATE, time(12, 0))

# US East business hours marker on Gantt

US_OPEN_GMT = datetime.combine(T_DATE, time(13, 0))  # 08:00 EST = 13:00 GMT

# –––––––––––––––––––––––––––––––––––

# Timezone Helpers

# –––––––––––––––––––––––––––––––––––

def gmt_to_local(gmt_dt: datetime, offset_hours: float) -> datetime:
“”“Convert a GMT datetime to a local datetime given an offset in hours.”””
return gmt_dt + timedelta(hours=offset_hours)

def gmt_to_est(gmt_dt: datetime) -> datetime:
return gmt_to_local(gmt_dt, -5)

def fmt_gmt(dt_val: datetime) -> str:
return dt_val.strftime(”%H:%M”)

def fmt_est(gmt_dt: datetime) -> str:
return gmt_to_est(gmt_dt).strftime(”%H:%M”)

def fmt_local(gmt_dt: datetime, hub_name: str) -> str:
info = HUB_DATA.get(hub_name)
if not info:
return fmt_gmt(gmt_dt)
return gmt_to_local(gmt_dt, info.gmt_offset).strftime(”%H:%M”)

def is_in_operating_window(gmt_dt: datetime, hub_name: str) -> bool:
“”“Check if a GMT datetime falls within the hub’s operating window.”””
info = HUB_DATA.get(hub_name)
if not info:
return True
# Minutes since T 00:00
if gmt_dt.date() == T_DATE:
mins = gmt_dt.hour * 60 + gmt_dt.minute
else:
mins = 24 * 60 + gmt_dt.hour * 60 + gmt_dt.minute
return info.window_start_gmt <= mins <= info.window_end_gmt

def add_mins(d: datetime, minutes: int) -> datetime:
return d + timedelta(minutes=minutes)

# –––––––––––––––––––––––––––––––––––

# Sidebar – User Configuration

# –––––––––––––––––––––––––––––––––––

with st.sidebar:
st.markdown(”## ⚙️ Configuration”)
st.caption(“Adjust inputs to model the NAV critical path.”)

```
# --- Processing Hubs ---
st.markdown("### 🌐 Processing Hubs")
hub_trade_processing = st.selectbox("Trade Processing", HUBS, index=2, key="hub_tp")
hub_recon = st.selectbox("Reconciliations", HUBS, index=0, key="hub_recon")
hub_accruals = st.selectbox("Income & Expense Accruals", HUBS, index=2, key="hub_acc")
hub_corp_actions = st.selectbox("Corporate Actions", HUBS, index=0, key="hub_ca")
hub_derivatives = st.selectbox("Derivatives Pricing", HUBS, index=0, key="hub_deriv")
hub_nav_review = st.selectbox("NAV Review & Publication", HUBS, index=0, key="hub_nav")

st.markdown("---")

# --- Data Ingestion Cutoffs ---
st.markdown("### 📥 Data Ingestion Cutoffs (GMT)")
ta_file_time = st.time_input(
    "TA Cap Stock / Dealing Files",
    value=time(17, 0),
    help="Time TA files (cap stock, dealing) are received on T (GMT).",
    key="ta_time",
)
st.caption(f"= {fmt_est(datetime.combine(T_DATE, ta_file_time))} EST | "
           f"{fmt_local(datetime.combine(T_DATE, ta_file_time), 'APAC -- India')} IST")

broker_file_time = st.time_input(
    "Broker / Custodian Confirmations",
    value=time(16, 30),
    help="Time broker confirmations & custodian files arrive on T (GMT).",
    key="broker_time",
)
st.caption(f"= {fmt_est(datetime.combine(T_DATE, broker_file_time))} EST | "
           f"{fmt_local(datetime.combine(T_DATE, broker_file_time), 'APAC -- India')} IST")

pricing_file_time = st.time_input(
    "Pricing Feed (WM/Reuters/Bloomberg)",
    value=time(16, 15),
    help="Time closing prices are available after valuation point (GMT).",
    key="pricing_time",
)
st.caption(f"= {fmt_est(datetime.combine(T_DATE, pricing_file_time))} EST | "
           f"{fmt_local(datetime.combine(T_DATE, pricing_file_time), 'APAC -- India')} IST")

st.markdown("---")

# --- Batch File Runs ---
st.markdown("### 🔄 Accounting System Batches (GMT)")
batch_1_time = st.time_input(
    "Batch Run 1 (T evening)",
    value=time(18, 0),
    help="First automated batch into accounting system on T (GMT).",
    key="batch1",
)
st.caption(f"= {fmt_est(datetime.combine(T_DATE, batch_1_time))} EST")

batch_2_time = st.time_input(
    "Batch Run 2 (Overnight)",
    value=time(2, 0),
    help="Overnight batch run (T+1 early morning, GMT).",
    key="batch2",
)
st.caption(f"= {fmt_est(datetime.combine(T1_DATE, batch_2_time))} EST (prev evening)")

batch_3_time = st.time_input(
    "Batch Run 3 -- Final (T+1 morning)",
    value=time(5, 30),
    help="Final batch before NAV review on T+1 (GMT).",
    key="batch3",
)
st.caption(f"= {fmt_est(datetime.combine(T1_DATE, batch_3_time))} EST")

batch_duration = st.slider(
    "Batch Run Duration (mins)", 10, 90, 30, 5, key="batch_dur"
)

st.markdown("---")

# --- Processing Durations ---
st.markdown("### ⏱️ Processing Durations")
dur_trade = st.slider("Trade Processing (mins)", 15, 120, 45, 5, key="dur_trade")
dur_recon = st.slider("Cash & Position Recon (mins)", 15, 120, 60, 5, key="dur_recon")
dur_accruals = st.slider("Income / Expense Accruals (mins)", 15, 90, 30, 5, key="dur_accruals")
dur_corp = st.slider("Corporate Actions (mins)", 10, 90, 30, 5, key="dur_corp")
dur_deriv = st.slider("Derivatives Pricing (mins)", 15, 120, 45, 5, key="dur_deriv")
dur_validation = st.slider("Pre-NAV Validation (mins)", 10, 60, 20, 5, key="dur_val")
dur_nav_review = st.slider("Final NAV Review (T+1) (mins)", 15, 120, 60, 5, key="dur_nav")
dur_nav_publish = st.slider("NAV Publication (mins)", 5, 30, 15, 5, key="dur_pub")
```

# –––––––––––––––––––––––––––––––––––

# Build the task schedule

# –––––––––––––––––––––––––––––––––––

warnings: List[str] = []
errors: List[str] = []

def to_dt_t(t: time) -> datetime:
return datetime.combine(T_DATE, t)

def to_dt_t1(t: time) -> datetime:
return datetime.combine(T1_DATE, t)

# Data ingestion

ta_file_dt = to_dt_t(ta_file_time)
broker_file_dt = to_dt_t(broker_file_time)
pricing_file_dt = to_dt_t(pricing_file_time)

if pricing_file_dt < VALUATION_POINT:
warnings.append(
f”⚠️ Pricing feed at {pricing_file_time.strftime(’%H:%M’)} GMT “
f”({fmt_est(pricing_file_dt)} EST) is before the 16:00 valuation point. “
f”Prices may not reflect closing levels.”
)

# Batch runs

batch1_start = to_dt_t(batch_1_time)
batch1_end = add_mins(batch1_start, batch_duration)

batch2_start = to_dt_t1(batch_2_time) if batch_2_time.hour < 12 else to_dt_t(batch_2_time)
batch2_end = add_mins(batch2_start, batch_duration)

batch3_start = to_dt_t1(batch_3_time) if batch_3_time.hour < 12 else to_dt_t(batch_3_time)
batch3_end = add_mins(batch3_start, batch_duration)

if ta_file_dt > batch1_start:
warnings.append(
f”⚠️ TA files arrive at {ta_file_time.strftime(’%H:%M’)} GMT which is after “
f”Batch Run 1 at {batch_1_time.strftime(’%H:%M’)} GMT. TA data excluded from first batch.”
)

# T-Day processing

trade_proc_start = max(broker_file_dt, pricing_file_dt, VALUATION_POINT)
trade_proc_end = add_mins(trade_proc_start, dur_trade)

recon_start = max(trade_proc_end, ta_file_dt)
recon_end = add_mins(recon_start, dur_recon)

accruals_start = max(pricing_file_dt, VALUATION_POINT)
accruals_end = add_mins(accruals_start, dur_accruals)

corp_start = max(pricing_file_dt, VALUATION_POINT)
corp_end = add_mins(corp_start, dur_corp)

deriv_start = max(pricing_file_dt, VALUATION_POINT)
deriv_end = add_mins(deriv_start, dur_deriv)

prenav_start = max(trade_proc_end, recon_end, accruals_end, corp_end, deriv_end)
prenav_end = add_mins(prenav_start, dur_validation)

if prenav_end > batch1_start:
warnings.append(
f”⚠️ Pre-NAV validation ends at {fmt_gmt(prenav_end)} GMT “
f”({fmt_est(prenav_end)} EST) after Batch 1 ({batch_1_time.strftime(’%H:%M’)} GMT). “
f”Processing pushed to later batches.”
)

# T+1 Processing

nav_review_start = batch3_end
nav_review_end = add_mins(nav_review_start, dur_nav_review)
nav_pub_start = nav_review_end
nav_pub_end = add_mins(nav_pub_start, dur_nav_publish)

sla_met = nav_pub_end <= NAV_DEADLINE
slack_minutes = (NAV_DEADLINE - nav_pub_end).total_seconds() / 60 if sla_met else 0
breach_minutes = (nav_pub_end - NAV_DEADLINE).total_seconds() / 60 if not sla_met else 0

if not sla_met:
errors.append(
f”🚨 **SLA BREACH**: NAV publication completes at **{fmt_gmt(nav_pub_end)} GMT** “
f”(**{fmt_est(nav_pub_end)} EST**) on T+1, which is **{int(breach_minutes)} minutes** “
f”past the 09:00 GMT deadline.”
)

# Hub operating window checks

hub_task_pairs = [
(hub_trade_processing, “Trade Processing”, trade_proc_start, trade_proc_end),
(hub_recon, “Reconciliations”, recon_start, recon_end),
(hub_accruals, “Income & Expense Accruals”, accruals_start, accruals_end),
(hub_corp_actions, “Corporate Actions”, corp_start, corp_end),
(hub_derivatives, “Derivatives Pricing”, deriv_start, deriv_end),
(hub_nav_review, “Final NAV Review”, nav_review_start, nav_review_end),
(hub_nav_review, “NAV Publication”, nav_pub_start, nav_pub_end),
]

out_of_hours_tasks = set()
for hub_name, task_name, t_start, t_end in hub_task_pairs:
if not is_in_operating_window(t_start, hub_name) or not is_in_operating_window(t_end, hub_name):
info = HUB_DATA[hub_name]
warnings.append(
f”⚠️ **{task_name}** ({fmt_gmt(t_start)}-{fmt_gmt(t_end)} GMT) falls outside “
f”{info.short} operating window. Local time: “
f”{fmt_local(t_start, hub_name)}-{fmt_local(t_end, hub_name)} {info.tz_name}.”
)
out_of_hours_tasks.add(task_name)

# –––––––––––––––––––––––––––––––––––

# Assemble task list

# –––––––––––––––––––––––––––––––––––

@dataclass
class Task:
name: str
start: datetime
end: datetime
hub: str
category: str
day: str = “T”

tasks: List[Task] = [
Task(“Pricing Feed Received”, pricing_file_dt, add_mins(pricing_file_dt, 5), “Market Data”, “Data Ingestion”, “T”),
Task(“Broker / Custodian Files”, broker_file_dt, add_mins(broker_file_dt, 5), “Custody”, “Data Ingestion”, “T”),
Task(“TA Cap Stock / Dealing Files”, ta_file_dt, add_mins(ta_file_dt, 5), “Transfer Agency”, “Data Ingestion”, “T”),
Task(“Batch Run 1”, batch1_start, batch1_end, “Systems”, “Batch Run”, “T”),
Task(“Batch Run 2 (Overnight)”, batch2_start, batch2_end, “Systems”, “Batch Run”, “T+1”),
Task(“Batch Run 3 (Final)”, batch3_start, batch3_end, “Systems”, “Batch Run”, “T+1”),
Task(“Trade Processing”, trade_proc_start, trade_proc_end, hub_trade_processing, “Trade Date Processing”, “T”),
Task(“Cash & Position Reconciliation”, recon_start, recon_end, hub_recon, “Reconciliation”, “T”),
Task(“Income & Expense Accruals”, accruals_start, accruals_end, hub_accruals, “Trade Date Processing”, “T”),
Task(“Corporate Actions”, corp_start, corp_end, hub_corp_actions, “Trade Date Processing”, “T”),
Task(“Derivatives Pricing & Processing”, deriv_start, deriv_end, hub_derivatives, “Valuation”, “T”),
Task(“Pre-NAV Validation Checks”, prenav_start, prenav_end, hub_nav_review, “Valuation”, “T”),
Task(“Final NAV Review”, nav_review_start, nav_review_end, hub_nav_review, “T+1 Review”, “T+1”),
Task(“NAV Publication & Delivery”, nav_pub_start, nav_pub_end, hub_nav_review, “Publication”, “T+1”),
]

# –––––––––––––––––––––––––––––––––––

# MAIN DASHBOARD

# –––––––––––––––––––––––––––––––––––

st.markdown(
“””
<div class="main-header">
<h1>🏦 Irish UCITS – Daily NAV Lifecycle Modeler</h1>
<p>Model the critical-path timings from Valuation Point (T 16:00 GMT) through
NAV Delivery (T+1 09:00 GMT) | Multi-hub timezone support</p>
</div>
“””,
unsafe_allow_html=True,
)

# –––––––––––––––––––––––––––––––––––

# Tabs: Dashboard | Source Code

# –––––––––––––––––––––––––––––––––––

tab_dashboard, tab_source = st.tabs([“📊 Dashboard”, “💻 Source Code”])

with tab_source:
st.markdown(”### 💻 Application Source Code”)
st.caption(
“Full source for this Streamlit application. “
“Copy or download to run locally with `streamlit run <filename>.py`.”
)
try:
import pathlib
source_code = pathlib.Path(**file**).read_text(encoding=“utf-8”)
except Exception:
source_code = “# Unable to read source file.”

```
# Line count & size info
line_count = source_code.count("\n") + 1
size_kb = len(source_code.encode("utf-8")) / 1024
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Lines of Code", f"{line_count:,}")
sc2.metric("File Size", f"{size_kb:.1f} KB")
sc3.metric("Language", "Python 3")

st.code(source_code, language="python", line_numbers=True)

st.download_button(
    label="⬇️ Download Source (.py)",
    data=source_code,
    file_name="ucits_nav_lifecycle_app.py",
    mime="text/x-python",
)
```

with tab_dashboard:

```
# -- Timezone Clock Strip --
active_hubs = {hub_trade_processing, hub_recon, hub_accruals,
               hub_corp_actions, hub_derivatives, hub_nav_review}

tz_cells = ""
for hub_name, info in HUB_DATA.items():
    is_active = hub_name in active_hubs
    vp_local = gmt_to_local(VALUATION_POINT, info.gmt_offset)
    in_window = is_in_operating_window(VALUATION_POINT, hub_name)
    # Operating window in local time
    win_start_local = gmt_to_local(
        datetime.combine(T_DATE, time(0, 0)) + timedelta(minutes=info.window_start_gmt),
        info.gmt_offset
    )
    win_end_local = gmt_to_local(
        datetime.combine(T_DATE, time(0, 0)) + timedelta(minutes=info.window_end_gmt),
        info.gmt_offset
    )
    active_cls = "active" if is_active else ""
    dot_cls = "on" if in_window else "off"
    opacity = "" if is_active else "opacity:0.45;"

    tz_cells += f"""
    <div class="tz-cell {active_cls}" style="{opacity}">
        <div class="tz-city"><span class="tz-dot {dot_cls}"></span>{info.city}</div>
        <div class="tz-time">{vp_local.strftime('%H:%M')}</div>
        <div class="tz-offset">{info.tz_name} | GMT{'+' if info.gmt_offset >= 0 else ''}{info.gmt_offset:g}</div>
        <div class="tz-window">{win_start_local.strftime('%H:%M')}-{win_end_local.strftime('%H:%M')} local</div>
    </div>
    """

st.markdown(f'<div class="tz-strip">{tz_cells}</div>', unsafe_allow_html=True)
st.caption("🟢 Hub online at Valuation Point (16:00 GMT) | 🔴 Hub offline | Highlighted = assigned to tasks")


# -- Top-level metrics --
col_sla, col_nav, col_slack, col_vp, col_hubs = st.columns([1.3, 1, 1, 1, 1])

with col_sla:
    sla_class = "sla-met" if sla_met else "sla-breach"
    sla_icon = "✅ SLA MET" if sla_met else "❌ SLA BREACH"
    st.markdown(
        f'<div class="sla-card {sla_class}">'
        f'<div class="sla-label">NAV Delivery SLA</div>'
        f'<div class="sla-value">{sla_icon}</div></div>',
        unsafe_allow_html=True,
    )

with col_nav:
    st.markdown(
        f'<div class="info-card">'
        f'<div class="label">NAV Published</div>'
        f'<div class="value">{fmt_gmt(nav_pub_end)} GMT</div>'
        f'<div class="sub">{fmt_est(nav_pub_end)} EST</div></div>',
        unsafe_allow_html=True,
    )

with col_slack:
    if sla_met:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="label">Buffer to SLA</div>'
            f'<div class="value" style="color:#00d4aa">+{int(slack_minutes)} mins</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="info-card">'
            f'<div class="label">SLA Overrun</div>'
            f'<div class="value" style="color:#ff4444">-{int(breach_minutes)} mins</div></div>',
            unsafe_allow_html=True,
        )

with col_vp:
    st.markdown(
        f'<div class="info-card">'
        f'<div class="label">Valuation Point</div>'
        f'<div class="value">16:00 GMT</div>'
        f'<div class="sub">11:00 EST</div></div>',
        unsafe_allow_html=True,
    )

with col_hubs:
    active_short = sorted({HUB_DATA[h].short for h in active_hubs})
    st.markdown(
        f'<div class="info-card">'
        f'<div class="label">Active Hubs</div>'
        f'<div class="value">{len(active_hubs)} hubs</div>'
        f'<div class="sub" style="font-size:0.6rem;color:#8899aa">{" | ".join(active_short)}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# -- Warnings & Errors --
for e in errors:
    st.error(e)
for w in warnings:
    st.warning(w)


# ----------------------------------------------------------------------
# Gantt Chart with dual-timezone axis
# ----------------------------------------------------------------------
st.markdown("### 📊 Lifecycle Timeline -- Trade Date to T+1")
st.caption("Primary axis: GMT | Orange markers: US Eastern (EST / GMT-5)")

gantt_data = []
for t in tasks:
    hub_info = HUB_DATA.get(t.hub)
    hub_short = hub_info.short if hub_info else t.hub
    tz_name = hub_info.tz_name if hub_info else "GMT"
    local_start = fmt_local(t.start, t.hub) if hub_info else fmt_gmt(t.start)
    local_end = fmt_local(t.end, t.hub) if hub_info else fmt_gmt(t.end)
    dur_mins = int((t.end - t.start).total_seconds() / 60)

    gantt_data.append({
        "Task": t.name,
        "Start": t.start,
        "Finish": t.end,
        "Hub": hub_short,
        "Category": t.category,
        "Day": t.day,
        "Duration": f"{dur_mins} mins",
        "GMT": f"{fmt_gmt(t.start)} -> {fmt_gmt(t.end)}",
        "EST": f"{fmt_est(t.start)} -> {fmt_est(t.end)}",
        "Local": f"{local_start} -> {local_end} {tz_name}" if tz_name != "GMT" else "",
    })

df_gantt = pd.DataFrame(gantt_data)

fig = px.timeline(
    df_gantt,
    x_start="Start",
    x_end="Finish",
    y="Task",
    color="Category",
    color_discrete_map=CATEGORY_COLORS,
    hover_data=["Hub", "Duration", "Day", "GMT", "EST", "Local"],
    title="",
)

fig.update_yaxes(autorange="reversed")

# Valuation Point
fig.add_vline(
    x=VALUATION_POINT, line_dash="dash", line_color="#ff9933", line_width=2,
    annotation_text="VP 16:00 GMT (11:00 EST)",
    annotation_position="top left",
    annotation_font_color="#ff9933", annotation_font_size=11,
)

# SLA Deadline
fig.add_vline(
    x=NAV_DEADLINE, line_dash="dash", line_color="#ff4444", line_width=2,
    annotation_text="SLA 09:00 GMT (04:00 EST)",
    annotation_position="top left",
    annotation_font_color="#ff4444", annotation_font_size=11,
)

# Midnight
midnight = datetime.combine(T1_DATE, time(0, 0))
fig.add_vline(
    x=midnight, line_dash="dot", line_color="#445566", line_width=1,
    annotation_text="Midnight GMT (19:00 EST)",
    annotation_position="bottom left",
    annotation_font_color="#667788", annotation_font_size=10,
)

# US East market open (08:00 EST = 13:00 GMT)
fig.add_vline(
    x=US_OPEN_GMT, line_dash="dot", line_color="#ff8844", line_width=1.5,
    annotation_text="US East Opens 08:00 EST",
    annotation_position="bottom right",
    annotation_font_color="#ff8844", annotation_font_size=10,
)

# SLA breach zone
fig.add_vrect(
    x0=NAV_DEADLINE, x1=TIMELINE_END,
    fillcolor="rgba(255,68,68,0.07)", line_width=0,
    annotation_text="SLA Breach Zone",
    annotation_position="top right",
    annotation_font_color="#ff4444", annotation_font_size=10,
)

# US East operating hours zone (subtle)
fig.add_vrect(
    x0=US_OPEN_GMT, x1=TIMELINE_END,
    fillcolor="rgba(255,136,68,0.03)", line_width=0,
)

fig.update_layout(
    plot_bgcolor="#0a1628",
    paper_bgcolor="#0a1628",
    font=dict(color="#c8d8e8", size=12),
    height=540,
    margin=dict(l=10, r=30, t=30, b=30),
    xaxis=dict(
        title="",
        gridcolor="#1a2a40",
        range=[TIMELINE_START, TIMELINE_END],
        dtick=3600000 * 2,  # 2-hour ticks
        tickformat="%H:%M\n%d %b",
    ),
    yaxis=dict(title="", gridcolor="#1a2a40"),
    legend=dict(
        orientation="h", yanchor="bottom", y=-0.22,
        xanchor="center", x=0.5, font=dict(size=11),
    ),
    hoverlabel=dict(bgcolor="#1a2a40", font_size=12),
)

st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# Detailed Schedule Table with GMT + EST + Local columns
# ----------------------------------------------------------------------
with st.expander("📋 Detailed Chronological Schedule", expanded=True):
    table_rows = []
    for t in sorted(tasks, key=lambda x: x.start):
        duration_mins = int((t.end - t.start).total_seconds() / 60)
        hub_info = HUB_DATA.get(t.hub)
        hub_short = hub_info.short if hub_info else t.hub
        tz_name = hub_info.tz_name if hub_info else "GMT"

        # Status logic
        if t.category == "Data Ingestion":
            status = "📥 Received"
        elif t.category == "Batch Run":
            status = "⚙️ Automated"
        elif t.name in out_of_hours_tasks:
            status = "🌙 Out of Hours"
        elif t.end <= VALUATION_POINT:
            status = "⏳ Pre-VP"
        elif t.day == "T+1" and t.end > NAV_DEADLINE:
            status = "🚨 Past SLA"
        elif t.day == "T+1":
            status = "🔍 Review"
        else:
            status = "✅ Scheduled"

        # Local time for non-GMT hubs
        local_col = ""
        if hub_info and hub_info.tz_name not in ("GMT",):
            local_col = f"{fmt_local(t.start, t.hub)}-{fmt_local(t.end, t.hub)} {tz_name}"

        table_rows.append({
            "Day": t.day,
            "Task": t.name,
            "Start (GMT)": fmt_gmt(t.start),
            "End (GMT)": fmt_gmt(t.end),
            "Start (EST)": fmt_est(t.start),
            "End (EST)": fmt_est(t.end),
            "Duration": f"{duration_mins} min",
            "Hub": hub_short,
            "Hub Local Time": local_col,
            "Status": status,
        })

    df_table = pd.DataFrame(table_rows)
    st.dataframe(
        df_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Day": st.column_config.TextColumn(width="small"),
            "Task": st.column_config.TextColumn(width="large"),
            "Start (GMT)": st.column_config.TextColumn(width="small"),
            "End (GMT)": st.column_config.TextColumn(width="small"),
            "Start (EST)": st.column_config.TextColumn(width="small"),
            "End (EST)": st.column_config.TextColumn(width="small"),
            "Duration": st.column_config.TextColumn(width="small"),
            "Hub Local Time": st.column_config.TextColumn(width="medium"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )


# ----------------------------------------------------------------------
# Critical Path Analysis
# ----------------------------------------------------------------------
st.markdown("### 🔗 Critical Path Analysis")

cp_col1, cp_col2 = st.columns(2)

with cp_col1:
    st.markdown("**Critical Path Sequence**")
    critical_path = [
        ("Valuation Point", VALUATION_POINT, VALUATION_POINT, "EMEA -- Dublin"),
        ("Pricing Feed Received", pricing_file_dt, pricing_file_dt, "Market Data"),
        ("Trade Processing", trade_proc_start, trade_proc_end, hub_trade_processing),
        ("TA Files Received", ta_file_dt, ta_file_dt, "Transfer Agency"),
        ("Cash & Position Recon", recon_start, recon_end, hub_recon),
        ("Pre-NAV Validation", prenav_start, prenav_end, hub_nav_review),
        ("Batch Run 1", batch1_start, batch1_end, "Systems"),
        ("Batch Run 2", batch2_start, batch2_end, "Systems"),
        ("Batch Run 3 (Final)", batch3_start, batch3_end, "Systems"),
        ("Final NAV Review", nav_review_start, nav_review_end, hub_nav_review),
        ("NAV Publication", nav_pub_start, nav_pub_end, hub_nav_review),
    ]

    for i, (name, start, end, hub) in enumerate(critical_path):
        marker = "🟢" if end <= NAV_DEADLINE else "🔴"
        day_lbl = "T" if start.date() == T_DATE else "T+1"

        if start == end:
            time_str = f"{fmt_gmt(start)} GMT"
            est_str = f"{fmt_est(start)} EST"
        else:
            time_str = f"{fmt_gmt(start)} -> {fmt_gmt(end)} GMT"
            est_str = f"{fmt_est(start)} -> {fmt_est(end)} EST"

        # Hub local time
        hub_info = HUB_DATA.get(hub)
        local_str = ""
        if hub_info and hub_info.tz_name not in ("GMT", "EST"):
            if start == end:
                local_str = f" | {fmt_local(start, hub)} {hub_info.tz_name}"
            else:
                local_str = f" | {fmt_local(start, hub)}->{fmt_local(end, hub)} {hub_info.tz_name}"

        st.markdown(
            f"{marker} **{name}** -- {time_str} ({day_lbl})  \n"
            f"<small style='color:#ff8844'>{est_str}</small>"
            f"<small style='color:#667788'>{local_str}</small>",
            unsafe_allow_html=True,
        )

        if i < len(critical_path) - 1:
            next_start = critical_path[i + 1][1]
            gap = (next_start - end).total_seconds() / 60
            if gap > 0:
                st.caption(f"  -> {int(gap)} min gap")
            elif gap < 0:
                st.caption(f"  -> * Parallel / overlap ({int(abs(gap))} min)")

with cp_col2:
    st.markdown("**Processing Hub Allocation**")

    hub_workload = {}
    for t in tasks:
        hub_info = HUB_DATA.get(t.hub)
        hub_key = hub_info.short if hub_info else t.hub
        tz = hub_info.tz_name if hub_info else "GMT"
        dur = int((t.end - t.start).total_seconds() / 60)
        if hub_key not in hub_workload:
            hub_workload[hub_key] = {"tasks": 0, "total_mins": 0, "tz": tz}
        hub_workload[hub_key]["tasks"] += 1
        hub_workload[hub_key]["total_mins"] += dur

    hub_df = pd.DataFrame([
        {"Hub": k, "Timezone": v["tz"], "Tasks": v["tasks"], "Total Duration (mins)": v["total_mins"]}
        for k, v in sorted(hub_workload.items(), key=lambda x: -x[1]["total_mins"])
    ])
    st.dataframe(hub_df, use_container_width=True, hide_index=True)

    st.markdown("**Time Budget Breakdown**")
    total_processing = sum(
        (t.end - t.start).total_seconds() / 60
        for t in tasks
        if t.category not in ("Data Ingestion", "Batch Run")
    )
    total_batch = sum(
        (t.end - t.start).total_seconds() / 60
        for t in tasks
        if t.category == "Batch Run"
    )
    total_window = (NAV_DEADLINE - VALUATION_POINT).total_seconds() / 60

    st.markdown(
        f"- Total processing window: **{int(total_window)} mins** (VP -> SLA)\n"
        f"- Aggregate processing time: **{int(total_processing)} mins**\n"
        f"- Aggregate batch time: **{int(total_batch)} mins**\n"
        f"- Parallelism benefit: tasks run concurrently across hubs"
    )

    # EST conversion reference
    st.markdown("**Key Time Conversions**")
    st.markdown(
        "| Milestone | GMT | EST |\n"
        "|---|---|---|\n"
        "| Valuation Point | 16:00 | 11:00 |\n"
        "| Midnight | 00:00 T+1 | 19:00 T |\n"
        "| SLA Deadline | 09:00 T+1 | 04:00 T+1 |\n"
        f"| NAV Published | {fmt_gmt(nav_pub_end)} T+1 | {fmt_est(nav_pub_end)} |\n"
    )


# ----------------------------------------------------------------------
# Dependency Logic & Validation
# ----------------------------------------------------------------------
with st.expander("🔍 Dependency Validation & Rule Checks"):
    # Check if any US/EST hub tasks are out of hours
    any_est_ooh = any(
        HUB_DATA.get(hub, HubInfo("","",0,0,0,"")).tz_name == "EST"
        and (not is_in_operating_window(t_start, hub) or not is_in_operating_window(t_end, hub))
        for hub, _, t_start, t_end in hub_task_pairs
    )

    checks = [
        ("Pricing feed arrives after Valuation Point",
         pricing_file_dt >= VALUATION_POINT,
         f"Pricing at {pricing_file_time.strftime('%H:%M')} GMT "
         f"({fmt_est(pricing_file_dt)} EST), VP at 16:00 GMT (11:00 EST)"),

        ("Broker files arrive before Trade Processing starts",
         broker_file_dt <= trade_proc_start,
         f"Broker at {broker_file_time.strftime('%H:%M')} GMT, "
         f"processing at {fmt_gmt(trade_proc_start)} GMT"),

        ("TA files arrive before Reconciliation starts",
         ta_file_dt <= recon_start,
         f"TA at {ta_file_time.strftime('%H:%M')} GMT, "
         f"recon at {fmt_gmt(recon_start)} GMT"),

        ("All T-day tasks complete before Batch 1",
         prenav_end <= batch1_start,
         f"Pre-NAV ends {fmt_gmt(prenav_end)} GMT, "
         f"Batch 1 at {batch_1_time.strftime('%H:%M')} GMT"),

        ("Batch runs are in sequential order",
         batch1_end <= batch2_start and batch2_end <= batch3_start,
         f"B1->B2->B3: {fmt_gmt(batch1_end)} -> {fmt_gmt(batch2_start)} -> "
         f"{fmt_gmt(batch3_start)} GMT"),

        ("NAV Review starts after final batch",
         nav_review_start >= batch3_end,
         f"Review at {fmt_gmt(nav_review_start)} GMT, "
         f"Batch 3 ends {fmt_gmt(batch3_end)} GMT"),

        ("NAV published before 09:00 GMT T+1 SLA",
         sla_met,
         f"Publication at {fmt_gmt(nav_pub_end)} GMT "
         f"({fmt_est(nav_pub_end)} EST), deadline 09:00 GMT (04:00 EST)"),

        ("US East / EST hub tasks within operating hours",
         not any_est_ooh,
         f"US East window: 08:00-00:00 EST (13:00-05:00 GMT T+1)"),
    ]

    for label, passed, detail in checks:
        icon = "✅" if passed else "❌"
        st.markdown(
            f"{icon} **{label}**  \n"
            f"<small style='color:#667788'>{detail}</small>",
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------
st.markdown("---")
st.caption(
    "Irish UCITS NAV Lifecycle Modeler | Fund Type: UCITS V | "
    "Valuation Point: 16:00 GMT (11:00 EST) | SLA: 09:00 GMT T+1 (04:00 EST) | "
    "All primary times in GMT | For modelling purposes only"
)