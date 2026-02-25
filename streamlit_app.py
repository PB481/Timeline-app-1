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

# NEW: Multi-Day Baseline Timings Session State
if 'baseline_times' not in st.session_state or type(st.session_state.baseline_times.get("broker")) == time:
    st.session_state.baseline_times = {
        "broker": {"time": time(16, 30), "offset": 0}, 
        "ta": {"time": time(17, 0), "offset": 0}, 
        "pricing": {"time": time(16, 15), "offset": 0},
        "b1": {"time": time(18, 0), "offset": 0}, 
        "b2": {"time": time(2, 0), "offset": 1}, 
        "b3": {"time": time(5, 30), "offset": 1}
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
CATEGORIES = list(CATEGORY_COLORS.keys())

T_DATE = date.today()
T1_DATE = T_DATE + timedelta(days=1)
VALUATION_POINT = datetime.combine(T_DATE, time(16, 0))
NAV_DEADLINE = datetime.combine(T1_DATE, time(9, 0))

DAY_OPTIONS = ["T", "T+1", "T+2", "T+3", "T+4", "T+5"]

def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=int(mins))
def get_concurrent_duration(total_workload_mins: float, n_staff: int, overhead: float) -> float:
    if n_staff == 1: return float(total_workload_mins)
    return (total_workload_mins / n_staff) * (1 + (overhead * (n_staff - 1)))
def get_day_label(dt_start: datetime) -> str:
    days_diff = (dt_start.date() - T_DATE).days
    return "T" if days_diff <= 0 else f"T+{days_diff}"

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

    # 1. EDIT BASELINE TIMINGS & DAYS
    with st.expander("🛠️ Edit Baseline Timings (T+X)"):
        with st.form("edit_timings_form"):
            st.markdown("**Data Ingestion Assumptions**")
            c1, c2 = st.columns(2)
            e_broker_t = c1.time_input("Broker Files", st.session_state.baseline_times["broker"]["time"])
            e_broker_d = c2.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["broker"]["offset"], key="bd")
            
            c3, c4 = st.columns(2)
            e_pricing_t = c3.time_input("Pricing Feed", st.session_state.baseline_times["pricing"]["time"])
            e_pricing_d = c4.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["pricing"]["offset"], key="pd")
            
            c5, c6 = st.columns(2)
            e_ta_t = c5.time_input("TA Files", st.session_state.baseline_times["ta"]["time"])
            e_ta_d = c6.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["ta"]["offset"], key="td")
            
            st.markdown("**System Batch Schedules**")
            c7, c8 = st.columns(2)
            e_b1_t = c7.time_input("Batch 1", st.session_state.baseline_times["b1"]["time"])
            e_b1_d = c8.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b1"]["offset"], key="b1d")
            
            c9, c10 = st.columns(2)
            e_b2_t = c9.time_input("Batch 2", st.session_state.baseline_times["b2"]["time"])
            e_b2_d = c10.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b2"]["offset"], key="b2d")
            
            c11, c12 = st.columns(2)
            e_b3_t = c11.time_input("Batch 3", st.session_state.baseline_times["b3"]["time"])
            e_b3_d = c12.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b3"]["offset"], key="b3d")
            
            if st.form_submit_button("Update System Timings"):
                st.session_state.baseline_times.update({
                    "broker": {"time": e_broker_t, "offset": DAY_OPTIONS.index(e_broker_d)},
                    "pricing": {"time": e_pricing_t, "offset": DAY_OPTIONS.index(e_pricing_d)},
                    "ta": {"time": e_ta_t, "offset": DAY_OPTIONS.index(e_ta_d)},
                    "b1": {"time": e_b1_t, "offset": DAY_OPTIONS.index(e_b1_d)},
                    "b2": {"time": e_b2_t, "offset": DAY_OPTIONS.index(e_b2_d)},
                    "b3": {"time": e_b3_t, "offset": DAY_OPTIONS.index(e_b3_d)}
                })
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

    # 2. ADD CUSTOM TASK (With Category promotion and Day Selection)
    with st.expander("➕ Add Custom Task"):
        with st.form("task_form", clear_on_submit=True):
            n_t_name = st.text_input("Task Name")
            n_t_cat = st.selectbox("Task Category (Promote to Baseline)", CATEGORIES, index=CATEGORIES.index("Custom Task"))
            n_t_hub = st.selectbox("Assigned Hub", HUBS)
            c1, c2 = st.columns(2)
            n_t_start = c1.time_input("Start Time (GMT)", time(18, 30))
            n_t_day = c2.selectbox("Day", DAY_OPTIONS, index=0)
            n_t_dur = st.number_input("Duration (mins)", 5, 1000, 30)
            n_t_staff = st.number_input("Staff Count", 1, 50, 1)
            
            if st.form_submit_button("Save Task"):
                if n_t_name:
                    st.session_state.custom_tasks.append({
                        "name": n_t_name, "cat": n_t_cat, "hub": n_t_hub, 
                        "time": n_t_start, "offset": DAY_OPTIONS.index(n_t_day), 
                        "dur": n_t_dur, "staff": n_t_staff
                    })
                    st.rerun()

    # 3. EDIT CUSTOM TASKS
    if st.session_state.custom_tasks:
        with st.expander("🛠️ Edit Custom Tasks"):
            task_list = [t["name"] for t in st.session_state.custom_tasks]
            edit_task_name = st.selectbox("Select Task", task_list)
            if edit_task_name:
                t_idx = task_list.index(edit_task_name)
                t_data = st.session_state.custom_tasks[t_idx]
                with st.form("edit_task_form"):
                    e_t_name = st.text_input("Task Name", t_data["name"])
                    e_t_cat = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(t_data.get("cat", "Custom Task")))
                    hub_idx = HUBS.index(t_data["hub"]) if t_data["hub"] in HUBS else 0
                    e_t_hub = st.selectbox("Hub", HUBS, index=hub_idx)
                    
                    c1, c2 = st.columns(2)
                    e_t_start = c1.time_input("Start Time", t_data["time"])
                    e_t_day = c2.selectbox("Day", DAY_OPTIONS, index=t_data.get("offset", 0))
                    
                    e_t_dur = st.number_input("Duration (mins)", 1, 1000, int(t_data["dur"]))
                    e_t_staff = st.number_input("Staff", 1, 50, int(t_data["staff"]))
                    
                    colA, colB = st.columns(2)
                    with colA:
                        if st.form_submit_button("Update Task"):
                            st.session_state.custom_tasks[t_idx] = {
                                "name": e_t_name, "cat": e_t_cat, "hub": e_t_hub, 
                                "time": e_t_start, "offset": DAY_OPTIONS.index(e_t_day), 
                                "dur": e_t_dur, "staff": e_t_staff
                            }
                            st.rerun()
                    with colB:
                        if st.form_submit_button("Delete Task"):
                            st.session_state.custom_tasks.pop(t_idx)
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

