# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import io
from html import escape as html_escape
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
if 'use_baseline' not in st.session_state: st.session_state.use_baseline = True

# NEW BASELINE TASKS
if 'baseline_names' not in st.session_state:
    st.session_state.baseline_names = {
        "t_trade_files": "Trade Files",
        "t_pricing": "Pricing",
        "t_corp": "Corp Actions",
        "t_income": "Income",
        "t_deriv": "Derivatives",
        "t_cash": "Cash Flow",
        "t_recon": "Reconciliation",
        "t_nav": "NAV Review & Publication",
        "t_reporting": "Reporting",
        "t_settlement": "Settlement"
    }

if 'baseline_times' not in st.session_state or "trade_files" not in st.session_state.baseline_times:
    st.session_state.baseline_times = {
        "trade_files": {"time": time(16, 30), "offset": 0},
        "pricing": {"time": time(16, 15), "offset": 0},
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
    "Data Ingestion": "#3b82f6", "Processing": "#f59e0b", "Reconciliation": "#06b6d4",
    "Review & Pub": "#10b981", "Post-NAV": "#8b5cf6", "Custom Task": "#eab308"
}
CATEGORIES = list(CATEGORY_COLORS.keys())

def get_t_date() -> date:
    return date.today()

T_DATE = get_t_date()
DAY_OPTIONS = ["T", "T+1", "T+2", "T+3", "T+4", "T+5"]

def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=round(mins))
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
    st.markdown("## ⚙️ Scenario Engine")
    
    st.session_state.use_baseline = st.toggle("Show Baseline Tasks", value=st.session_state.use_baseline, help="Turn this off to completely hide the standard workflow and only show your custom uploaded tasks.")
    
    total_funds = st.slider("Total Fund Volume", 1, 1000, 100)
    
    with st.expander("⏱️ Average Time Per Fund (Mins)"):
        avg_corp = st.number_input("Corp Actions", 1.0, 60.0, 3.0)
        avg_inc = st.number_input("Income", 1.0, 60.0, 2.0)
        avg_deriv = st.number_input("Derivatives", 1.0, 60.0, 8.0)
        avg_cash = st.number_input("Cash Flow", 1.0, 60.0, 4.0)
        avg_recon = st.number_input("Reconciliation", 1.0, 60.0, 15.0)
        avg_nav = st.number_input("NAV Review", 1.0, 60.0, 10.0)
        avg_reporting = st.number_input("Reporting", 1.0, 60.0, 3.0)
        avg_settlement = st.number_input("Settlement", 1.0, 60.0, 4.0)

    st.divider()
    st.markdown("## 👥 Hub Assignment")
    hub_proc = st.selectbox("Data Processing Hub", HUBS, index=get_hub_idx("India"))
    staff_proc = st.slider("Processing Staff", 1, 50, 15, key="s_pr")
    
    hub_recon = st.selectbox("Reconciliation Hub", HUBS, index=get_hub_idx("Dublin"))
    staff_recon = st.slider("Recon Staff", 1, 50, 20, key="s_rc")
    
    hub_nav = st.selectbox("Review & Pub Hub", HUBS, index=get_hub_idx("Dublin"))
    staff_nav = st.slider("Review Staff", 1, 50, 10, key="s_nv")
    
    latency_gap = st.slider("Inter-Hub Hand-off (mins)", 0, 60, 15)

# ---------------------------------------------------------------------
# Main Application Header & Tabs
# ---------------------------------------------------------------------
st.markdown(f'<div class="main-header"><h1>Enterprise Capacity &amp; Timelines</h1><p>Modeling {int(total_funds)} funds concurrently.</p></div>', unsafe_allow_html=True)

tab_dash, tab_config = st.tabs(["📊 Capacity Dashboard", "⚙️ Data & Configuration Manager"])

