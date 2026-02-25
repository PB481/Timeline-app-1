# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, time, date
from dataclasses import dataclass

# ---------------------------------------------------------------------
# Page config & Styling
# ---------------------------------------------------------------------
st.set_page_config(page_title="UCITS Multi-Fund Capacity Planner", page_icon="🏦", layout="wide")

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
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Session State Initialization 
# ---------------------------------------------------------------------
if 'custom_hubs' not in st.session_state: st.session_state.custom_hubs = {}
if 'custom_tasks' not in st.session_state: st.session_state.custom_tasks = []

if 'baseline_names' not in st.session_state:
    st.session_state.baseline_names = {
        "hub_1": "EMEA - Dublin", "hub_2": "APAC - India", "hub_3": "NAM - New York",
        "t_broker": "Broker Files", "t_price": "Pricing Feed", "t_ta": "TA Files",
        "t_tp": "Trade Processing", "t_recon": "Reconciliation", "t_nav": "Final NAV Review",
        "t_pub": "NAV Publication", "b_1": "Batch 1", "b_2": "Batch 2", "b_3": "Batch 3"
    }

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
    overhead_factor: float # Friction added per additional FTE

# Note: Overhead factors reduced to simulate factory-line queues (vs software dev)
HUB_DATA = {
    st.session_state.baseline_names["hub_1"]: HubInfo("DUB", "GMT", 0, "Dublin", 85.0, 0.01),
    st.session_state.baseline_names["hub_2"]: HubInfo("IND", "IST", +5.5, "Mumbai", 25.0, 0.02),
    st.session_state.baseline_names["hub_3"]: HubInfo("NYC", "EST", -5, "New York", 100.0, 0.015),
}
HUB_DATA.update(st.session_state.custom_hubs)
HUBS = list(HUB_DATA.keys())

CATEGORY_COLORS = {
    "Data Ingestion": "#3b82f6", "Batch Run": "#8b5cf6", "Trade Date Processing": "#f59e0b",
    "Reconciliation": "#06b6d4", "Valuation": "#ec4899", "T+1 Review": "#10b981", "Publication": "#00d4aa", "Custom Task": "#eab308"
}

T_DATE = date.today()
T1_DATE = T_DATE + timedelta(days=1)
VALUATION_POINT = datetime.combine(T_DATE, time(16, 0))
NAV_DEADLINE = datetime.combine(T1_DATE, time(9, 0))

def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def fmt_est(dt: datetime) -> str: return (dt + timedelta(hours=-5)).strftime("%H:%M")
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=int(mins))

def get_concurrent_duration(total_workload_mins: float, n_staff: int, overhead: float) -> float:
    """Calculates timeline duration by dividing total man-hours across concurrent staff, plus management friction."""
    if n_staff == 1: return float(total_workload_mins)
    return (total_workload_mins / n_staff) * (1 + (overhead * (n_staff - 1)))