# DYNAMIC MULTI-DAY CALCULATIONS
broker_dt = datetime.combine(T_DATE + timedelta(days=bt["broker"]["offset"]), bt["broker"]["time"])
ta_dt = datetime.combine(T_DATE + timedelta(days=bt["ta"]["offset"]), bt["ta"]["time"])
pricing_dt = datetime.combine(T_DATE + timedelta(days=bt["pricing"]["offset"]), bt["pricing"]["time"])
batch1_start = datetime.combine(T_DATE + timedelta(days=bt["b1"]["offset"]), bt["b1"]["time"])
batch2_start = datetime.combine(T_DATE + timedelta(days=bt["b2"]["offset"]), bt["b2"]["time"])
batch3_start = datetime.combine(T_DATE + timedelta(days=bt["b3"]["offset"]), bt["b3"]["time"])

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
    c_start = datetime.combine(T_DATE + timedelta(days=ct.get("offset", 0)), ct["time"])
    c_hub_info = hd[c_hub_name]
    c_dur = get_concurrent_duration(ct["dur"], ct["staff"], c_hub_info.overhead_factor)
    c_end = add_mins(c_start, c_dur)
    c_cost = (c_dur / 60) * c_hub_info.hourly_rate * ct["staff"]
    tasks.append(dict(Task=ct["name"], Start=c_start, End=c_end, Hub=c_hub_name, Cat=ct.get("cat", "Custom Task"), Cost_Raw=c_cost, Staff=ct["staff"]))

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
with col2: st.markdown(f'<div class="info-card"><div class="label">Book Published</div><div class="value">{get_day_label(pub_end)} {fmt_gmt(pub_end)}</div></div>', unsafe_allow_html=True)
with col3: 
    buffer = int((NAV_DEADLINE - pub_end).total_seconds() / 60)
    color = "#00d4aa" if buffer >= 0 else "#ff4444"
    st.markdown(f'<div class="info-card"><div class="label">Buffer to SLA</div><div class="value" style="color:{color}">{buffer} mins</div></div>', unsafe_allow_html=True)
with col4: st.markdown(f'<div class="info-card"><div class="label">Total Variable Cost</div><div class="value cost-text">${total_op_cost:,.2f}</div></div>', unsafe_allow_html=True)
with col5: st.markdown(f'<div class="info-card"><div class="label">Total Volume</div><div class="value">{total_funds} Funds</div></div>', unsafe_allow_html=True)
with col6: st.markdown(f'<div class="info-card"><div class="label">Unit Economics</div><div class="value unit-text">${unit_cost_overall:,.2f} / Fund</div></div>', unsafe_allow_html=True)

for w in warnings: st.warning(w)

st.markdown("### 📊 Concurrent Lifecycle Timeline")
# Adjust chart limits dynamically based on latest task
max_end = df_tasks['End'].max() + timedelta(hours=2)
fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
fig.update_yaxes(autorange="reversed")
fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text="VP T 16:00", annotation_position="top left")
fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text="SLA T+1 09:00", annotation_position="top left")
fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30), xaxis=dict(range=[VALUATION_POINT - timedelta(hours=2), max_end]))
st.plotly_chart(fig, use_container_width=True)

with st.expander("📋 Detailed Workload, Capacity & Unit Economics", expanded=True):
    display_df = df_tasks.copy().sort_values(by="Start")
    display_df['Day'] = display_df['Start'].apply(get_day_label)
    display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
    display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
    display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
    display_df['Cost/Fund'] = (display_df['Cost_Raw'] / total_funds).apply(lambda x: f"${x:.2f}" if x > 0 else "-")
    display_df['Total Cost'] = display_df['Cost_Raw'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
    st.dataframe(display_df[['Day', 'Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Total Cost', 'Cost/Fund']], use_container_width=True, hide_index=True)