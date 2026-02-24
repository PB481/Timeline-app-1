# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, time, date
from dataclasses import dataclass
from typing import List, Dict

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
    .info-card .sub { font-size: 0.72rem; color: #ff8844; margin-top: 0.1rem; }
    .cost-text { color: #85e89d; }
    .tz-strip { display: flex; gap: 0; border-radius: 10px; overflow: hidden; border: 1px solid #1e2d44; margin-bottom: 1rem; }
    .tz-cell { flex: 1; padding: 0.7rem 0.6rem; text-align: center; background: #0e1a2e; border-right: 1px solid #1e2d44; }
    .tz-cell:last-child { border-right: none; }
    .tz-city { font-size: 0.62rem; text-transform: uppercase; color: #667788; margin-bottom: 0.15rem; }
    .tz-time { font-size: 1.05rem; font-weight: 700; color: #c8d8e8; }
    .tz-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; }
    .tz-dot.on { background: #00d4aa; }
    .tz-dot.off { background: #ff4444; opacity: 0.5; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Enhanced Hub Definitions (Timezones + Financials)
# ---------------------------------------------------------------------
@dataclass
class HubInfo:
    short: str
    tz_name: str
    gmt_offset: float
    window_start_gmt: int
    window_end_gmt: int
    city: str
    hourly_rate: float
    overhead_factor: float

HUB_DATA = {
    "EMEA - Dublin":       HubInfo("EMEA-DUB", "GMT", 0, 7*60, 19*60, "Dublin", 85.0, 0.05),
    "EMEA - Luxembourg":   HubInfo("EMEA-LUX", "CET", +1, 6*60, 18*60, "Luxembourg", 90.0, 0.05),
    "APAC - India":        HubInfo("APAC-IND", "IST", +5.5, 3*60+30, 14*60+30, "Mumbai", 25.0, 0.12),
    "APAC - Philippines":  HubInfo("APAC-PHL", "PHT", +8, 1*60, 12*60, "Manila", 22.0, 0.12),
    "NAM - New York":      HubInfo("NAM-NYC", "EST", -5, 13*60, 24*60, "New York", 100.0, 0.08),
}
HUBS = list(HUB_DATA.keys())
CATEGORY_COLORS = {
    "Data Ingestion": "#3b82f6", "Batch Run": "#8b5cf6", "Trade Date Processing": "#f59e0b",
    "Reconciliation": "#06b6d4", "Valuation": "#ec4899", "T+1 Review": "#10b981", "Publication": "#00d4aa"
}

T_DATE = date.today()
T1_DATE = T_DATE + timedelta(days=1)
VALUATION_POINT = datetime.combine(T_DATE, time(16, 0))
NAV_DEADLINE = datetime.combine(T1_DATE, time(9, 0))

# ---------------------------------------------------------------------
# Timezone & Logic Helpers
# ---------------------------------------------------------------------
def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def fmt_est(dt: datetime) -> str: return (dt + timedelta(hours=-5)).strftime("%H:%M")
def fmt_local(dt: datetime, hub: str) -> str: return (dt + timedelta(hours=HUB_DATA[hub].gmt_offset)).strftime("%H:%M") if hub in HUB_DATA else fmt_gmt(dt)
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=int(mins))

def get_compressed_duration(base_mins: int, n_staff: int, overhead: float) -> float:
    if n_staff == 1: return float(base_mins)
    return base_mins / (n_staff ** 0.7) * (1 + (overhead * n_staff))

# ---------------------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Operating Model")
    
    st.subheader("🌐 Hubs & Headcount")
    hub_trade = st.selectbox("Trade Processing", HUBS, index=2)
    staff_trade = st.slider("Trade Staff", 1, 10, 3, key="s_tr")
    
    hub_recon = st.selectbox("Reconciliations", HUBS, index=0)
    staff_recon = st.slider("Recon Staff", 1, 10, 4, key="s_rc")
    
    hub_nav = st.selectbox("NAV Review & Pub", HUBS, index=0)
    staff_nav = st.slider("Review Staff", 1, 5, 2, key="s_nv")
    
    st.subheader("⏱️ Base Processing Times")
    dur_trade = st.slider("Trade Proc. (mins)", 30, 120, 60)
    dur_recon = st.slider("Recon (mins)", 30, 180, 90)
    dur_nav = st.slider("NAV Review (mins)", 30, 120, 60)
    
    st.subheader("⚠️ Resiliency Levers")
    stress_mode = st.toggle("Enable Stress Scenario (Data Delays)")
    latency_gap = st.slider("Inter-Hub Hand-off Friction (mins)", 0, 60, 15)

    st.subheader("📥 Data Cutoffs (GMT)")
    broker_time = time(17, 0) if stress_mode else time(16, 30)
    ta_time = time(17, 30) if stress_mode else time(17, 0)
    pricing_time = time(16, 45) if stress_mode else time(16, 15)
    
    b1_time = time(18, 0)
    b2_time = time(2, 0)
    b3_time = time(5, 30)

# ---------------------------------------------------------------------
# Core Logic & Timeline Assembly
# ---------------------------------------------------------------------
tasks = []
warnings = []

# Base Datetimes
broker_dt = datetime.combine(T_DATE, broker_time)
ta_dt = datetime.combine(T_DATE, ta_time)
pricing_dt = datetime.combine(T_DATE, pricing_time)
batch1_start = datetime.combine(T_DATE, b1_time)
batch2_start = datetime.combine(T1_DATE, b2_time)
batch3_start = datetime.combine(T1_DATE, b3_time)

tasks.extend([
    dict(Task="Broker Files", Start=broker_dt, End=add_mins(broker_dt, 5), Hub="Custody", Cat="Data Ingestion", Cost=0),
    dict(Task="Pricing Feed", Start=pricing_dt, End=add_mins(pricing_dt, 5), Hub="Market Data", Cat="Data Ingestion", Cost=0),
    dict(Task="TA Files", Start=ta_dt, End=add_mins(ta_dt, 5), Hub="Transfer Agency", Cat="Data Ingestion", Cost=0),
    dict(Task="Batch 1", Start=batch1_start, End=add_mins(batch1_start, 30), Hub="Systems", Cat="Batch Run", Cost=0),
    dict(Task="Batch 2", Start=batch2_start, End=add_mins(batch2_start, 30), Hub="Systems", Cat="Batch Run", Cost=0),
    dict(Task="Batch 3", Start=batch3_start, End=add_mins(batch3_start, 30), Hub="Systems", Cat="Batch Run", Cost=0),
])

# 1. Trade Processing
tp_actual_dur = get_compressed_duration(dur_trade, staff_trade, HUB_DATA[hub_trade].overhead_factor)
tp_start = max(broker_dt, pricing_dt, VALUATION_POINT)
tp_end = add_mins(tp_start, tp_actual_dur)
tp_cost = (tp_actual_dur / 60) * HUB_DATA[hub_trade].hourly_rate * staff_trade
tasks.append(dict(Task="Trade Processing", Start=tp_start, End=tp_end, Hub=hub_trade, Cat="Trade Date Processing", Cost=tp_cost))

# Batch 1 Miss Logic
if tp_end > batch1_start:
    warnings.append("⚠️ **Batch 1 Missed!** Trade processing finished after 18:00 GMT. Subsequent tasks pushed to Batch 2.")
    recon_base = add_mins(batch2_start, 30) # Wait for Batch 2
else:
    recon_base = add_mins(batch1_start, 30)

# 2. Reconciliation
recon_wait = latency_gap if hub_trade != hub_recon else 0
rec_actual_dur = get_compressed_duration(dur_recon, staff_recon, HUB_DATA[hub_recon].overhead_factor)
recon_start = max(recon_base, ta_dt) + timedelta(minutes=recon_wait)
recon_end = add_mins(recon_start, rec_actual_dur)
rec_cost = (rec_actual_dur / 60) * HUB_DATA[hub_recon].hourly_rate * staff_recon
tasks.append(dict(Task="Reconciliation", Start=recon_start, End=recon_end, Hub=hub_recon, Cat="Reconciliation", Cost=rec_cost))

# 3. NAV Review
nav_wait = latency_gap if hub_recon != hub_nav else 0
nav_actual_dur = get_compressed_duration(dur_nav, staff_nav, HUB_DATA[hub_nav].overhead_factor)
nav_start = max(recon_end, add_mins(batch3_start, 30)) + timedelta(minutes=nav_wait)
nav_end = add_mins(nav_start, nav_actual_dur)
nav_cost = (nav_actual_dur / 60) * HUB_DATA[hub_nav].hourly_rate * staff_nav
tasks.append(dict(Task="Final NAV Review", Start=nav_start, End=nav_end, Hub=hub_nav, Cat="T+1 Review", Cost=nav_cost))

# 4. Publication
pub_start = nav_end
pub_end = add_mins(pub_start, 15)
tasks.append(dict(Task="NAV Publication", Start=pub_start, End=pub_end, Hub=hub_nav, Cat="Publication", Cost=0))

sla_met = pub_end <= NAV_DEADLINE
df_tasks = pd.DataFrame(tasks)
total_op_cost = df_tasks['Cost'].sum()
total_headcount = staff_trade + staff_recon + staff_nav

# ---------------------------------------------------------------------
# Main Dashboard UI
# ---------------------------------------------------------------------
st.markdown('<div class="main-header"><h1>🏦 Integrated UCITS Timeline & Operations Modeler</h1><p>Models the critical-path timings, multi-hub handoffs, and resource costs from Valuation Point to SLA.</p></div>', unsafe_allow_html=True)

# Original Timezone Clock Strip
tz_cells = ""
for hub_name, info in HUB_DATA.items():
    vp_local = (VALUATION_POINT + timedelta(hours=info.gmt_offset)).strftime('%H:%M')
    active_cls = "active" if hub_name in [hub_trade, hub_recon, hub_nav] else ""
    tz_cells += f'<div class="tz-cell {active_cls}"><div class="tz-city">{info.city}</div><div class="tz-time">{vp_local}</div><div class="tz-city" style="font-size:0.5rem">{info.tz_name} (GMT{info.gmt_offset:g})</div></div>'
st.markdown(f'<div class="tz-strip">{tz_cells}</div>', unsafe_allow_html=True)

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
with col5: st.markdown(f'<div class="info-card"><div class="label">Total Headcount</div><div class="value">{total_headcount} FTEs</div><div class="sub">Across {len(set([hub_trade, hub_recon, hub_nav]))} hubs</div></div>', unsafe_allow_html=True)

for w in warnings: st.warning(w)

# Gantt Chart (Original Formatting with Datetime Bug Fix)
st.markdown("### 📊 Lifecycle Timeline (GMT / EST)")
fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub"])
fig.update_yaxes(autorange="reversed")

# Plotly bug fix: Convert datetimes to timestamps (ms) for annotated vertical lines
fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text="VP 16:00 GMT", annotation_position="top left")
fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text="SLA 09:00 GMT", annotation_position="top left")
us_open_dt = datetime.combine(T_DATE, time(13,0))
fig.add_vline(x=us_open_dt.timestamp() * 1000, line_dash="dot", line_color="#8899aa", annotation_text="US Market Opens (08:00 EST)", annotation_position="bottom right")

fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=450, margin=dict(l=10, r=30, t=30, b=30))
st.plotly_chart(fig, use_container_width=True)

# Detailed Schedule (Original Table + PM Additions)
with st.expander("📋 Detailed Chronological Schedule & Cost Breakdown", expanded=True):
    display_df = df_tasks.copy()
    display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
    display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
    display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
    display_df['Start EST'] = (display_df['Start'] - timedelta(hours=5)).dt.strftime("%H:%M")
    display_df['Cost'] = display_df['Cost'].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
    
    st.dataframe(display_df[['Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Start EST', 'Duration', 'Cost']], use_container_width=True, hide_index=True)