# ---------------------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Volume & Capacity")
    
    # --- UPGRADED: Multi-Fund Workload Engine ---
    total_funds = st.slider("Total Fund Volume", 1, 1000, 100, 
                            help="The total number of funds in this processing batch. This scales the total required man-hours.")
    
    with st.expander("⏱️ Average Time Per Fund", expanded=False):
        st.markdown("Set the baseline time it takes one FTE to process a **single average fund** at each stage.", 
                    help="Total Workload = (Funds × Avg Time per Fund). E.g., 100 funds × 5 mins = 500 total minutes of work.")
        avg_trade = st.number_input(st.session_state.baseline_names["t_tp"] + " (mins/fund)", 1.0, 60.0, 5.0)
        avg_recon = st.number_input(st.session_state.baseline_names["t_recon"] + " (mins/fund)", 1.0, 60.0, 15.0)
        avg_nav = st.number_input(st.session_state.baseline_names["t_nav"] + " (mins/fund)", 1.0, 60.0, 10.0)

    st.divider()
    st.markdown("## 👥 Operating Model")
    
    hub_trade = st.selectbox("Assign: " + st.session_state.baseline_names["t_tp"], HUBS, index=1,
                             help="Select geographic location. Applies the hub's local timezone and cost-per-FTE.")
    staff_trade = st.slider("Staff Count", 1, 50, 10, key="s_tr",
                            help="Number of FTEs processing the fund volume concurrently. Divides the total workload, but adds slight coordination overhead.")
    
    hub_recon = st.selectbox("Assign: " + st.session_state.baseline_names["t_recon"], HUBS, index=0,
                             help="Select geographic location. Applies the hub's local timezone and cost-per-FTE.")
    staff_recon = st.slider("Staff Count", 1, 50, 20, key="s_rc",
                            help="Number of FTEs processing the fund volume concurrently.")
    
    hub_nav = st.selectbox("Assign: " + st.session_state.baseline_names["t_nav"], HUBS, index=0,
                           help="Select geographic location. Applies the hub's local timezone and cost-per-FTE.")
    staff_nav = st.slider("Staff Count", 1, 50, 10, key="s_nv",
                          help="Number of FTEs processing the fund volume concurrently.")
    
    latency_gap = st.slider("Inter-Hub Hand-off (mins)", 0, 60, 15,
                            help="Dead-time (latency) added to the timeline when consecutive tasks are performed by different hubs (e.g., waiting for emails, system syncs). If the same hub does both tasks, this penalty is zero.")

    st.divider()
    st.markdown("## ✏️ Data Management")
    with st.expander("✏️ Rename Baseline Hubs & Tasks"):
        with st.form("rename_form"):
            st.markdown("**Hub Names**")
            new_h1 = st.text_input("Hub 1", st.session_state.baseline_names["hub_1"])
            new_h2 = st.text_input("Hub 2", st.session_state.baseline_names["hub_2"])
            new_h3 = st.text_input("Hub 3", st.session_state.baseline_names["hub_3"])
            st.markdown("**Task Names**")
            new_t_tp = st.text_input("Trade Processing Task", st.session_state.baseline_names["t_tp"])
            new_t_rec = st.text_input("Reconciliation Task", st.session_state.baseline_names["t_recon"])
            new_t_nav = st.text_input("NAV Review Task", st.session_state.baseline_names["t_nav"])
            if st.form_submit_button("Update Names"):
                st.session_state.baseline_names.update({"hub_1": new_h1, "hub_2": new_h2, "hub_3": new_h3, "t_tp": new_t_tp, "t_recon": new_t_rec, "t_nav": new_t_nav})
                st.rerun()

    with st.expander("➕ Add Custom Hub"):
        with st.form("hub_form", clear_on_submit=True):
            new_h_name = st.text_input("Full Name (e.g. APAC - SG)")
            new_h_short = st.text_input("Short Code (e.g. SG)", max_chars=4)
            new_h_offset = st.number_input("GMT Offset (Hours)", -12.0, 14.0, 8.0)
            new_h_rate = st.number_input("Hourly Rate ($)", 10.0, 200.0, 45.0, help="Fully loaded operational cost for 1 FTE per hour.")
            if st.form_submit_button("Save Hub"):
                if new_h_name and new_h_short:
                    st.session_state.custom_hubs[new_h_name] = HubInfo(new_h_short, f"GMT{new_h_offset:+g}", new_h_offset, "Custom", new_h_rate, 0.02)
                    st.rerun()

    if st.button("🗑️ Reset All Customizations"):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------------------
# Core Logic & Timeline Assembly
# ---------------------------------------------------------------------
tasks = []
warnings = []
bn = st.session_state.baseline_names

broker_dt = datetime.combine(T_DATE, time(16, 30))
ta_dt = datetime.combine(T_DATE, time(17, 0))
pricing_dt = datetime.combine(T_DATE, time(16, 15))
batch1_start = datetime.combine(T_DATE, time(18, 0))
batch2_start = datetime.combine(T1_DATE, time(2, 0))
batch3_start = datetime.combine(T1_DATE, time(5, 30))

