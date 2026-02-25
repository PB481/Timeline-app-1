# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import io
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

if 'baseline_times' not in st.session_state or type(st.session_state.baseline_times.get("broker")) == time:
    st.session_state.baseline_times = {
        "broker": {"time": time(16, 30), "offset": 0}, "ta": {"time": time(17, 0), "offset": 0}, 
        "pricing": {"time": time(16, 15), "offset": 0}, "b1": {"time": time(18, 0), "offset": 0}, 
        "b2": {"time": time(2, 0), "offset": 1}, "b3": {"time": time(5, 30), "offset": 1}
    }

if 'milestones' not in st.session_state:
    st.session_state.milestones = {
        "investor": {"time": time(12, 0), "offset": 0}, "trade": {"time": time(14, 0), "offset": 0},
        "vp": {"time": time(16, 0), "offset": 0}, "nav": {"time": time(9, 0), "offset": 1}
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
# Sidebar Configuration (Strictly for Scenario Testing)
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Scenario Testing")
    total_funds = st.slider("Total Fund Volume", 1, 1000, 100)
    
    with st.expander("⏱️ Average Time Per Fund"):
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

# ---------------------------------------------------------------------
# Main Application Header & Tabs
# ---------------------------------------------------------------------
st.markdown(f'<div class="main-header"><h1>🏦 Enterprise Capacity & Timelines</h1><p>Modeling {total_funds} funds concurrently.</p></div>', unsafe_allow_html=True)

tab_dash, tab_config = st.tabs(["📊 Capacity Dashboard", "⚙️ Data & Configuration Manager"])

# =====================================================================
# TAB 2: DATA & CONFIGURATION MANAGER (Intuitive UI)
# =====================================================================
with tab_config:
    st.markdown("### 🛠️ System Configuration")
    st.write("Manage your structural data, deadlines, and hubs here. Changes instantly update the main dashboard.")
    
    conf_col1, conf_col2 = st.columns(2)
    
    with conf_col1:
        # MILESTONES
        st.subheader("🚩 Key Deadlines & Milestones")
        with st.form("edit_milestones_form"):
            m1, m2 = st.columns(2)
            e_inv_t = m1.time_input("Investor Cutoff", st.session_state.milestones["investor"]["time"])
            e_inv_d = m2.selectbox("Inv. Day", DAY_OPTIONS, index=st.session_state.milestones["investor"]["offset"])
            
            m3, m4 = st.columns(2)
            e_trd_t = m3.time_input("Trade Cutoff", st.session_state.milestones["trade"]["time"])
            e_trd_d = m4.selectbox("Trade Day", DAY_OPTIONS, index=st.session_state.milestones["trade"]["offset"])
            
            m5, m6 = st.columns(2)
            e_vp_t = m5.time_input("Valuation Point (VP)", st.session_state.milestones["vp"]["time"])
            e_vp_d = m6.selectbox("VP Day", DAY_OPTIONS, index=st.session_state.milestones["vp"]["offset"])
            
            m7, m8 = st.columns(2)
            e_nav_t = m7.time_input("NAV Delivery SLA", st.session_state.milestones["nav"]["time"])
            e_nav_d = m8.selectbox("SLA Day", DAY_OPTIONS, index=st.session_state.milestones["nav"]["offset"])
            
            if st.form_submit_button("💾 Save Deadlines"):
                st.session_state.milestones.update({
                    "investor": {"time": e_inv_t, "offset": DAY_OPTIONS.index(e_inv_d)},
                    "trade": {"time": e_trd_t, "offset": DAY_OPTIONS.index(e_trd_d)},
                    "vp": {"time": e_vp_t, "offset": DAY_OPTIONS.index(e_vp_d)},
                    "nav": {"time": e_nav_t, "offset": DAY_OPTIONS.index(e_nav_d)}
                })
                st.success("Deadlines Updated!")
                st.rerun()

        # BASELINE TIMINGS
        st.subheader("⏱️ Baseline Files & Batches")
        with st.form("edit_timings_form"):
            t1, t2, t3, t4 = st.columns(4)
            e_broker_t = t1.time_input("Broker Files", st.session_state.baseline_times["broker"]["time"])
            e_broker_d = t2.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["broker"]["offset"], key="tb1")
            e_pricing_t = t3.time_input("Pricing", st.session_state.baseline_times["pricing"]["time"])
            e_pricing_d = t4.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["pricing"]["offset"], key="tp1")
            
            t5, t6, t7, t8 = st.columns(4)
            e_ta_t = t5.time_input("TA Files", st.session_state.baseline_times["ta"]["time"])
            e_ta_d = t6.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["ta"]["offset"], key="tta1")
            e_b1_t = t7.time_input("Batch 1", st.session_state.baseline_times["b1"]["time"])
            e_b1_d = t8.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b1"]["offset"], key="tb11")
            
            t9, t10, t11, t12 = st.columns(4)
            e_b2_t = t9.time_input("Batch 2", st.session_state.baseline_times["b2"]["time"])
            e_b2_d = t10.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b2"]["offset"], key="tb22")
            e_b3_t = t11.time_input("Batch 3", st.session_state.baseline_times["b3"]["time"])
            e_b3_d = t12.selectbox("Day", DAY_OPTIONS, index=st.session_state.baseline_times["b3"]["offset"], key="tb33")
            
            if st.form_submit_button("💾 Save Background Timings"):
                st.session_state.baseline_times.update({
                    "broker": {"time": e_broker_t, "offset": DAY_OPTIONS.index(e_broker_d)},
                    "pricing": {"time": e_pricing_t, "offset": DAY_OPTIONS.index(e_pricing_d)},
                    "ta": {"time": e_ta_t, "offset": DAY_OPTIONS.index(e_ta_d)},
                    "b1": {"time": e_b1_t, "offset": DAY_OPTIONS.index(e_b1_d)},
                    "b2": {"time": e_b2_t, "offset": DAY_OPTIONS.index(e_b2_d)},
                    "b3": {"time": e_b3_t, "offset": DAY_OPTIONS.index(e_b3_d)}
                })
                st.success("Timings Updated!")
                st.rerun()

    with conf_col2:
        # EXCEL IMPORT/EXPORT
        st.subheader("📁 Bulk Task Import (CSV/Excel)")
        
        # 1. Generate Template
        template_df = pd.DataFrame({
            "Task_Name": ["Client Reporting", "Price Overrides"],
            "Category": ["Publication", "Valuation"],
            "Hub": [HUBS[0], HUBS[0]],
            "Start_Time": ["18:30", "17:15"],
            "Day_Offset": [1, 0], 
            "Duration_Mins": [45, 20],
            "Staff_Count": [2, 1]
        })
        csv_template = template_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(label="⬇️ Download Data Template", data=csv_template, file_name="task_template.csv", mime="text/csv", help="Download a formatted CSV template to build your custom tasks in Excel.")
        
        # 2. Upload Data
        uploaded_file = st.file_uploader("Upload Populated Template (.csv)", type=["csv"])
        if uploaded_file is not None:
            try:
                imported_df = pd.read_csv(uploaded_file)
                # Parse and inject
                for index, row in imported_df.iterrows():
                    hub_val = row["Hub"] if row["Hub"] in HUBS else HUBS[0]
                    cat_val = row["Category"] if row["Category"] in CATEGORIES else "Custom Task"
                    time_val = datetime.strptime(row["Start_Time"], "%H:%M").time()
                    st.session_state.custom_tasks.append({
                        "name": str(row["Task_Name"]), "cat": cat_val, "hub": hub_val,
                        "time": time_val, "offset": int(row["Day_Offset"]),
                        "dur": int(row["Duration_Mins"]), "staff": int(row["Staff_Count"])
                    })
                st.success(f"✅ Successfully imported {len(imported_df)} tasks!")
                # Button to force refresh to clear the uploader memory state
                if st.button("Refresh Timeline"): st.rerun()
            except Exception as e:
                st.error(f"Error parsing file. Please ensure it matches the template format. Details: {e}")

        # HUBS MANAGEMENT
        st.subheader("🏢 Hub Management")
        with st.expander("➕ Add / Edit Hubs", expanded=False):
            with st.form("hub_add_form", clear_on_submit=True):
                h1, h2 = st.columns(2)
                n_h_name = h1.text_input("Full Name (e.g. APAC - SG)")
                n_h_rate = h2.number_input("Hourly Rate ($)", 10.0, 300.0, 45.0)
                h3, h4 = st.columns(2)
                n_h_short = h3.text_input("Short Code", max_chars=4)
                n_h_offset = h4.number_input("GMT Offset (Hours)", -12.0, 14.0, 8.0)
                if st.form_submit_button("Save New Hub"):
                    if n_h_name and n_h_short:
                        st.session_state.hub_dict[n_h_name] = HubInfo(n_h_short, f"GMT{n_h_offset:+g}", n_h_offset, "Custom", n_h_rate, 0.02)
                        st.rerun()
            st.write("---")
            edit_hub_key = st.selectbox("Select Hub to Delete", HUBS)
            if st.button("🗑️ Delete Selected Hub"):
                if len(st.session_state.hub_dict) > 1:
                    del st.session_state.hub_dict[edit_hub_key]
                    st.rerun()
                else: st.error("Cannot delete the last hub.")

        if st.button("🚨 Factory Reset All Data", type="primary"):
            st.session_state.clear()
            st.rerun()

