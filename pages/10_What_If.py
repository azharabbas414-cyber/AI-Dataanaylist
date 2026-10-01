"""InsightAI | What-If Analysis — Decision Intelligence"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from core.what_if import available_metrics, run_multi_scenario

st.set_page_config(page_title="InsightAI | What-If Analysis", page_icon="🔮", layout="wide")

st.title("🔮 What-If Analysis")
st.caption("Build transparent business scenarios without changing your original dataset.")

df = st.session_state.get("active_dataframe")
if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    st.info("No active dataset is loaded yet. This module is intentionally open. Load a dataset from Select Data to run a scenario.")
    st.markdown("### Decision Intelligence\n\nCreate multiple assumptions, compare their combined impact, and identify which groups contribute most to the scenario.")
    st.stop()

metrics = available_metrics(df)
categorical = [str(c) for c in df.select_dtypes(include=["object", "category", "bool"]).columns]

st.markdown("### 1️⃣ Build Scenario")
if "whatif_assumptions" not in st.session_state:
    st.session_state.whatif_assumptions = [{"metric": metrics[0], "scenario_type": "Increase by %", "adjustment": 10.0}]

for i, a in enumerate(st.session_state.whatif_assumptions):
    c1, c2, c3, c4 = st.columns([3, 2.5, 2, 1])
    with c1:
        a["metric"] = st.selectbox("Metric", metrics, index=metrics.index(a["metric"]) if a["metric"] in metrics else 0, key=f"wi_metric_{i}")
    with c2:
        types = ["Increase by %", "Decrease by %", "Add", "Subtract"]
        a["scenario_type"] = st.selectbox("Assumption", types, index=types.index(a["scenario_type"]), key=f"wi_type_{i}")
    with c3:
        a["adjustment"] = st.number_input("Adjustment", min_value=0.0, value=float(a["adjustment"]), step=1.0, key=f"wi_adj_{i}")
    with c4:
        if len(st.session_state.whatif_assumptions) > 1 and st.button("🗑️", key=f"wi_del_{i}"):
            st.session_state.whatif_assumptions.pop(i)
            st.rerun()

b1, b2 = st.columns(2)
with b1:
    if st.button("➕ Add Assumption", use_container_width=True):
        st.session_state.whatif_assumptions.append({"metric": metrics[0], "scenario_type": "Increase by %", "adjustment": 5.0})
        st.rerun()
with b2:
    if st.button("♻️ Reset Scenario", use_container_width=True):
        st.session_state.whatif_assumptions = [{"metric": metrics[0], "scenario_type": "Increase by %", "adjustment": 10.0}]
        st.session_state.pop("what_if_result", None)
        st.rerun()

c1, c2 = st.columns(2)
with c1:
    group_by = st.selectbox("Impact breakdown", ["None"] + categorical, key="whatif_group_v2")
with c2:
    filter_column = st.selectbox("Optional filter", ["None"] + categorical, key="whatif_filter_v2")
filter_value = None
if filter_column != "None":
    vals = sorted(df[filter_column].dropna().astype(str).unique().tolist())
    filter_value = st.selectbox("Filter value", vals, key="whatif_filter_value_v2") if vals else None

if st.button("🚀 Run Combined Scenario", type="primary", use_container_width=True):
    try:
        st.session_state.what_if_result = run_multi_scenario(df, st.session_state.whatif_assumptions, group_by, filter_column, filter_value)
    except Exception as exc:
        st.error(f"Unable to run scenario: {exc}")

result = st.session_state.get("what_if_result")
if result:
    st.markdown("### 2️⃣ Decision Impact")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Actual Baseline", f"{result['actual']:,.2f}")
    k2.metric("Scenario", f"{result['scenario']:,.2f}")
    k3.metric("Expected Impact", f"{result['impact']:+,.2f}")
    k4.metric("Impact %", f"{result['impact_pct']:+.2f}%")

    st.markdown("### 3️⃣ Assumption Summary")
    st.dataframe(pd.DataFrame(result["assumptions"]), use_container_width=True, hide_index=True)

    st.markdown("### 4️⃣ Actual vs Scenario")
    comparison = result["result"]
    st.dataframe(comparison.style.format({"Actual": "{:,.2f}", "Scenario": "{:,.2f}", "Impact": "{:+,.2f}", "Impact %": "{:+.2f}%"}), use_container_width=True, hide_index=True)

    fig = px.bar(comparison, x="Group", y=["Actual", "Scenario"], barmode="group", title="Actual vs Combined Scenario")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 5️⃣ Impact Ranking")
    ranking = comparison.copy()
    ranking["Absolute Impact"] = ranking["Impact"].abs()
    ranking = ranking.sort_values("Absolute Impact", ascending=False)
    st.dataframe(ranking[["Group", "Impact", "Impact %"]].style.format({"Impact": "{:+,.2f}", "Impact %": "{:+.2f}%"}), use_container_width=True, hide_index=True)

    direction = "increase" if result["impact"] >= 0 else "decrease"
    st.markdown("### 🧠 Management Interpretation")
    st.success(f"Under the defined assumptions, the modeled result shows an **{direction} of {abs(result['impact']):,.2f} ({abs(result['impact_pct']):.2f}%)** versus the baseline.")
    st.caption("This is deterministic scenario simulation, not a causal forecast. The original dataset is never modified.")