tasks.extend([
    dict(Task=bn["t_broker"], Start=broker_dt, End=add_mins(broker_dt, 5), Hub="Custody", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task=bn["t_price"], Start=pricing_dt, End=add_mins(pricing_dt, 5), Hub="Market Data", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task=bn["t_ta"], Start=ta_dt, End=add_mins(ta_dt, 5), Hub="Transfer Agency", Cat="Data Ingestion", Cost=0, Staff=0),
    dict(Task=bn["b_1"], Start=batch1_start, End=add_mins(batch1_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
    dict(Task=bn["b_2"], Start=batch2_start, End=add_mins(batch2_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
    dict(Task=bn["b_3"], Start=batch3_start, End=add_mins(batch3_start, 30), Hub="Systems", Cat="Batch Run", Cost=0, Staff=0),
])

# 1. Trade Processing
tp_workload_mins = total_funds * avg_trade
tp_actual_dur = get_concurrent_duration(tp_workload_mins, staff_trade, HUB_DATA[hub_trade].overhead_factor)
tp_start = max(broker_dt, pricing_dt, VALUATION_POINT)
tp_end = add_mins(tp_start, tp_actual_dur)
tp_cost = (tp_actual_dur / 60) * HUB_DATA[hub_trade].hourly_rate * staff_trade
tasks.append(dict(Task=bn["t_tp"], Start=tp_start, End=tp_end, Hub=hub_trade, Cat="Trade Date Processing", Cost=tp_cost, Staff=staff_trade))

# Batch 1 Miss Logic
if tp_end > batch1_start:
    warnings.append(f"⚠️ **{bn['b_1']} Missed!** {bn['t_tp']} finished after 18:00 GMT due to high volume. Tasks delayed until Batch 2.")
    recon_base = add_mins(batch2_start, 30)
else:
    recon_base = add_mins(batch1_start, 30)

# 2. Reconciliation
recon_workload_mins = total_funds * avg_recon
recon_wait = latency_gap if hub_trade != hub_recon else 0
rec_actual_dur = get_concurrent_duration(recon_workload_mins, staff_recon, HUB_DATA[hub_recon].overhead_factor)
recon_start = max(recon_base, ta_dt) + timedelta(minutes=recon_wait)
recon_end = add_mins(recon_start, rec_actual_dur)
rec_cost = (rec_actual_dur / 60) * HUB_DATA[hub_recon].hourly_rate * staff_recon
tasks.append(dict(Task=bn["t_recon"], Start=recon_start, End=recon_end, Hub=hub_recon, Cat="Reconciliation", Cost=rec_cost, Staff=staff_recon))

# 3. NAV Review
nav_workload_mins = total_funds * avg_nav
nav_wait = latency_gap if hub_recon != hub_nav else 0
nav_actual_dur = get_concurrent_duration(nav_workload_mins, staff_nav, HUB_DATA[hub_nav].overhead_factor)
nav_start = max(recon_end, add_mins(batch3_start, 30)) + timedelta(minutes=nav_wait)
nav_end = add_mins(nav_start, nav_actual_dur)
nav_cost = (nav_actual_dur / 60) * HUB_DATA[hub_nav].hourly_rate * staff_nav
tasks.append(dict(Task=bn["t_nav"], Start=nav_start, End=nav_end, Hub=hub_nav, Cat="T+1 Review", Cost=nav_cost, Staff=staff_nav))

# 4. Publication
pub_start = nav_end
pub_end = add_mins(pub_start, 15)
tasks.append(dict(Task=bn["t_pub"], Start=pub_start, End=pub_end, Hub=hub_nav, Cat="Publication", Cost=0, Staff=0))

sla_met = pub_end <= NAV_DEADLINE
df_tasks = pd.DataFrame(tasks)
total_op_cost = df_tasks['Cost'].sum()
total_headcount = df_tasks['Staff'].sum()

# ---------------------------------------------------------------------
# Main Dashboard UI
# ---------------------------------------------------------------------
st.markdown(f'<div class="main-header"><h1>🏦 Enterprise Capacity & Timelines</h1><p>Modeling {total_funds} funds concurrently across {int(total_headcount)} FTEs.</p></div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    sla_class = "sla-met" if sla_met else "sla-breach"
    st.markdown(f'<div class="sla-card {sla_class}"><div class="sla-label">NAV Delivery SLA</div><div class="sla-value">{"✅ MET" if sla_met else "❌ BREACH"}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="info-card" title="Time the final fund in the batch is published"><div class="label">Book Published</div><div class="value">{fmt_gmt(pub_end)} GMT</div><div class="sub">{fmt_est(pub_end)} EST</div></div>', unsafe_allow_html=True)
with col3: 
    buffer = int((NAV_DEADLINE - pub_end).total_seconds() / 60)
    color = "#00d4aa" if buffer >= 0 else "#ff4444"
    st.markdown(f'<div class="info-card"><div class="label">Buffer to SLA</div><div class="value" style="color:{color}">{buffer} mins</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="info-card" title="Total variable staffing cost to process this batch"><div class="label">Total Variable Cost</div><div class="value cost-text">${total_op_cost:,.2f}</div></div>', unsafe_allow_html=True)
with col5: st.markdown(f'<div class="info-card"><div class="label">Total Book Volume</div><div class="value">{total_funds} Funds</div></div>', unsafe_allow_html=True)

for w in warnings: st.warning(w)

st.markdown("### 📊 Concurrent Lifecycle Timeline")
fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
fig.update_yaxes(autorange="reversed")
fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text="VP 16:00 GMT", annotation_position="top left")
fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text="SLA 09:00 GMT", annotation_position="top left")
fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30))
st.plotly_chart(fig, use_container_width=True)

with st.expander("📋 Detailed Workload & Cost Breakdown", expanded=True):
    display_df = df_tasks.copy().sort_values(by="Start")
    display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
    display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
    display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
    display_df['Cost'] = display_df['Cost'].apply(lambda x: f"${x:.2f}" if x > 0 else "-")
    st.dataframe(display_df[['Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Cost']], use_container_width=True, hide_index=True)