# =====================================================================
# TAB 2: DATA & CONFIGURATION MANAGER
# =====================================================================
with tab_config:
    st.markdown("### 🛠️ System Configuration")
    
    conf_col1, conf_col2 = st.columns(2)
    
    with conf_col1:
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
                st.rerun()

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

    with conf_col2:
        st.subheader("📁 Bulk Task Import (CSV)")
        
        # 1. Generate Template
        template_df = pd.DataFrame({
            "Task_Name": ["Bespoke Client Reporting", "Audit Extract"],
            "Category": ["Post-NAV", "Custom Task"],
            "Hub": [HUBS[0], HUBS[0]],
            "Start_Time": ["10:30", "11:00"],
            "Day_Offset": [1, 1], 
            "Duration_Mins": [45, 20],
            "Staff_Count": [2, 1]
        })
        csv_template = template_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(label="⬇️ Download Data Template", data=csv_template, file_name="task_template.csv", mime="text/csv", help="Download a CSV template to build custom workflows.")
        
        # 2. Upload Data (Trigger Baseline Override)
        uploaded_file = st.file_uploader("Upload Populated Template (.csv)", type=["csv"])
        if uploaded_file is not None:
            try:
                imported_df = pd.read_csv(uploaded_file)
                required_cols = {"Task_Name", "Category", "Hub", "Start_Time", "Day_Offset", "Duration_Mins", "Staff_Count"}
                missing_cols = required_cols - set(imported_df.columns)
                if missing_cols:
                    st.error(f"Missing required columns: {', '.join(sorted(missing_cols))}")
                else:
                    errors = []
                    st.session_state.custom_tasks = []

                    for index, row in imported_df.iterrows():
                        row_num = index + 2  # 1-indexed + header
                        dur_val = int(row["Duration_Mins"])
                        staff_val = int(row["Staff_Count"])
                        offset_val = int(row["Day_Offset"])
                        if dur_val <= 0:
                            errors.append(f"Row {row_num}: Duration_Mins must be > 0 (got {dur_val})")
                            continue
                        if staff_val <= 0:
                            errors.append(f"Row {row_num}: Staff_Count must be > 0 (got {staff_val})")
                            continue
                        if offset_val < 0:
                            errors.append(f"Row {row_num}: Day_Offset must be >= 0 (got {offset_val})")
                            continue

                        hub_val = row["Hub"] if row["Hub"] in HUBS else HUBS[0]
                        cat_val = row["Category"] if row["Category"] in CATEGORIES else "Custom Task"
                        time_val = datetime.strptime(str(row["Start_Time"]).strip(), "%H:%M").time()
                        st.session_state.custom_tasks.append({
                            "name": str(row["Task_Name"]), "cat": cat_val, "hub": hub_val,
                            "time": time_val, "offset": offset_val,
                            "dur": dur_val, "staff": staff_val
                        })

                    if errors:
                        for e in errors:
                            st.warning(e)

                    st.session_state.use_baseline = False
                    st.success(f"Imported {len(st.session_state.custom_tasks)} tasks! Baseline tasks have been hidden.")
                    if st.button("Render Timeline"): st.rerun()
            except Exception as e:
                st.error(f"Error parsing file. Details: {e}")

        if st.button("🚨 Factory Reset All Data", type="primary"):
            st.session_state.clear()
            st.rerun()

