# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import re
from html import escape as html_escape
from datetime import datetime, timedelta, time, date
from difflib import SequenceMatcher

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
# Constants
# ---------------------------------------------------------------------
CATEGORY_COLORS = {
    "Data Ingestion": "#3b82f6", "Processing": "#f59e0b", "Reconciliation": "#06b6d4",
    "Review & Pub": "#10b981", "Post-NAV": "#8b5cf6", "Custom Task": "#eab308"
}
CATEGORIES = list(CATEGORY_COLORS.keys())
DAY_OPTIONS = ["T", "T+1", "T+2", "T+3", "T+4", "T+5"]
T_DATE = date.today()

def fmt_gmt(dt: datetime) -> str: return dt.strftime("%H:%M")
def add_mins(dt: datetime, mins: float) -> datetime: return dt + timedelta(minutes=round(mins))
def get_concurrent_duration(total_workload_mins: float, n_staff: int, overhead: float) -> float:
    if n_staff <= 1: return float(total_workload_mins)
    return (total_workload_mins / n_staff) * (1 + (overhead * (n_staff - 1)))
def get_day_label(dt_start: datetime) -> str:
    days_diff = (dt_start.date() - T_DATE).days
    return "T" if days_diff <= 0 else f"T+{days_diff}"

# ---------------------------------------------------------------------
# Smart Import: Field Aliases & Cleaning Functions
# ---------------------------------------------------------------------
FIELD_ALIASES = {
    "Task": ["task", "task_name", "taskname", "name", "activity",
             "process", "step", "description", "task name", "task description",
             "workflow", "action", "item"],
    "Category": ["category", "cat", "type", "group", "phase",
                 "stage", "classification", "task type", "task category"],
    "Hub": ["hub", "location", "centre", "center", "office",
            "site", "region", "hub name", "processing center", "team"],
    "Staff": ["staff", "staff_count", "staffcount", "headcount",
              "head_count", "fte", "ftes", "people", "resources",
              "team_size", "team size", "staff count", "number of staff"],
    "Start Time": ["start_time", "starttime", "start", "time",
                   "begin", "start time", "begin time", "scheduled time",
                   "start_hour", "kick off", "kickoff"],
    "Day": ["day", "day_offset", "dayoffset", "offset", "t_day",
            "day offset", "schedule day", "trading day"],
    "Duration Mins": ["duration_mins", "durationmins", "duration",
                      "mins", "minutes", "time_mins", "duration mins",
                      "est duration", "estimated duration", "duration minutes",
                      "processing time", "elapsed", "duration_minutes"],
}

