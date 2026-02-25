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
    .unit-text { color: #fbbf24; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Dynamic Database (Session State)
# ---------------------------------------------------------------------
@dataclass
class HubInfo:
    short: str
    tz_name: str
    gmt_offset: float
    city: str
    hourly_rate: float
    overhead_factor: float 

if 'hub_dict' not in st.session_state:
    st.session_state.hub_dict = {
        "EMEA - Dublin": HubInfo("DUB", "GMT", 0, "Dublin", 85.0, 0.01),
        "APAC - India": HubInfo("IND", "IST", +5.5, "Mumbai", 25.0, 0.02),
        "NAM - New York": HubInfo("NYC", "EST", -5, "New York", 100.0, 0.015),
    }

if 'custom_tasks' not in st.session_state: st.session_state.custom_tasks = []

if 'baseline_names' not in st.session_state:
    st.session_state.baseline_names = {
        "t_broker": "Broker Files", "t_price": "Pricing Feed", "t_ta": "TA Files",
        "t_tp": "Trade Processing", "t_recon": "Reconciliation", "t_nav": "Final NAV Review",
        "t_pub": "NAV Publication", "b_1": "Batch 1", "b_2": "Batch 2", "b_3": "Batch 3"
    }

# NEW: Baseline Timings Session State
if 'baseline_times' not in st.session_state:
    st.session_state.baseline_times = {
        "broker": time(16, 30), "ta": time(17, 0), "pricing": time(16, 15),
        "b1": time(18, 0), "b2": time(2, 0), "b3": time(5, 30)
    }

HUBS = list(st.session_state.hub_dict.keys())
def get_hub_idx(name_substring):
    for i, h in enumerate(HUBS):
        if name_substring in h: return i
    return 0

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
    if n_staff == 1: return float(total_workload_mins)
    return (total_workload_mins / n_staff) * (1 + (overhead * (n_staff - 1)))

# ---------------------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Volume & Capacity")
    total_funds = st.slider("Total Fund Volume", 1, 1000, 100)
    
    with st.expander("⏱️ Average Time Per Fund", expanded=False):
        avg_trade = st.number_input(st.session_state.baseline_names["t_tp"] + " (mins)", 1.0, 60.0, 5.0)
        avg_recon = st.number_input(st.session_state.baseline_names["t_recon"] + " (mins)", 1.0, 60.0, 15.0)
        avg_nav = st.number_input(st.session_state.baseline_names["t_nav"] + " (mins)", 1.0, 60.0, 10.0)

    st.divider()
    st.markdown("## 👥 Operating Model")
    
    hub_trade = st.selectbox("Assign: " + st.session_state.baseline_names["t_tp"], HUBS, index=get_hub_idx("India"))
    staff_trade = st.slider("Staff Count", 1, 50, 10, key="s_tr")
    
    hub_recon = st.selectbox("Assign: " + st.session_state.baseline_names["t_recon"], HUBS, index=get_hub_idx("Dublin"))
    staff_recon = st.slider("Staff Count", 1, 50, 20, key="s_rc")
    
    hub_nav = st.selectbox("Assign: " + st.session_state.baseline_names["t_nav"], HUBS, index=get_hub_idx("Dublin"))
    staff_nav = st.slider("Staff Count", 1, 50, 10, key="s_nv")
    
    latency_gap = st.slider("Inter-Hub Hand-off (mins)", 0, 60, 15)

    st.divider()
    st.markdown("## ✏️ Data Management")

    # --- NEW FEATURE: EDIT BASELINE TIMINGS ---
    with st.expander("🛠️ Edit Baseline Timings (GMT)"):
        with st.form("edit_timings_form"):
            st.markdown("**Data Ingestion Assumptions**")
            e_broker = st.time_input("Broker Files Arrival", st.session_state.baseline_times["broker"])
            e_pricing = st.time_input("Pricing Feed Arrival", st.session_state.baseline_times["pricing"])
            e_ta = st.time_input("TA Files Arrival", st.session_state.baseline_times["ta"])
            
            st.markdown("**System Batch Schedules**")
            e_b1 = st.time_input("Batch 1 Run (T)", st.session_state.baseline_times["b1"])
            e_b2 = st.time_input("Batch 2 Run (Overnight)", st.session_state.baseline_times["b2"])
            e_b3 = st.time_input("Batch 3 Run (Final)", st.session_state.baseline_times["b3"])
            
            if st.form_submit_button("Update System Timings"):
                st.session_state.baseline_times.update({
                    "broker": e_broker, "pricing": e_pricing, "ta": e_ta,
                    "b1": e_b1, "b2": e_b2, "b3": e_b3
                })
                st.rerun()
    
    with st.expander("➕ Add New Hub"):
        with st.form("hub_add_form", clear_on_submit=True):
            n_h_name = st.text_input("Full Name (e.g. APAC - SG)")
            n_h_short = st.text_input("Short Code", max_chars=4)
            n_h_offset = st.number_input("GMT Offset (Hours)", -12.0, 14.0, 8.0)
            n_h_rate = st.number_input("Hourly Rate ($)", 10.0, 300.0, 45.0)
            if st.form_submit_button("Save Hub"):
                if n_h_name and n_h_short:
                    st.session_state.hub_dict[n_h_name] = HubInfo(n_h_short, f"GMT{n_h_offset:+g}", n_h_offset, "Custom", n_h_rate, 0.02)
                    st.rerun()

    with st.expander("🛠️ Edit / Manage Hubs"):
        edit_hub_key = st.selectbox("Select Hub to Edit", HUBS)
        if edit_hub_key:
            h_info = st.session_state.hub_dict[edit_hub_key]
            with st.form("hub_edit_form"):
                e_name = st.text_input("Hub Name", edit_hub_key)
                e_short = st.text_input("Short Code", h_info.short, max_chars=4)
                e_rate = st.number_input("Hourly Rate ($)", 10.0, 300.0, float(h_info.hourly_rate))
                e_offset = st.number_input("GMT Offset (Hours)", -12.0, 14.0, float(h_info.gmt_offset))
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Update Hub"):
                        st.session_state.hub_dict[e_name] = HubInfo(e_short, f"GMT{e_offset:+g}", e_offset, h_info.city, e_rate, h_info.overhead_factor)
                        if e_name != edit_hub_key: 
                            del st.session_state.hub_dict[edit_hub_key]
                            for t in st.session_state.custom_tasks:
                                if t["hub"] == edit_hub_key: t["hub"] = e_name
                        st.rerun()
                with col2:
                    if st.form_submit_button("Delete Hub"):
                        if len(st.session_state.hub_dict) > 1:
                            del st.session_state.hub_dict[edit_hub_key]
                            st.rerun()
                        else: st.error("Cannot delete the last hub.")

    with st.expander("➕ Add Custom Task"):
        with st.form("task_form", clear_on_submit=True):
            n_t_name = st.text_input("Task Name")
            n_t_hub = st.selectbox("Assigned Hub", HUBS)
            n_t_start = st.time_input("Start Time (GMT)", time(18, 30))
            n_t_dur = st.number_input("Duration (mins)", 5, 240, 30)
            n_t_staff = st.number_input("Staff Count", 1, 10, 1)
            if st.form_submit_button("Save Task"):
                if n_t_name:
                    st.session_state.custom_tasks.append({"name": n_t_name, "hub": n_t_hub, "time": n_t_start, "dur": n_t_dur, "staff": n_t_staff})
                    st.rerun()

    if st.session_state.custom_tasks:
        with st.expander("🛠️ Edit Custom Tasks"):
            task_list = [t["name"] for t in st.session_state.custom_tasks]
            edit_task_name = st.selectbox("Select Task", task_list)
            if edit_task_name:
                t_idx = task_list.index(edit_task_name)
                t_data = st.session_state.custom_tasks[t_idx]
                with st.form("edit_task_form"):
                    e_t_name = st.text_input("Task Name", t_data["name"])
                    hub_idx = HUBS.index(t_data["hub"]) if t_data["hub"] in HUBS else 0
                    e_t_hub = st.selectbox("Hub", HUBS, index=hub_idx)
                    e_t_dur = st.number_input("Duration (mins)", 1, 500, int(t_data["dur"]))
                    e_t_staff = st.number_input("Staff", 1, 50, int(t_data["staff"]))
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.form_submit_button("Update Task"):
                            st.session_state.custom_tasks[t_idx] = {"name": e_t_name, "hub": e_t_hub, "time": t_data["time"], "dur": e_t_dur, "staff": e_t_staff}
                            st.rerun()
                    with c2:
                        if st.form_submit_button("Delete Task"):
                            st.session_state.custom_tasks.pop(t_idx)
                            st.rerun()

    with st.expander("✏️ Rename Baseline Tasks"):
        with st.form("rename_form"):
            new_t_tp = st.text_input("Trade Processing Task", st.session_state.baseline_names["t_tp"])
            new_t_rec = st.text_input("Reconciliation Task", st.session_state.baseline_names["t_recon"])
            new_t_nav = st.text_input("NAV Review Task", st.session_state.baseline_names["t_nav"])
            if st.form_submit_button("Update Names"):
                st.session_state.baseline_names.update({"t_tp": new_t_tp, "t_recon": new_t_rec, "t_nav": new_t_nav})
                st.rerun()

    if st.button("🗑️ Factory Reset App"):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------------------
# Core Logic & Timeline Assembly
# ---------------------------------------------------------------------
tasks = []
warnings = []
bn = st.session_state.baseline_names
hd = st.session_state.hub_dict
bt = st.session_state.baseline_times

# NOW USING DYNAMIC BASELINE TIMES
broker_dt = datetime.combine(T_DATE, bt["broker"])
ta_dt = datetime.combine(T_DATE, bt["ta"])
pricing_dt = datetime.combine(T_DATE, bt["pricing"])
batch1_start = datetime.combine(T_DATE, bt["b1"])

# Smart logic for overnight batches: if time is PM, it might still be T_DATE, otherwise T1_DATE
b2_day = T_DATE if bt["b2"].hour >= 18 else T1_DATE
batch2_start = datetime.combine(b2_day, bt["b2"])

b3_day = T_DATE if bt["b3"].hour >= 18 else T1_DATE
batch3_start = datetime.combine(b3_day, bt["b3"])

tasks.extend([
    dict(Task=bn["t_broker"], Start=broker_dt, End=add_mins(broker_dt, 5), Hub="Custody", Cat="Data Ingestion", Cost_Raw=0, Staff=0),
    dict(Task=bn["t_price"], Start=pricing_dt, End=add_mins(pricing_dt, 5), Hub="Market Data", Cat="Data Ingestion", Cost_Raw=0, Staff=0),
    dict(Task=bn["t_ta"], Start=ta_dt, End=add_mins(ta_dt, 5), Hub="Transfer Agency", Cat="Data Ingestion", Cost_Raw=0, Staff=0),
    dict(Task=bn["b_1"], Start=batch1_start, End=add_mins(batch1_start, 30), Hub="Systems", Cat="Batch Run", Cost_Raw=0, Staff=0),
    dict(Task=bn["b_2"], Start=batch2_start, End=add_mins(batch2_start, 30), Hub="Systems", Cat="Batch Run", Cost_Raw=0, Staff=0),
    dict(Task=bn["b_3"], Start=batch3_start, End=add_mins(batch3_start, 30), Hub="Systems", Cat="Batch Run", Cost_Raw=0, Staff=0),
])

# 1. Trade Processing
tp_workload_mins = total_funds * avg_trade
tp_actual_dur = get_concurrent_duration(tp_workload_mins, staff_trade, hd[hub_trade].overhead_factor)
tp_start = max(broker_dt, pricing_dt, VALUATION_POINT)
tp_end = add_mins(tp_start, tp_actual_dur)
tp_cost = (tp_actual_dur / 60) * hd[hub_trade].hourly_rate * staff_trade
tasks.append(dict(Task=bn["t_tp"], Start=tp_start, End=tp_end, Hub=hub_trade, Cat="Trade Date Processing", Cost_Raw=tp_cost, Staff=staff_trade))

if tp_end > batch1_start:
    warnings.append(f"⚠️ **{bn['b_1']} Missed!** Tasks delayed until Batch 2.")
    recon_base = add_mins(batch2_start, 30)
else:
    recon_base = add_mins(batch1_start, 30)

# 2. Reconciliation
recon_workload_mins = total_funds * avg_recon
recon_wait = latency_gap if hub_trade != hub_recon else 0
rec_actual_dur = get_concurrent_duration(recon_workload_mins, staff_recon, hd[hub_recon].overhead_factor)
recon_start = max(recon_base, ta_dt) + timedelta(minutes=recon_wait)
recon_end = add_mins(recon_start, rec_actual_dur)
rec_cost = (rec_actual_dur / 60) * hd[hub_recon].hourly_rate * staff_recon
tasks.append(dict(Task=bn["t_recon"], Start=recon_start, End=recon_end, Hub=hub_recon, Cat="Reconciliation", Cost_Raw=rec_cost, Staff=staff_recon))

# 3. NAV Review
nav_workload_mins = total_funds * avg_nav
nav_wait = latency_gap if hub_recon != hub_nav else 0
nav_actual_dur = get_concurrent_duration(nav_workload_mins, staff_nav, hd[hub_nav].overhead_factor)
nav_start = max(recon_end, add_mins(batch3_start, 30)) + timedelta(minutes=nav_wait)
nav_end = add_mins(nav_start, nav_actual_dur)
nav_cost = (nav_actual_dur / 60) * hd[hub_nav].hourly_rate * staff_nav
tasks.append(dict(Task=bn["t_nav"], Start=nav_start, End=nav_end, Hub=hub_nav, Cat="T+1 Review", Cost_Raw=nav_cost, Staff=staff_nav))

# 4. Publication
pub_start = nav_end
pub_end = add_mins(pub_start, 15)
tasks.append(dict(Task=bn["t_pub"], Start=pub_start, End=pub_end, Hub=hub_nav, Cat="Publication", Cost_Raw=0, Staff=0))

# Custom Tasks Injection
for ct in st.session_state.custom_tasks:
    c_hub_name = ct["hub"] if ct["hub"] in hd else list(hd.keys())[0] 
    t_day = T1_DATE if ct["time"].hour < 12 else T_DATE
    c_start = datetime.combine(t_day, ct["time"])
    c_hub_info = hd[c_hub_name]
    c_dur = get_concurrent_duration(ct["dur"], ct["staff"], c_hub_info.overhead_factor)
    c_end = add_mins(c_start, c_dur)
    c_cost = (c_dur / 60) * c_hub_info.hourly_rate * ct["staff"]
    tasks.append(dict(Task=ct["name"], Start=c_start, End=c_end, Hub=c_hub_name, Cat="Custom Task", Cost_Raw=c_cost, Staff=ct["staff"]))

sla_met = pub_end <= NAV_DEADLINE
df_tasks = pd.DataFrame(tasks)
total_op_cost = df_tasks['Cost_Raw'].sum()
total_headcount = df_tasks['Staff'].sum()
unit_cost_overall = total_op_cost / total_funds
df_tasks['Cost'] = df_tasks['Cost_Raw'].apply(lambda x: f"${x:,.2f}")

# ---------------------------------------------------------------------
# Main Dashboard UI
# ---------------------------------------------------------------------
st.markdown(f'<div class="main-header"><h1>🏦 Enterprise Capacity & Timelines</h1><p>Modeling {total_funds} funds concurrently across {int(total_headcount)} FTEs.</p></div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    sla_class = "sla-met" if sla_met else "sla-breach"
    st.markdown(f'<div class="sla-card {sla_class}"><div class="sla-label">SLA Status</div><div class="sla-value">{"✅ MET" if sla_met else "❌ BREACH"}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="info-card"><div class="label">Book Published</div><div class="value">{fmt_gmt(pub_end)} GMT</div></div>', unsafe_allow_html=True)
with col3: 
    buffer = int((NAV_DEADLINE - pub_end).total_seconds() / 60)
    color = "#00d4aa" if buffer >= 0 else "#ff4444"
    st.markdown(f'<div class="info-card"><div class="label">Buffer to SLA</div><div class="value" style="color:{color}">{buffer} mins</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="info-card"><div class="label">Total Variable Cost</div><div class="value cost-text">${total_op_cost:,.2f}</div></div>', unsafe_allow_html=True)
with col5: st.markdown(f'<div class="info-card"><div class="label">Total Volume</div><div class="value">{total_funds} Funds</div></div>', unsafe_allow_html=True)
with col6: st.markdown(f'<div class="info-card"><div class="label">Unit Economics</div><div class="value unit-text">${unit_cost_overall:,.2f} / Fund</div></div>', unsafe_allow_html=True)

for w in warnings: st.warning(w)

st.markdown("### 📊 Concurrent Lifecycle Timeline")
fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
fig.update_yaxes(autorange="reversed")
fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text="VP 16:00 GMT", annotation_position="top left")
fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text="SLA 09:00 GMT", annotation_position="top left")
fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30))
st.plotly_chart(fig, use_container_width=True)

with st.expander("📋 Detailed Workload, Capacity & Unit Economics", expanded=True):
    display_df = df_tasks.copy().sort_values(by="Start")
    display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
    display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
    display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
    display_df['Cost/Fund'] = (display_df['Cost_Raw'] / total_funds).apply(lambda x: f"${x:.2f}" if x > 0 else "-")
    display_df['Total Cost'] = display_df['Cost_Raw'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
    st.dataframe(display_df[['Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Total Cost', 'Cost/Fund']], use_container_width=True, hide_index=True)