# =====================================================================
# TAB 1: CAPACITY DASHBOARD (Engine & Visuals)
# =====================================================================
with tab_dash:
    tasks = []
    warnings = []
    bn = st.session_state.baseline_names
    hd = st.session_state.hub_dict
    bt = st.session_state.baseline_times
    ms = st.session_state.milestones

    # DYNAMIC MILESTONES
    INVESTOR_CUTOFF = datetime.combine(T_DATE + timedelta(days=ms["investor"]["offset"]), ms["investor"]["time"])
    TRADE_CUTOFF = datetime.combine(T_DATE + timedelta(days=ms["trade"]["offset"]), ms["trade"]["time"])
    VALUATION_POINT = datetime.combine(T_DATE + timedelta(days=ms["vp"]["offset"]), ms["vp"]["time"])
    NAV_DEADLINE = datetime.combine(T_DATE + timedelta(days=ms["nav"]["offset"]), ms["nav"]["time"])

    broker_dt = datetime.combine(T_DATE + timedelta(days=bt["broker"]["offset"]), bt["broker"]["time"])
    ta_dt = datetime.combine(T_DATE + timedelta(days=bt["ta"]["offset"]), bt["ta"]["time"])
    pricing_dt = datetime.combine(T_DATE + timedelta(days=bt["pricing"]["offset"]), bt["pricing"]["time"])
    batch1_start = datetime.combine(T_DATE + timedelta(days=bt["b1"]["offset"]), bt["b1"]["time"])
    batch2_start = datetime.combine(T_DATE + timedelta(days=bt["b2"]["offset"]), bt["b2"]["time"])
    batch3_start = datetime.combine(T_DATE + timedelta(days=bt["b3"]["offset"]), bt["b3"]["time"])

    # Ensure batch sequences mathematically follow
    if batch2_start < batch1_start: batch2_start += timedelta(days=1)
    if batch3_start < batch2_start: batch3_start += timedelta(days=1)

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

    # Custom Tasks Injection (From Memory or Excel Upload)
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

    # --- TOP METRICS ---
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
    with col5: st.markdown(f'<div class="info-card"><div class="label">Total Managed Staff</div><div class="value">{int(total_headcount)} FTEs</div></div>', unsafe_allow_html=True)
    with col6: st.markdown(f'<div class="info-card"><div class="label">Unit Economics</div><div class="value unit-text">${unit_cost_overall:,.2f} / Fund</div></div>', unsafe_allow_html=True)

    for w in warnings: st.warning(w)

    # --- GANTT CHART ---
    min_start = min(df_tasks['Start'].min(), INVESTOR_CUTOFF) - timedelta(hours=1)
    max_end = max(df_tasks['End'].max(), NAV_DEADLINE) + timedelta(hours=2)

    fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
    fig.update_yaxes(autorange="reversed")

    fig.add_vline(x=INVESTOR_CUTOFF.timestamp() * 1000, line_dash="dot", line_color="#3b82f6", annotation_text=f"Investor {get_day_label(INVESTOR_CUTOFF)} {fmt_gmt(INVESTOR_CUTOFF)}", annotation_position="bottom right")
    fig.add_vline(x=TRADE_CUTOFF.timestamp() * 1000, line_dash="dot", line_color="#a855f7", annotation_text=f"Trade {get_day_label(TRADE_CUTOFF)} {fmt_gmt(TRADE_CUTOFF)}", annotation_position="bottom right")
    fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text=f"VP {get_day_label(VALUATION_POINT)} {fmt_gmt(VALUATION_POINT)}", annotation_position="top left")
    fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text=f"SLA {get_day_label(NAV_DEADLINE)} {fmt_gmt(NAV_DEADLINE)}", annotation_position="top left")

    fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30), xaxis=dict(range=[min_start, max_end]))
    st.plotly_chart(fig, use_container_width=True)

    # --- TABLE ---
    with st.expander("📋 Detailed Workload & Unit Economics", expanded=True):
        display_df = df_tasks.copy().sort_values(by="Start")
        display_df['Day'] = display_df['Start'].apply(get_day_label)
        display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
        display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
        display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
        display_df['Cost/Fund'] = (display_df['Cost_Raw'] / total_funds).apply(lambda x: f"${x:.2f}" if x > 0 else "-")
        display_df['Total Cost'] = display_df['Cost_Raw'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
        st.dataframe(display_df[['Day', 'Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Total Cost', 'Cost/Fund']], use_container_width=True, hide_index=True)