def read_uploaded_file(uploaded_file):
    """Read CSV or Excel file into a DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    elif name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        return pd.read_excel(uploaded_file, engine="xlrd")
    raise ValueError(f"Unsupported file type: {uploaded_file.name}")

def auto_map_columns(source_columns, field_aliases=FIELD_ALIASES):
    """For each target field, find the best matching source column using fuzzy matching."""
    mapping = {}
    used = set()
    for target, aliases in field_aliases.items():
        best_score, best_col = 0.0, None
        aliases_lower = [a.lower() for a in aliases]
        for src in source_columns:
            if src in used:
                continue
            src_lower = src.strip().lower()
            # Exact alias match
            if src_lower in aliases_lower:
                best_score, best_col = 1.0, src
                break
            # Substring match
            for alias in aliases_lower:
                if alias in src_lower or src_lower in alias:
                    if 0.85 > best_score:
                        best_score, best_col = 0.85, src
            # Fuzzy match
            for alias in aliases_lower:
                score = SequenceMatcher(None, src_lower, alias).ratio()
                if score > best_score:
                    best_score, best_col = score, src
        if best_score >= 0.55 and best_col:
            mapping[target] = best_col
            used.add(best_col)
        else:
            mapping[target] = None
    return mapping

def clean_category(val):
    if pd.isna(val): return "Custom Task"
    v = str(val).strip()
    if v in CATEGORIES: return v
    cat_lower = {c.lower(): c for c in CATEGORIES}
    if v.lower() in cat_lower: return cat_lower[v.lower()]
    best_score, best = 0, "Custom Task"
    for c in CATEGORIES:
        s = SequenceMatcher(None, v.lower(), c.lower()).ratio()
        if s > best_score: best_score, best = s, c
    return best if best_score >= 0.6 else "Custom Task"

def clean_hub(val, hub_names):
    if pd.isna(val) or not hub_names:
        return hub_names[0] if hub_names else "EMEA - Dublin"
    v = str(val).strip()
    if v in hub_names: return v
    hub_lower = {h.lower(): h for h in hub_names}
    if v.lower() in hub_lower: return hub_lower[v.lower()]
    for h in hub_names:
        if v.lower() in h.lower() or h.lower() in v.lower():
            return h
    best_score, best = 0, hub_names[0]
    for h in hub_names:
        s = SequenceMatcher(None, v.lower(), h.lower()).ratio()
        if s > best_score: best_score, best = s, h
    return best if best_score >= 0.5 else hub_names[0]

def clean_staff(val):
    try: return max(int(float(str(val).strip())), 1)
    except (ValueError, TypeError): return 1

def clean_time(val):
    if pd.isna(val): return time(9, 0)
    if isinstance(val, datetime): return val.time()
    if isinstance(val, time): return val
    v = str(val).strip()
    for fmt in ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%H.%M"]:
        try: return datetime.strptime(v, fmt).time()
        except ValueError: continue
    m = re.search(r'(\d{1,2}):(\d{2})', v)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return time(h, mn)
    return time(9, 0)

def clean_day(val):
    if pd.isna(val): return "T"
    v = str(val).strip()
    if v in DAY_OPTIONS: return v
    try:
        offset = int(float(v))
        return f"T+{offset}" if offset > 0 else "T"
    except ValueError: pass
    m = re.search(r'T\+?(\d+)', v, re.IGNORECASE)
    if m:
        offset = int(m.group(1))
        return f"T+{offset}" if offset > 0 else "T"
    return "T"

def clean_duration(val):
    if pd.isna(val): return None
    try:
        v = int(float(str(val).strip()))
        return v if v > 0 else None
    except (ValueError, TypeError): return None

def transform_and_validate(raw_df, col_map, hub_names):
    """Apply column mapping and clean each field. Returns (cleaned_df, warnings_list)."""
    rows = []
    warnings = []
    for idx, raw_row in raw_df.iterrows():
        row_warns = []
        row = {}
        # Task
        if col_map.get("Task"):
            t = str(raw_row[col_map["Task"]]).strip()
            row["Task"] = t if t and t.lower() not in ("nan", "none", "") else f"Unnamed Task {idx+1}"
            if row["Task"].startswith("Unnamed"):
                row_warns.append("Missing task name")
        else:
            row["Task"] = f"Unnamed Task {idx+1}"
            row_warns.append("No task column mapped")
        # Category
        row["Category"] = clean_category(raw_row[col_map["Category"]]) if col_map.get("Category") else "Custom Task"
        # Hub
        row["Hub"] = clean_hub(raw_row[col_map["Hub"]], hub_names) if col_map.get("Hub") else (hub_names[0] if hub_names else "EMEA - Dublin")
        # Staff
        row["Staff"] = clean_staff(raw_row[col_map["Staff"]]) if col_map.get("Staff") else 1
        # Start Time
        row["Start Time"] = clean_time(raw_row[col_map["Start Time"]]) if col_map.get("Start Time") else time(9, 0)
        # Day
        row["Day"] = clean_day(raw_row[col_map["Day"]]) if col_map.get("Day") else "T"
        # Duration
        if col_map.get("Duration Mins"):
            d = clean_duration(raw_row[col_map["Duration Mins"]])
            if d is None:
                row_warns.append(f"Invalid duration: {raw_row[col_map['Duration Mins']]}")
                row["Duration Mins"] = 30  # Fallback
            else:
                row["Duration Mins"] = d
        else:
            row["Duration Mins"] = 30
            row_warns.append("No duration column mapped, defaulting to 30 mins")
        row["Enabled"] = True
        rows.append(row)
        if row_warns:
            warnings.append((idx + 2, row_warns))
    return pd.DataFrame(rows), warnings

# ---------------------------------------------------------------------
# Session State Defaults
# ---------------------------------------------------------------------
DEFAULT_HUBS = pd.DataFrame([
    {"Hub Name": "EMEA - Dublin", "Short": "DUB", "City": "Dublin", "GMT Offset": 0.0, "Hourly Rate ($)": 85.0, "Overhead Factor": 0.01},
    {"Hub Name": "APAC - India",  "Short": "IND", "City": "Mumbai", "GMT Offset": 5.5, "Hourly Rate ($)": 25.0, "Overhead Factor": 0.02},
    {"Hub Name": "NAM - New York","Short": "NYC", "City": "New York","GMT Offset": -5.0,"Hourly Rate ($)": 100.0,"Overhead Factor": 0.015},
])

DEFAULT_MILESTONES = pd.DataFrame([
    {"Milestone": "Investor Cutoff",  "Time": time(12, 0), "Day": "T"},
    {"Milestone": "Trade Cutoff",     "Time": time(14, 0), "Day": "T"},
    {"Milestone": "Valuation Point",  "Time": time(16, 0), "Day": "T"},
    {"Milestone": "NAV Delivery SLA", "Time": time(9, 0),  "Day": "T+1"},
])

DEFAULT_BASELINE = pd.DataFrame([
    {"Task": "Trade Files",            "Category": "Data Ingestion",  "Hub": "Custody",          "Staff": 0,  "Avg Mins/Fund": 0.0, "Fixed Mins": 5,  "Start Time": time(16,30), "Day": "T",  "Enabled": True},
    {"Task": "Pricing",                "Category": "Data Ingestion",  "Hub": "Market Data",      "Staff": 0,  "Avg Mins/Fund": 0.0, "Fixed Mins": 5,  "Start Time": time(16,15), "Day": "T",  "Enabled": True},
    {"Task": "Corp Actions",           "Category": "Processing",      "Hub": "APAC - India",     "Staff": 15, "Avg Mins/Fund": 3.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Income",                 "Category": "Processing",      "Hub": "APAC - India",     "Staff": 15, "Avg Mins/Fund": 2.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Derivatives",            "Category": "Processing",      "Hub": "APAC - India",     "Staff": 15, "Avg Mins/Fund": 8.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Cash Flow",              "Category": "Processing",      "Hub": "APAC - India",     "Staff": 15, "Avg Mins/Fund": 4.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Reconciliation",         "Category": "Reconciliation",  "Hub": "EMEA - Dublin",    "Staff": 20, "Avg Mins/Fund": 15.0,"Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "NAV Review & Publication","Category": "Review & Pub",   "Hub": "EMEA - Dublin",    "Staff": 10, "Avg Mins/Fund": 10.0,"Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Reporting",              "Category": "Post-NAV",        "Hub": "EMEA - Dublin",    "Staff": 10, "Avg Mins/Fund": 3.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
    {"Task": "Settlement",             "Category": "Post-NAV",        "Hub": "EMEA - Dublin",    "Staff": 10, "Avg Mins/Fund": 4.0, "Fixed Mins": 0,  "Start Time": time(0,0),   "Day": "T",  "Enabled": True},
])

if 'hub_df' not in st.session_state:
    st.session_state.hub_df = DEFAULT_HUBS.copy()
if 'milestone_df' not in st.session_state:
    st.session_state.milestone_df = DEFAULT_MILESTONES.copy()
if 'baseline_df' not in st.session_state:
    st.session_state.baseline_df = DEFAULT_BASELINE.copy()
if 'custom_tasks_df' not in st.session_state:
    st.session_state.custom_tasks_df = pd.DataFrame(columns=["Task", "Category", "Hub", "Staff", "Start Time", "Day", "Duration Mins", "Enabled"])
if 'use_baseline' not in st.session_state:
    st.session_state.use_baseline = True

# Import wizard state
if 'import_step' not in st.session_state:
    st.session_state.import_step = 0
if 'import_raw_df' not in st.session_state:
    st.session_state.import_raw_df = None
if 'import_col_map' not in st.session_state:
    st.session_state.import_col_map = {}
if 'import_preview_df' not in st.session_state:
    st.session_state.import_preview_df = None
if 'import_warnings' not in st.session_state:
    st.session_state.import_warnings = []

def reset_import_wizard():
    st.session_state.import_step = 0
    st.session_state.import_raw_df = None
    st.session_state.import_col_map = {}
    st.session_state.import_preview_df = None
    st.session_state.import_warnings = []

# ---------------------------------------------------------------------
# Helper: get hub list from current hub_df
# ---------------------------------------------------------------------
def get_hub_names():
    return st.session_state.hub_df["Hub Name"].tolist()

def get_hub_info(hub_name):
    """Return (hourly_rate, overhead_factor) for a hub name, with fallback."""
    df = st.session_state.hub_df
    match = df[df["Hub Name"] == hub_name]
    if match.empty:
        return 0.0, 0.02
    row = match.iloc[0]
    return float(row["Hourly Rate ($)"]), float(row["Overhead Factor"])

# ---------------------------------------------------------------------
# Sidebar (Slim)
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Scenario Engine")
    st.session_state.use_baseline = st.toggle("Show Baseline Tasks", value=st.session_state.use_baseline, help="Toggle the standard waterfall workflow on/off.")
    total_funds = st.slider("Total Fund Volume", 1, 1000, 100)
    latency_gap = st.slider("Inter-Hub Hand-off (mins)", 0, 60, 15)

    st.divider()
    if st.button("Factory Reset All Data", type="primary"):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------------------
# Main Header & Tabs
# ---------------------------------------------------------------------
st.markdown(f'<div class="main-header"><h1>Enterprise Capacity &amp; Timelines</h1><p>Modeling {int(total_funds)} funds concurrently.</p></div>', unsafe_allow_html=True)

tab_dash, tab_config = st.tabs(["Dashboard", "Configuration"])

# =====================================================================
# TAB: CONFIGURATION
# =====================================================================
with tab_config:

    # --- DEADLINES ---
    st.subheader("Key Deadlines & Milestones")
    st.caption("Edit times and day offsets directly in the table below.")
    edited_milestones = st.data_editor(
        st.session_state.milestone_df,
        column_config={
            "Milestone": st.column_config.TextColumn("Milestone", disabled=True, width="medium"),
            "Time": st.column_config.TimeColumn("Time", format="HH:mm"),
            "Day": st.column_config.SelectboxColumn("Day", options=DAY_OPTIONS, width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key="milestone_editor",
        num_rows="fixed",
    )
    st.session_state.milestone_df = edited_milestones

    st.divider()

    # --- HUBS ---
    st.subheader("Hub Management")
    st.caption("Edit hub details, add new rows, or remove hubs. Changes apply immediately to the dashboard.")
    edited_hubs = st.data_editor(
        st.session_state.hub_df,
        column_config={
            "Hub Name": st.column_config.TextColumn("Hub Name", width="medium"),
            "Short": st.column_config.TextColumn("Short Code", max_chars=4, width="small"),
            "City": st.column_config.TextColumn("City", width="small"),
            "GMT Offset": st.column_config.NumberColumn("GMT Offset", min_value=-12.0, max_value=14.0, step=0.5, format="%.1f"),
            "Hourly Rate ($)": st.column_config.NumberColumn("Rate ($/hr)", min_value=1.0, max_value=500.0, step=1.0, format="$%.0f"),
            "Overhead Factor": st.column_config.NumberColumn("Overhead", min_value=0.0, max_value=1.0, step=0.005, format="%.3f"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="hub_editor",
    )
    st.session_state.hub_df = edited_hubs

    st.divider()

    # --- BASELINE TASKS ---
    st.subheader("Baseline Workflow Tasks")
    st.caption("Configure each task's hub, staffing, and timing. Toggle **Enabled** to include/exclude individual tasks. "
               "**Waterfall tasks** (Avg Mins/Fund > 0) chain sequentially after the Valuation Point. "
               "**Fixed tasks** (Fixed Mins > 0, like data feeds) start at their specified Start Time.")

    all_hub_options = get_hub_names() + ["Custody", "Market Data"]

    edited_baseline = st.data_editor(
        st.session_state.baseline_df,
        column_config={
            "Task": st.column_config.TextColumn("Task Name", width="medium"),
            "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, width="small"),
            "Hub": st.column_config.SelectboxColumn("Hub", options=all_hub_options, width="medium"),
            "Staff": st.column_config.NumberColumn("Staff", min_value=0, max_value=100, step=1),
            "Avg Mins/Fund": st.column_config.NumberColumn("Avg Mins/Fund", min_value=0.0, max_value=120.0, step=0.5, format="%.1f"),
            "Fixed Mins": st.column_config.NumberColumn("Fixed Mins", min_value=0, max_value=480, step=1, help="For fixed-duration tasks (data feeds). Set to 0 for waterfall tasks."),
            "Start Time": st.column_config.TimeColumn("Start Time", format="HH:mm", help="Only used for fixed-duration tasks (data feeds)."),
            "Day": st.column_config.SelectboxColumn("Day", options=DAY_OPTIONS, width="small"),
            "Enabled": st.column_config.CheckboxColumn("On", default=True),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="baseline_editor",
    )
    st.session_state.baseline_df = edited_baseline

    st.divider()

    # =================================================================
    # SMART IMPORT WIZARD
    # =================================================================
    st.subheader("Task Import")

    step = st.session_state.import_step

    # ---- STEP 0: Upload ----
    if step == 0:
        st.caption("Upload a CSV or Excel file with task data. Column names don't need to match exactly — the wizard will help you map them.")

        # Template download
        hub_names = get_hub_names()
        default_hub = hub_names[0] if hub_names else "EMEA - Dublin"
        template_df = pd.DataFrame({
            "Task_Name": ["Bespoke Client Reporting", "Audit Extract"],
            "Category": ["Post-NAV", "Custom Task"],
            "Hub": [default_hub, default_hub],
            "Start_Time": ["10:30", "11:00"],
            "Day_Offset": [1, 1],
            "Duration_Mins": [45, 20],
            "Staff_Count": [2, 1]
        })
        csv_template = template_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="Download CSV Template", data=csv_template, file_name="task_template.csv", mime="text/csv")

        uploaded_file = st.file_uploader("Upload task file (.csv, .xlsx, .xls)", type=["csv", "xlsx", "xls"], key="file_uploader")
        if uploaded_file is not None:
            try:
                raw_df = read_uploaded_file(uploaded_file)
                raw_df.columns = raw_df.columns.str.strip()
                st.session_state.import_raw_df = raw_df
                st.session_state.import_col_map = auto_map_columns(list(raw_df.columns))
                st.session_state.import_step = 1
                st.rerun()
            except Exception as e:
                st.error(f"Could not read file: {e}")

    # ---- STEP 1: Raw Preview ----
    elif step == 1:
        raw_df = st.session_state.import_raw_df
        if raw_df is None:
            reset_import_wizard()
            st.rerun()

        st.caption("**Step 1 of 3** — Preview your uploaded data.")
        st.info(f"{len(raw_df)} rows, {len(raw_df.columns)} columns detected: {', '.join(raw_df.columns.tolist())}")
        st.dataframe(raw_df.head(10), use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        if col_a.button("Proceed to Column Mapping", type="primary"):
            st.session_state.import_step = 2
            st.rerun()
        if col_b.button("Cancel", key="cancel_step1"):
            reset_import_wizard()
            st.rerun()

    # ---- STEP 2: Column Mapping ----
    elif step == 2:
        raw_df = st.session_state.import_raw_df
        if raw_df is None:
            reset_import_wizard()
            st.rerun()

        st.caption("**Step 2 of 3** — Map your file's columns to the required fields. Auto-detected mappings are pre-selected.")

        source_cols = ["-- Skip --"] + list(raw_df.columns)
        auto_map = st.session_state.import_col_map
        mapped_count = sum(1 for v in auto_map.values() if v is not None)
        st.info(f"{mapped_count} of {len(FIELD_ALIASES)} fields auto-detected.")

        new_map = {}
        for target in FIELD_ALIASES.keys():
            auto_val = auto_map.get(target)
            default_idx = source_cols.index(auto_val) if auto_val in source_cols else 0
            required = " *" if target in ("Task", "Duration Mins") else ""
            chosen = st.selectbox(
                f"{target}{required}",
                source_cols,
                index=default_idx,
                key=f"map_{target}"
            )
            new_map[target] = None if chosen == "-- Skip --" else chosen

        # Validation: Task and Duration are required
        can_proceed = True
        if not new_map.get("Task"):
            st.warning("**Task** column is required. Please map it to proceed.")
            can_proceed = False
        if not new_map.get("Duration Mins"):
            st.warning("**Duration Mins** column is required. Please map it to proceed.")
            can_proceed = False

        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Apply Mapping & Preview", type="primary", disabled=not can_proceed):
            st.session_state.import_col_map = new_map
            hub_names = get_hub_names()
            preview_df, warns = transform_and_validate(raw_df, new_map, hub_names)
            st.session_state.import_preview_df = preview_df
            st.session_state.import_warnings = warns
            st.session_state.import_step = 3
            st.rerun()
        if col_b.button("Back", key="back_step2"):
            st.session_state.import_step = 1
            st.rerun()
        if col_c.button("Cancel", key="cancel_step2"):
            reset_import_wizard()
            st.rerun()

    # ---- STEP 3: Review & Import ----
    elif step == 3:
        preview_df = st.session_state.import_preview_df
        warns = st.session_state.import_warnings
        if preview_df is None:
            reset_import_wizard()
            st.rerun()

        st.caption("**Step 3 of 3** — Review the cleaned data. Fix any issues in the table below, then import.")

        # Show warnings
        if warns:
            with st.expander(f"{len(warns)} row(s) have warnings", expanded=False):
                for row_num, row_warns in warns:
                    for w in row_warns:
                        st.warning(f"Row {row_num}: {w}")
        else:
            st.success("All rows cleaned successfully.")

        # Editable preview
        hub_names = get_hub_names()
        edited_preview = st.data_editor(
            preview_df,
            column_config={
                "Task": st.column_config.TextColumn("Task Name", width="medium"),
                "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, width="small"),
                "Hub": st.column_config.SelectboxColumn("Hub", options=hub_names, width="medium"),
                "Staff": st.column_config.NumberColumn("Staff", min_value=1, max_value=100, step=1),
                "Start Time": st.column_config.TimeColumn("Start Time", format="HH:mm"),
                "Day": st.column_config.SelectboxColumn("Day", options=DAY_OPTIONS, width="small"),
                "Duration Mins": st.column_config.NumberColumn("Duration (mins)", min_value=1, max_value=1440, step=1),
                "Enabled": st.column_config.CheckboxColumn("On", default=True),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="import_preview_editor",
        )

        # Import options
        opt_col1, opt_col2 = st.columns(2)
        import_mode = opt_col1.radio("Import mode", ["Replace existing tasks", "Append to existing tasks"], index=0, key="import_mode")
        hide_baseline = opt_col2.checkbox("Hide baseline tasks after import", value=True, key="import_hide_baseline")

        col_a, col_b, col_c = st.columns(3)
        if col_a.button(f"Import {len(edited_preview)} Tasks", type="primary"):
            if import_mode == "Append to existing tasks" and not st.session_state.custom_tasks_df.empty:
                st.session_state.custom_tasks_df = pd.concat(
                    [st.session_state.custom_tasks_df, edited_preview], ignore_index=True
                )
            else:
                st.session_state.custom_tasks_df = edited_preview.copy()
            if hide_baseline:
                st.session_state.use_baseline = False
            reset_import_wizard()
            st.rerun()
        if col_b.button("Back to Mapping", key="back_step3"):
            st.session_state.import_step = 2
            st.rerun()
        if col_c.button("Cancel", key="cancel_step3"):
            reset_import_wizard()
            st.rerun()

    st.divider()

    # --- CUSTOM TASKS EDITOR (always visible) ---
    st.subheader("Imported Custom Tasks")
    st.caption("Edit imported tasks in-place: change hub, staff, timing, or toggle them on/off.")
    if st.session_state.custom_tasks_df.empty:
        st.info("No custom tasks imported yet. Upload a file above to populate this table.")
    else:
        edited_custom = st.data_editor(
            st.session_state.custom_tasks_df,
            column_config={
                "Task": st.column_config.TextColumn("Task Name", width="medium"),
                "Category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, width="small"),
                "Hub": st.column_config.SelectboxColumn("Hub", options=get_hub_names(), width="medium"),
                "Staff": st.column_config.NumberColumn("Staff", min_value=1, max_value=100, step=1),
                "Start Time": st.column_config.TimeColumn("Start Time", format="HH:mm"),
                "Day": st.column_config.SelectboxColumn("Day", options=DAY_OPTIONS, width="small"),
                "Duration Mins": st.column_config.NumberColumn("Duration (mins)", min_value=1, max_value=1440, step=1),
                "Enabled": st.column_config.CheckboxColumn("On", default=True),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="custom_editor",
        )
        st.session_state.custom_tasks_df = edited_custom

# =====================================================================
# TAB: DASHBOARD
# =====================================================================
with tab_dash:
    tasks = []
    ms_df = st.session_state.milestone_df
    bl_df = st.session_state.baseline_df

    # --- Parse milestones ---
    def get_milestone_dt(name):
        row = ms_df[ms_df["Milestone"] == name]
        if row.empty:
            return datetime.combine(T_DATE, time(0, 0))
        r = row.iloc[0]
        day_str = str(r["Day"]) if pd.notna(r["Day"]) else "T"
        offset = int(day_str.replace("T+", "").replace("T", "0")) if "+" in day_str else 0
        return datetime.combine(T_DATE + timedelta(days=offset), r["Time"])

    INVESTOR_CUTOFF = get_milestone_dt("Investor Cutoff")
    TRADE_CUTOFF = get_milestone_dt("Trade Cutoff")
    VALUATION_POINT = get_milestone_dt("Valuation Point")
    NAV_DEADLINE = get_milestone_dt("NAV Delivery SLA")

    # --- Build baseline waterfall ---
    if st.session_state.use_baseline:
        enabled = bl_df[bl_df["Enabled"] == True].copy()

        fixed_tasks = enabled[enabled["Fixed Mins"] > 0]
        waterfall_tasks = enabled[(enabled["Avg Mins/Fund"] > 0) & (enabled["Fixed Mins"] == 0)]

        latest_fixed_end = VALUATION_POINT
        for _, row in fixed_tasks.iterrows():
            day_str = str(row["Day"]) if pd.notna(row["Day"]) else "T"
            offset = int(day_str.replace("T+", "").replace("T", "0")) if "+" in day_str else 0
            start = datetime.combine(T_DATE + timedelta(days=offset), row["Start Time"])
            end = add_mins(start, int(row["Fixed Mins"]))
            tasks.append(dict(Task=row["Task"], Start=start, End=end, Hub=row["Hub"], Cat=row["Category"], Cost_Raw=0, Staff=0))
            if end > latest_fixed_end:
                latest_fixed_end = end

        cursor = max(latest_fixed_end, VALUATION_POINT)
        prev_hub = None

        for _, row in waterfall_tasks.iterrows():
            hub_name = row["Hub"]
            staff = int(row["Staff"])
            avg = float(row["Avg Mins/Fund"])
            rate, overhead = get_hub_info(hub_name)

            wait = latency_gap if (prev_hub is not None and prev_hub != hub_name) else 0
            actual_start = add_mins(cursor, wait)
            dur = get_concurrent_duration(total_funds * avg, max(staff, 1), overhead)
            end = add_mins(actual_start, dur)
            cost = (dur / 60) * rate * staff

            tasks.append(dict(Task=row["Task"], Start=actual_start, End=end, Hub=hub_name, Cat=row["Category"], Cost_Raw=cost, Staff=staff))
            cursor = end
            prev_hub = hub_name

    # --- Custom tasks ---
    ct_df = st.session_state.custom_tasks_df
    if not ct_df.empty:
        enabled_ct = ct_df[ct_df["Enabled"] == True]
        for _, row in enabled_ct.iterrows():
            day_str = str(row["Day"]) if pd.notna(row["Day"]) else "T"
            offset = int(day_str.replace("T+", "").replace("T", "0")) if "+" in day_str else 0
            start = datetime.combine(T_DATE + timedelta(days=offset), row["Start Time"])
            dur = float(row["Duration Mins"])
            end = add_mins(start, dur)
            hub_name = row["Hub"]
            rate, _ = get_hub_info(hub_name)
            staff = int(row["Staff"])
            cost = (dur / 60) * rate * staff
            tasks.append(dict(Task=row["Task"], Start=start, End=end, Hub=hub_name, Cat=row["Category"], Cost_Raw=cost, Staff=staff))

    # --- Guard ---
    if not tasks:
        st.error("No tasks to display! Upload a file or enable baseline tasks.")
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
    with st.expander("Detailed Workload & Unit Economics", expanded=True):
        display_df = df_tasks.copy().sort_values(by="Start")
        display_df['Day'] = display_df['Start'].apply(get_day_label)
        display_df['Duration'] = ((display_df['End'] - display_df['Start']).dt.total_seconds() / 60).astype(int).astype(str) + " min"
        display_df['Start GMT'] = display_df['Start'].dt.strftime("%H:%M")
        display_df['End GMT'] = display_df['End'].dt.strftime("%H:%M")
        display_df['Cost/Fund'] = (display_df['Cost_Raw'] / max(total_funds, 1)).apply(lambda x: f"${x:.2f}" if x > 0 else "-")
        display_df['Total Cost'] = display_df['Cost_Raw'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
        st.dataframe(display_df[['Day', 'Task', 'Cat', 'Hub', 'Start GMT', 'End GMT', 'Duration', 'Staff', 'Total Cost', 'Cost/Fund']], use_container_width=True, hide_index=True)