# =====================================================================
# TAB 1: CAPACITY DASHBOARD (Engine & Visuals)
# =====================================================================
with tab_dash:
    tasks = []
    bn = st.session_state.baseline_names
    hd = st.session_state.hub_dict
    bt = st.session_state.baseline_times
    ms = st.session_state.milestones

    INVESTOR_CUTOFF = datetime.combine(T_DATE + timedelta(days=ms["investor"]["offset"]), ms["investor"]["time"])
    TRADE_CUTOFF = datetime.combine(T_DATE + timedelta(days=ms["trade"]["offset"]), ms["trade"]["time"])
    VALUATION_POINT = datetime.combine(T_DATE + timedelta(days=ms["vp"]["offset"]), ms["vp"]["time"])
    NAV_DEADLINE = datetime.combine(T_DATE + timedelta(days=ms["nav"]["offset"]), ms["nav"]["time"])

    def append_waterfall_task(task_name, start_dt, avg_per_fund, hub_name, staff, cat, prev_hub=None):
        """Build a waterfall task, applying inter-hub latency when the hub changes."""
        hub_info = hd[hub_name]
        wait = latency_gap if (prev_hub is not None and prev_hub != hub_name) else 0
        actual_start = add_mins(start_dt, wait)
        dur = get_concurrent_duration(total_funds * avg_per_fund, staff, hub_info.overhead_factor)
        end = add_mins(actual_start, dur)
        cost = (dur / 60) * hub_info.hourly_rate * staff
        tasks.append(dict(Task=task_name, Start=actual_start, End=end, Hub=hub_name, Cat=cat, Cost_Raw=cost, Staff=staff))
        return end, hub_name

    # Baseline Waterfall
    if st.session_state.use_baseline:
        # 1. Ingestion (fixed-duration data feeds)
        trade_dt = datetime.combine(T_DATE + timedelta(days=bt["trade_files"]["offset"]), bt["trade_files"]["time"])
        pricing_dt = datetime.combine(T_DATE + timedelta(days=bt["pricing"]["offset"]), bt["pricing"]["time"])

        tasks.append(dict(Task=bn["t_trade_files"], Start=trade_dt, End=add_mins(trade_dt, 5), Hub="Custody", Cat="Data Ingestion", Cost_Raw=0, Staff=0))
        tasks.append(dict(Task=bn["t_pricing"], Start=pricing_dt, End=add_mins(pricing_dt, 5), Hub="Market Data", Cat="Data Ingestion", Cost_Raw=0, Staff=0))

        # Core waterfall starts at max of data arrival or Valuation Point
        cursor = max(trade_dt, pricing_dt, VALUATION_POINT)
        prev_hub = None

        # 2-5. Processing chain (all same hub, so no inter-hub latency)
        cursor, prev_hub = append_waterfall_task(bn["t_corp"],   cursor, avg_corp,  hub_proc, staff_proc, "Processing", prev_hub)
        cursor, prev_hub = append_waterfall_task(bn["t_income"], cursor, avg_inc,   hub_proc, staff_proc, "Processing", prev_hub)
        cursor, prev_hub = append_waterfall_task(bn["t_deriv"],  cursor, avg_deriv, hub_proc, staff_proc, "Processing", prev_hub)
        cursor, prev_hub = append_waterfall_task(bn["t_cash"],   cursor, avg_cash,  hub_proc, staff_proc, "Processing", prev_hub)

        # 6. Reconciliation (possible hub handoff from processing)
        cursor, prev_hub = append_waterfall_task(bn["t_recon"], cursor, avg_recon, hub_recon, staff_recon, "Reconciliation", prev_hub)

        # 7. NAV Review & Publication (possible hub handoff from recon)
        cursor, prev_hub = append_waterfall_task(bn["t_nav"], cursor, avg_nav, hub_nav, staff_nav, "Review & Pub", prev_hub)

        # 8-9. Post-NAV (same hub as review)
        cursor, prev_hub = append_waterfall_task(bn["t_reporting"],  cursor, avg_reporting,  hub_nav, staff_nav, "Post-NAV", prev_hub)
        cursor, prev_hub = append_waterfall_task(bn["t_settlement"], cursor, avg_settlement, hub_nav, staff_nav, "Post-NAV", prev_hub)

    # Custom Tasks (always runs)
    for ct in st.session_state.custom_tasks:
        c_hub_name = ct["hub"] if ct["hub"] in hd else list(hd.keys())[0]
        c_start = datetime.combine(T_DATE + timedelta(days=ct.get("offset", 0)), ct["time"])
        c_hub_info = hd[c_hub_name]
        c_dur = float(ct["dur"])
        c_end = add_mins(c_start, c_dur)
        c_cost = (c_dur / 60) * c_hub_info.hourly_rate * ct["staff"]
        tasks.append(dict(
            Task=ct["name"], Start=c_start, End=c_end,
            Hub=c_hub_name, Cat=ct.get("cat", "Custom Task"),
            Cost_Raw=c_cost, Staff=ct["staff"]
        ))

    if not tasks:
        st.error("No tasks to display! Please upload a file or turn Baseline Tasks back on.")
        st.stop()

    df_tasks = pd.DataFrame(tasks)
    final_end_time = df_tasks['End'].max()
    sla_met = final_end_time <= NAV_DEADLINE

    total_op_cost = df_tasks['Cost_Raw'].sum()
    total_headcount = df_tasks['Staff'].sum()
    unit_cost_overall = total_op_cost / max(total_funds, 1)
    df_tasks['Cost'] = df_tasks['Cost_Raw'].apply(lambda x: f"${x:,.2f}")

    # --- TOP METRICS ---
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        sla_class = "sla-met" if sla_met else "sla-breach"
        sla_label = "MET" if sla_met else "BREACH"
        st.markdown(f'<div class="sla-card {sla_class}"><div class="sla-label">SLA Status</div><div class="sla-value">{html_escape(sla_label)}</div></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="info-card"><div class="label">Book Completed</div><div class="value">{html_escape(get_day_label(final_end_time))} {html_escape(fmt_gmt(final_end_time))}</div></div>', unsafe_allow_html=True)
    with col3:
        buffer = int((NAV_DEADLINE - final_end_time).total_seconds() / 60)
        color = "#00d4aa" if buffer >= 0 else "#ff4444"
        st.markdown(f'<div class="info-card"><div class="label">Buffer to SLA</div><div class="value" style="color:{color}">{buffer} mins</div></div>', unsafe_allow_html=True)
    with col4: st.markdown(f'<div class="info-card"><div class="label">Total Variable Cost</div><div class="value cost-text">${total_op_cost:,.2f}</div></div>', unsafe_allow_html=True)
    with col5: st.markdown(f'<div class="info-card"><div class="label">Total Managed Staff</div><div class="value">{int(total_headcount)} FTEs</div></div>', unsafe_allow_html=True)
    with col6: st.markdown(f'<div class="info-card"><div class="label">Unit Economics</div><div class="value unit-text">${unit_cost_overall:,.2f} / Fund</div></div>', unsafe_allow_html=True)

    # --- GANTT CHART ---
    min_start = min(df_tasks['Start'].min(), INVESTOR_CUTOFF) - timedelta(hours=1)
    max_end_chart = max(df_tasks['End'].max(), NAV_DEADLINE) + timedelta(hours=2)

    fig = px.timeline(df_tasks, x_start="Start", x_end="End", y="Task", color="Cat", color_discrete_map=CATEGORY_COLORS, hover_data=["Hub", "Cost"])
    fig.update_yaxes(autorange="reversed")

    fig.add_vline(x=INVESTOR_CUTOFF.timestamp() * 1000, line_dash="dot", line_color="#3b82f6", annotation_text=f"Investor {get_day_label(INVESTOR_CUTOFF)} {fmt_gmt(INVESTOR_CUTOFF)}", annotation_position="bottom right")
    fig.add_vline(x=TRADE_CUTOFF.timestamp() * 1000, line_dash="dot", line_color="#a855f7", annotation_text=f"Trade {get_day_label(TRADE_CUTOFF)} {fmt_gmt(TRADE_CUTOFF)}", annotation_position="bottom right")
    fig.add_vline(x=VALUATION_POINT.timestamp() * 1000, line_dash="dash", line_color="#ff9933", annotation_text=f"VP {get_day_label(VALUATION_POINT)} {fmt_gmt(VALUATION_POINT)}", annotation_position="top left")
    fig.add_vline(x=NAV_DEADLINE.timestamp() * 1000, line_dash="dash", line_color="#ff4444", annotation_text=f"SLA {get_day_label(NAV_DEADLINE)} {fmt_gmt(NAV_DEADLINE)}", annotation_position="top left")

    fig.update_layout(plot_bgcolor="#0a1628", paper_bgcolor="#0a1628", font=dict(color="#c8d8e8"), height=500, margin=dict(l=10, r=30, t=30, b=30), xaxis=dict(range=[min_start, max_end_chart]))
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
