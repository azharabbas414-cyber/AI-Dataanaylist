"""InsightAI | What-If Analysis"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from core.what_if import available_metrics, run_scenario

st.set_page_config(page_title="InsightAI | What-If Analysis", page_icon="🔮", layout="wide")

st.title("🔮 What-If Analysis")
st.caption("Test business assumptions without changing your original dataset.")

df = st.session_state.get("active_dataframe")

if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    st.info(
        "No active dataset is loaded yet. This module is intentionally open. "
        "Load a dataset from Select Data to run a scenario."
    )
    st.markdown("""
### What-If Analysis

Ask questions such as:

- What if sales increase by 10%?
- What if quantity decreases by 5%?
- What if every value increases by 100?
- What would the impact be by country?

**Your original dataset is never modified.**
""")
    st.stop()

metrics = available_metrics(df)
categorical = [str(c) for c in df.select_dtypes(include=["object", "category", "bool"]).columns]
groups = ["None"] + categorical
filters = ["None"] + categorical

st.markdown("### 1️⃣ Define Scenario")

c1, c2, c3 = st.columns(3)
with c1:
    metric = st.selectbox("Metric", metrics, key="whatif_metric")
with c2:
    scenario_type = st.selectbox(
        "Scenario",
        ["Increase by %", "Decrease by %", "Add", "Subtract"],
        key="whatif_type",
    )
with c3:
    adjustment = st.number_input(
        "Adjustment",
        min_value=0.0,
        value=10.0,
        step=1.0,
        key="whatif_adjustment",
        help="Percentage for Increase/Decrease; absolute value for Add/Subtract.",
    )

c4, c5 = st.columns(2)
with c4:
    group_by = st.selectbox(
        "Break down by",
        groups,
        key="whatif_group",
        help="Compare actual vs scenario by a dimension.",
    )
with c5:
    filter_column = st.selectbox(
        "Optional filter",
        filters,
        key="whatif_filter_column",
    )

filter_value = None
if filter_column != "None":
    values = sorted(df[filter_column].dropna().astype(str).unique().tolist())
    if values:
        filter_value = st.selectbox("Filter value", values, key="whatif_filter_value")

if st.button("🚀 Run Scenario", type="primary", use_container_width=True):
    try:
        result = run_scenario(
            df,
            metric,
            scenario_type,
            float(adjustment),
            group_by,
            filter_column,
            filter_value,
        )
        st.session_state.what_if_result = result
    except Exception as exc:
        st.error(f"Unable to run scenario: {exc}")

result = st.session_state.get("what_if_result")

if result:
    st.markdown("### 2️⃣ Actual vs Scenario")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Actual", f"{result['actual']:,.2f}")
    k2.metric("Scenario", f"{result['scenario']:,.2f}")
    k3.metric("Impact", f"{result['impact']:+,.2f}")
    k4.metric("Impact %", f"{result['impact_pct']:+.2f}%")

    st.success(
        f"Scenario: **{result['adjustment_label']}** on **{result['metric']}** "
        f"using {result['rows_used']:,} rows."
    )

    st.markdown("### 3️⃣ Scenario Calculation")
    st.code(result["formula"])

    st.markdown("### 4️⃣ Comparison")
    comparison = result["result"]
    st.dataframe(
        comparison.style.format({
            "Actual": "{:,.2f}",
            "Scenario": "{:,.2f}",
            "Impact": "{:+,.2f}",
            "Impact %": "{:+.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    fig = px.bar(
        comparison,
        x="Group",
        y=["Actual", "Scenario"],
        barmode="group",
        title=f"Actual vs Scenario — {result['metric']}",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🧠 Interpretation")
    direction = "increase" if result["impact"] >= 0 else "decrease"
    st.write(
        f"The scenario produces a **{direction} of {abs(result['impact']):,.2f} "
        f"({abs(result['impact_pct']):.2f}%)** compared with the current baseline."
    )

    st.caption(
        "What-If is deterministic simulation. It does not modify the active dataset "
        "and does not use an AI model to perform the calculation."
    )
