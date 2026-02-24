# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time, date

# --- CONFIG ---
st.set_page_config(page_title="UCITS Monte Carlo Simulator", layout="wide")

# --- SIMULATION ENGINE ---
def run_monte_carlo(n_sims, base_time, staff, overhead, volatility):
    """
    Simulates task duration with random noise (Volatility).
    Volatility models the 'Unknown unknowns' of Fund Ops.
    """
    results = []
    # Brooks's Law Base Time
    team_time = base_time / (staff ** 0.7) * (1 + (overhead * staff))
    
    for _ in range(n_sims):
        # We use a Lognormal distribution because tasks can't take negative time 
        # but they can take 3x longer than expected (long tail risk).
        noise = np.random.lognormal(0, volatility)
        sim_time = team_time * noise
        results.append(sim_time)
    return results

# --- SIDEBAR: STRESS PARAMETERS ---
with st.sidebar:
    st.header("🎲 Risk Parameters")
    n_simulations = st.select_slider("Simulation Runs", options=[100, 500, 1000, 5000], value=1000)
    market_vol = st.slider("Process Volatility (σ)", 0.05, 0.50, 0.15, 
                          help="Higher sigma = more frequent system outages and late data feeds.")
    
    st.divider()
    st.header("🏢 Current Setup")
    total_staff = st.number_input("Total FTEs (Global)", 1, 50, 8)
    sla_threshold = st.number_input("SLA Time Limit (Mins from VP)", 100, 1000, 900)

# --- EXECUTION ---
# Modeling the entire critical path as a single aggregate task for the simulation
sim_results = run_monte_carlo(n_simulations, 600, total_staff, 0.08, market_vol)
df_sim = pd.DataFrame(sim_results, columns=['Duration'])

# Calculate Confidence
breaches = df_sim[df_sim['Duration'] > sla_threshold].shape[0]
prob_of_success = (1 - (breaches / n_simulations)) * 100

# --- DASHBOARD ---
st.title("🛡️ Operational Resiliency: Monte Carlo")
st.markdown("Quantifying the probability of hitting your **09:00 GMT SLA** under uncertainty.")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"### Probability of Success")
    color = "#238636" if prob_of_success > 95 else "#d29922" if prob_of_success > 80 else "#f85149"
    st.markdown(f"<div style='background:#161b22; padding:20px; border-radius:12px; border:1px solid #30363d; text-align:center;'>"
                f"<span style='color:{color}; font-size:2.5rem; font-weight:bold;'>{prob_of_success:.1f}%</span>"
                f"</div>", unsafe_allow_html=True)

with c2:
    st.markdown("### Expected Tail Risk")
    tail_risk = df_sim['Duration'].quantile(0.99)
    st.markdown(f"<div style='background:#161b22; padding:20px; border-radius:12px; border:1px solid #30363d; text-align:center;'>"
                f"<span style='font-size:2rem; font-weight:bold;'>{int(tail_risk)}m</span><br>"
                f"<span style='color:#8b949e;'>99th Percentile (Worst Case)</span></div>", unsafe_allow_html=True)

with c3:
    st.markdown("### System Stability")
    st.markdown(f"<div style='background:#161b22; padding:20px; border-radius:12px; border:1px solid #30363d; text-align:center;'>"
                f"<span style='font-size:2rem; font-weight:bold;'>{market_vol*100:.0f}%</span><br>"
                f"<span style='color:#8b949e;'>Standard Deviation (σ)</span></div>", unsafe_allow_html=True)

# Visualizing the Distribution
st.divider()

st.subheader("📊 Probability Distribution of NAV Completion")
fig = px.histogram(df_sim, x="Duration", nbins=50, 
                   title="Distribution of Completion Times (1,000 Scenarios)",
                   color_discrete_sequence=['#3b82f6'])
fig.add_vline(x=sla_threshold, line_dash="dash", line_color="#f85149", 
              annotation_text="SLA DEADLINE", annotation_font_color="#f85149")
fig.update_layout(template="plotly_dark", xaxis_title="Total Minutes from Valuation Point", yaxis_title="Frequency")
st.plotly_chart(fig, use_container_width=True)

# PM Risk Table
st.subheader("📉 Value-at-Risk (VaR) Analysis")

st.write("This table shows the 'Confidence Floor' for your current staffing model.")
percentiles = [50, 75, 90, 95, 99]
p_values = [df_sim['Duration'].quantile(p/100) for p in percentiles]
p_table = pd.DataFrame({"Confidence Level": [f"{p}%" for p in percentiles], 
                        "Completion Time (Mins)": [f"{int(v)}m" for v in p_values],
                        "Status": ["✅ Safe" if v < sla_threshold else "🚨 Breach" for v in p_values]})
st.table(p_table)