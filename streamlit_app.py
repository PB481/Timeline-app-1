# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, time, date
from dataclasses import dataclass

# ---------------------------------------------------------------------
# Page config & Styling
# ---------------------------------------------------------------------
st.set_page_config(page_title="UCITS NAV Lifecycle Modeler", page_icon="🏦", layout="wide")

st.markdown("""
<style>
    .main-header { background: linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d2137 100%); padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.2rem; border-left: 4px solid #00d4aa; }
    .main-header h1 { color: #ffffff; font-size: 1.6rem; margin: 0 0 0.3rem 0; font-weight: 700; }
    .main-header p { color: #8899aa; font-size: 0.85rem; margin: 0; }
    .sla-card { padding: 1.1rem 1.3rem; border-radius: 10px; text-align: center; font-weight: 600; }
    .sla-met { background: linear-gradient(135deg, #0a2e1a, #0d3d22); border: 1px solid #00d4aa; color: #00d4aa; }
    .sla-breach { background: linear-gradient(135deg, #3d0a0a, #4d1111); border: 1px solid #ff4444; color: #ff4444; }
    .info-card { background: #0e1a2e; border: 1px solid #1e2d44; border-radius: 8px; padding: 0.85rem 1rem; text-align: center; }
    .info-card .label { font-size: 0.66rem; text-transform: uppercase; color: #667788; margin-bottom: 0.15rem; }
    .info-card .value { font-size: 1rem; font-weight: 600; color: #c8d8e8; }
    .cost-text { color: #85e89d; }
    .tz-strip { display: flex; gap: 0; border-radius: 10px; overflow: hidden; border: 1px solid #1e2d44; margin-bottom: 1rem; }
    .tz-cell { flex: 1; padding: 0.7rem 0.6rem; text-align: center; background: #0e1a2e; border-right: 1px solid #1e2d44; }
    .tz-cell:last-child { border-right: none; }
    .tz-city { font-size: 0.62rem; text-transform: uppercase; color: #667788; margin-bottom: 0.15rem; }
    .tz-time { font-size: 1.05rem; font-weight: 700; color: #c8d8e8; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Session State Initialization (For Dynamic Features)
# ---------------------------------------------------------------------
if 'custom_hubs' not in st.session_state:
    st.session_state.custom_hubs = {}
if 'custom_tasks' not in st.session_state:
    st.session_state.custom_tasks = []

# ---------------------------------------------------------------------
# Enhanced Hub Definitions 
# ---------------------------------------------------------------------
@dataclass
class HubInfo:
    short: str
    tz_name: str
    gmt_offset: float
    city: str
    hourly_rate: float
    overhead_factor: float

# Base Hubs
HUB_DATA = {
    "EMEA - Dublin":       HubInfo("EMEA-DUB", "GMT", 0, "Dublin", 85.0, 0.05),
    "APAC - India":        HubInfo("APAC-IND", "IST", +5.5, "Mumbai", 25.0, 0.12),
    "NAM - New York":      HubInfo("NAM-NYC", "EST", -5, "New York", 100.0, 0.08),
}

# Inject Custom Hubs from Session State
HUB_DATA.update(st.session_state.custom_hubs)
HUBS = list(HUB_DATA.keys())

CATEGORY_COLORS = {
    "Data Ingestion": "#3b82f6", "Batch Run": "#8b5cf6", "Trade Date Processing": "#f59e0b",
    "Reconciliation": "#06b6d4", "Valuation": "#ec4899", "T+1 Review": "#10b981", "Publication": "#00d4aa",
    "Custom Task": "#eab308"
}

T_DATE = date.today()
T1_DATE = T_DATE + timedelta(days=1)
VALUATION_POINT = datetime.combine(T_DATE, time(16, 0))
NAV_DEADLINE = datetime.combine(T1_DATE, time(9, 0))

def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def fmt_est(dt: datetime) -> str: return (dt + timedelta(hours=-5)).strftime("%H:%M")
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=int(mins))
def get_compressed_duration(base_mins: int, n_staff: int, overhead: float) -> float:
    if n_staff == 1: return float(base_mins)
    return base_mins / (n_staff ** 0.7) * (1 + (overhead * n_staff))

# ---------------------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Operating Model")
    
    hub_trade = st.selectbox("Trade Processing", HUBS, index=1)
    staff_trade = st.slider("Trade Staff", 1, 10, 3, key="s_tr")
    
    hub_recon = st.selectbox("Reconciliations", HUBS, index=0)
    staff_recon = st.slider("Recon Staff", 1, 10, 4, key="s_rc")
    
    hub_nav = st.selectbox("NAV Review & Pub", HUBS, index=0)
    staff_nav = st.slider("Review Staff", 1, 5, 2, key="s_nv")
    
    st.subheader("⏱️ Base Processing Times")
    dur_trade = st.slider("Trade Proc. (mins)", 30, 120, 60)
    dur_recon = st.slider("Recon (mins)", 30, 180, 90)
    dur_nav = st.slider("NAV Review (mins)", 30, 120, 60)
    latency_gap = st.slider("Hand-off Friction (mins)", 0, 60, 15)

    # --- NEW FEATURE: DYNAMIC DATA ENTRY ---
    st.divider()
    st.markdown("## ➕ Custom Data Engine")
    
    with st.expander("Add Custom Hub"):
        with st.form("hub_form", clear_on_submit=True):
            new_h_name = st.text_input("Full Name (e.g. APAC - SG)")
            new_h_short = st.text_input("Short Code (e.g. SG)", max_chars=4)
            new_h_city = st.text_input("City")
            new_h_offset = st.number_input("GMT Offset (Hours)", -12.0, 14.0, 8.0)
            new_h_rate = st.number_input("Hourly Rate ($)", 10.0, 200.0, 45.0)
            
            if st.form_submit_button("Save Hub"):
                if new_h_name and new_h_short:
                    st.session_state.custom_hubs[new_h_name] = HubInfo(
                        new_h_short, f"GMT{new_h_offset:+g}", new_h_offset, new_h_city, new_h_rate, 0.10
                    )
                    st.rerun()

    with st.expander("Add Custom Task"):
        with st.form("task_form", clear_on_submit=True):
            new_t_name = st.text_input("Task Name")
            new_t_hub = st.selectbox("Assigned Hub", HUBS)
            new_t_start = st.time_input("Start Time (GMT)", time(18, 30))
            new_t_dur = st.number_input("Duration (mins)", 5, 240, 30)
            new_t_staff = st.number_input("Staff Count", 1, 10, 1)
            
            if st.form_submit_button("Save Task"):
                if new_t_name:
                    st.session_state.custom_tasks.append({
                        "name": new_t_name, "hub": new_t_hub, 
                        "time": new_t_start, "dur": new_t_dur, "staff": new_t_staff
                    })
                    st.rerun()

    if st.button("🗑️ Clear Custom Data"):
        st.session_state.custom_hubs = {}
        st.session_state.custom_tasks = []
        st.rerun()

# ---------------------------------------------------------------------
# Core Logic & Timeline Assembly
# ---------------------------------------------------------------------
tasks = []
warnings = []

# Base Datetimes
broker_dt = datetime.combine(T_DATE, time(16, 30))
ta_dt = datetime.combine(T_DATE, time(17, 0))
pricing_dt = datetime.combine(T_DATE, time(16, 15))
batch1_start = datetime.combine(T_DATE, time(18, 0))
batch2_start = datetime.combine(T1_DATE, time(2, 0))
batch3_start = datetime.combine(T1_DATE, time(5, 30))

tasks.extend([
    dict(Task="Broker Files", Start=broker_dt, End=add_mins(broker_dt, 5), Hub="Custody", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task="Pricing Feed", Start=pricing_dt, End=add_mins(pricing_dt, 5), Hub="Market Data", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task="TA Files", Start=ta_dt, End=add_mins(ta_dt, 5), Hub="Transfer Agency", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task="Batch 1", Start=batch1_start, End=add_mins(batch1_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
    dict(Task="Batch 2", Start=batch2_start, End=add_mins(batch2_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
    dict(Task="Batch 3", Start=batch3_start, End=add_mins(batch3_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
])

# 1. Trade Processing
tp_actual_dur = get_compressed_duration(dur_trade, staff_trade, HUB_DATA[hub_trade].overhead_factor)
tp_start = max(broker_dt, pricing_dt, VALUATION_POINT)
tp_end = add_mins(tp_start, tp_actual_dur)
tp_cost = (tp_actual_dur / 60) * HUB_DATA[hub_trade].hourly_rate * staff_trade
tasks.append(dict(Task="Trade Processing", Start=tp_start, End=tp_end, Hub=hub_trade, Cat="Trade Date Processing", Cost=tp_cost, Staff=staff_trade))

# Batch 1 Miss Logic
if tp_end > batch1_start:
    warnings.append("⚠️ **Batch 1 Missed!** Trade processing finished after 18:00 GMT.")
    recon_base = add_mins(batch2_start, 30)
else:
    recon_base = add_mins(batch1_start, 30)

# 2. Reconciliation
recon_wait = latency_gap if hub_trade != hub_recon else 0
rec_actual_dur = get_compressed_duration(dur_recon, staff_recon, HUB_DATA[hub_recon].overhead_factor)
recon_start = max(recon_base, ta_dt) + timedelta(minutes=recon_wait)
recon_end = add_mins(recon_start, rec_actual_dur)
rec_cost = (rec_actual_dur / 60) * HUB_DATA[hub_recon].hourly_rate * staff_recon
tasks.append(dict(Task="Reconciliation", Start=recon_start, End=recon_end, Hub=hub_recon, Cat="Reconciliation", Cost=rec_cost, Staff=staff_recon))

# 3. NAV Review
nav_wait = latency_gap if hub_recon != hub_nav else 0
nav_actual_dur = get_compressed_duration(dur_nav, staff_nav, HUB_DATA[hub_nav].overhead_factor)
nav_start = max(recon_end, add_mins(batch3_start, 30)) + timedelta(minutes=nav_wait)
nav_end = add_mins(nav_start, nav_actual_dur)
nav_cost = (nav_actual_dur / 60) * HUB_DATA[hub_nav].hourly_rate * staff_nav
tasks.append(dict(Task="Final NAV Review", Start=nav_start, End=nav_end, Hub=hub_nav, Cat="T+1 Review", Cost=nav_cost, Staff=staff_nav))

# 4. Publication
pub_start = nav_end
pub_end = add_mins(pub_start, 15)
tasks.append(dict(Task="NAV Publication", Start=pub_start, End=pub_end, Hub=hub_nav, Cat="Publication", Cost=0, Staff=0))

# --- INJECT DYNAMIC CUSTOM TASKS ---
for ct in st.session_state.custom_tasks:
    # If time is before 12:00 PM, assume it happens on T+1 morning
    t_day = T1_DATE if ct["time"].hour < 12 else T_DATE
    c_start = datetime.combine(t_day, ct["time"])
    
    c_hub_info = HUB_DATA[ct["hub"]]
    c_dur = get_compressed_duration(ct["dur"], ct["staff"], c_hub_info.overhead_factor)
    c_end = add_mins(c_start, c_dur)
    c_cost = (c_dur / 60) * c_hub_info.hourly_rate * ct["staff"]
    
    tasks.append(dict(Task=ct["name"], Start=c_start, End=c_end, Hub=ct["hub"], Cat="Custom Task", Cost=c_cost, Staff=ct["staff"]))

sla_met = pub_end <= NAV_DEADLINE
df_tasks = pd.DataFrame(tasks)
total_op_cost = df_tasks['Cost'].sum()
total_headcount = df_tasks['Staff'].sum()

# ---------------------------------------------------------------------
# Main Dashboard UI
# ---------------------------------------------------------------------
st.markdown('<div class="main-header"><h1>🏦 Extensible UCITS Operations Modeler</h1><p>Dynamic Hub & Task Injection Engine enabled.</p></div>', unsafe_allow_html=True)

# Top Metrics
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    sla_class = "sla-met" if sla_met else "sla-breach"
    st.markdown(f'<div class="sla-card {sla_class}"><div class="sla-label">NAV Delivery SLA</div><div class="sla-value">{"✅ MET" if sla_met else "❌ BREACH"}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="info-card"><div class="label">NAV Published</div><div class="value">{fmt_gmt(pub_end)} GMT</div><div class="sub">{fmt_est(pub_end)} EST</div></div>', unsafe_allow_html=True)
with col3: 
    buffer = int((NAV_DEADLINE - pub_end).total_seconds() / 60)
    color = "#00d4aa" if buffer >= 0 else "#ff4444"
    st.markdown(f'<div class="info-card"><div class="label">Buffer to SLA</div><div class="value" style="color:{color}">{buffer} mins</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="info-card"><div class="label">Op Run Cost</div><div class="value cost-text">${total_op_cost:,.2f}</div></div>', unsafe_allow_html=True)
with col5: st.markdown(f'<div class="info-card"><div class="label">Total Managed Headcount</div><div class="value">{int(total_headcount)} FTEs</div></div>', unsafe_allow_html=True)

for w in warnings: st.warning(w)

# Gantt Chart
st.markdown("### 📊 Lifecycle Timeline")
fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
fig.update_yaxes(autorange="reversed")

# Datetime Plotly Bug Fix
fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text="VP 16:00 GMT", annotation_position="top left")
fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text="SLA 09:00 GMT", annotation_position="top left")

fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30))
st.plotly_chart(fig, use_container_width=True)

# Detailed Schedule
with st.expander("📋 Detailed Chronological Schedule & Cost Breakdown", expanded=True):
    display_df = df_tasks.copy().sort_values(by="Start")
    display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
    display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
    display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
    display_df['Cost'] = display_df['Cost'].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
    
    st.dataframe(display_df[['Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Cost']], use_container_width=True, hide_index=True)