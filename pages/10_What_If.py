"""InsightAI | What-If Analysis — dataset-driven Decision Intelligence."""
from __future__ import annotations
import re
import streamlit as st
import pandas as pd
import plotly.express as px
from core.what_if import available_metrics, run_multi_scenario, evaluate_formula

st.set_page_config(page_title="InsightAI | What-If Analysis", page_icon="🔮", layout="wide")
st.title("🔮 What-If Analysis")
st.caption("Build transparent scenarios from any dataset. Metrics are discovered dynamically; no business metric is hard-coded.")

df = st.session_state.get("active_dataframe")
if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    st.info("No active dataset is loaded yet. This module is intentionally open. Load a dataset from Select Data to run a scenario.")
    st.stop()

numeric = [str(c) for c in df.select_dtypes(include="number").columns]
categorical = [str(c) for c in df.select_dtypes(include=["object", "category", "bool"]).columns]
if "whatif_calculated_metrics" not in st.session_state:
    st.session_state.whatif_calculated_metrics = {}
calc = st.session_state.whatif_calculated_metrics

st.markdown("### 🧮 Optional Calculated Metrics")
st.caption("Create your own metric from numeric fields. Example: Profit = Revenue - Cost. The metric is then available in the What-If selector.")
if numeric:
    with st.expander("Create Calculated Metric", expanded=False):
        m1, m2 = st.columns([1, 2])
        with m1:
            calc_name = st.text_input("Metric name", placeholder="e.g. Profit")
        with m2:
            field_tokens = ", ".join(numeric)
            calc_formula = st.text_input("Formula", placeholder="e.g. Revenue - Cost")
        st.caption(f"Available numeric fields: {field_tokens}")
        if st.button("➕ Create Metric", key="create_wi_metric"):
            safe_name = calc_name.strip()
            if not safe_name:
                st.warning("Enter a metric name.")
            elif safe_name in ["Row Count"] + numeric:
                st.warning("That name is already used by a dataset field or system metric.")
            elif not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", safe_name):
                st.warning("Use letters, numbers, spaces or underscores in the metric name.")
            else:
                # Formula evaluator expects Python-style column identifiers.
                # Replace spaces in column names with backtick-free identifiers is
                # deliberately avoided; users can use columns whose names are valid identifiers.
                try:
                    evaluate_formula(df, calc_formula)
                    calc[safe_name] = calc_formula
                    st.success(f"Created metric: {safe_name} = {calc_formula}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Invalid formula: {exc}")
        if calc:
            st.dataframe(pd.DataFrame([{"Metric": k, "Formula": v} for k, v in calc.items()]), use_container_width=True, hide_index=True)
            remove = st.selectbox("Remove calculated metric", ["None"] + list(calc.keys()), key="remove_wi_metric")
            if remove != "None" and st.button("🗑️ Remove Metric", key="remove_wi_metric_btn"):
                del calc[remove]
                st.rerun()
else:
    st.info("No numeric fields are available for metric simulation.")

metrics = available_metrics(df, calc)
st.markdown("### 1️⃣ Build Scenario")
if "whatif_assumptions" not in st.session_state:
    st.session_state.whatif_assumptions = [{"metric": metrics[0], "scenario_type": "Increase by %", "adjustment": 10.0}]

for i, a in enumerate(st.session_state.whatif_assumptions):
    c1, c2, c3, c4 = st.columns([3, 2.5, 2, 1])
    with c1:
        a["metric"] = st.selectbox("Metric", metrics, index=metrics.index(a["metric"]) if a["metric"] in metrics else 0, key=f"wi_metric_{i}")
    with c2:
        types = ["Increase by %", "Decrease by %", "Add", "Subtract"]
        a["scenario_type"] = st.selectbox("Assumption", types, index=types.index(a["scenario_type"]) if a["scenario_type"] in types else 0, key=f"wi_type_{i}")
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
        st.session_state.what_if_result = run_multi_scenario(df, st.session_state.whatif_assumptions, group_by, filter_column, filter_value, calc)
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
    st.markdown("### 3️⃣ Assumption Evidence")
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
