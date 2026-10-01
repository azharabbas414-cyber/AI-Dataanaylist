"""InsightAI | Data Lineage & Evidence"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from core.data_lineage import build_dataset_lineage, summarize_lineage

st.set_page_config(page_title="InsightAI | Data Lineage", page_icon="🔍", layout="wide")

df = st.session_state.get("active_dataframe")

st.title("🔍 Data Lineage & Evidence")
st.caption("Understand exactly where an InsightAI result came from.")

if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    st.info(
        "No active dataset is loaded yet. This module is intentionally open. "
        "Load a dataset from Select Data to generate lineage evidence."
    )
    st.markdown("""
### What this module will show

**Source → Fields → Transformation → Calculation → Result**

It does not modify your dataset and it does not calculate results using an AI model.
""")
    st.stop()

dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")
base = build_dataset_lineage(df, dataset_name)

latest_query = st.session_state.get("last_query_result")
latest_question = st.session_state.get("ai_last_question", "")

# ------------------------------------------------------------
# Executive source summary
# ------------------------------------------------------------
st.markdown("### 📌 Source Dataset")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Columns", f"{len(df.columns):,}")
c3.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")
c4.metric("Duplicate Rows", f"{int(df.duplicated().sum()):,}")
st.info(f"**Source:** {dataset_name}")

# ------------------------------------------------------------
# Latest analytical result
# ------------------------------------------------------------
st.markdown("### 🎯 Latest Result Being Traced")

if not latest_query:
    st.info(
        "No analytical result has been captured yet. "
        "Open AI Analyst and ask a deterministic question such as "
        "**What is the total sales value by country?**"
    )
else:
    question = latest_question or latest_query.get("question", "")
    metric = latest_query.get("metric") or latest_query.get("intent") or "Query"
    group_by = latest_query.get("group_by") or "None"
    aggregation = latest_query.get("aggregation") or latest_query.get("intent") or "Deterministic query"
    formula = latest_query.get("formula") or latest_query.get("calculation") or "Direct field / deterministic query"
    engine = latest_query.get("engine", "InsightAI deterministic analytics")
    rows_used = latest_query.get("rows_used")

    st.success("✓ Deterministic evidence captured")

    a, b = st.columns(2)
    with a:
        st.markdown("**Question**")
        st.write(question or "Not recorded")
        st.markdown("**Metric**")
        st.write(metric)
        st.markdown("**Fields / Grouping**")
        st.write(group_by)
    with b:
        st.markdown("**Formula / Transformation**")
        st.code(str(formula))
        st.markdown("**Aggregation**")
        st.write(aggregation)
        st.markdown("**Analytics Engine**")
        st.write(engine)
        st.markdown("**Rows Used**")
        st.write(f"{rows_used:,}" if isinstance(rows_used, int) else (rows_used or "Not recorded"))

    st.markdown("### 🔗 Lineage Flow")
    flow = [
        ("📂 SOURCE", dataset_name),
        ("🧬 FIELDS", ", ".join(
            str(x) for x in (
                latest_query.get("fields")
                or [x for x in [latest_query.get("metric"), latest_query.get("group_by")] if x]
            )
        ) or "Dataset fields"),
        ("⚙️ TRANSFORMATION", str(formula)),
        ("📐 AGGREGATION", str(aggregation)),
        ("🎯 GROUPING", str(group_by)),
        ("✅ RESULT", "Actual deterministic query result"),
    ]

    for i, (label, value) in enumerate(flow):
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"**{label}**")
        with col2:
            st.write(value)
        if i < len(flow) - 1:
            st.markdown("↓")

    st.markdown("### 📊 Result Evidence")
    if latest_query.get("results") is not None:
        result = latest_query["results"]
        if isinstance(result, list) and result and isinstance(result[0], dict):
            st.dataframe(pd.DataFrame(result), use_container_width=True, hide_index=True)
        else:
            st.write(result)
    elif latest_query.get("value") is not None:
        st.metric("Result", str(latest_query["value"]))
    else:
        st.info("The latest result did not provide a tabular evidence payload.")

# ------------------------------------------------------------
# Column-level lineage
# ------------------------------------------------------------
st.markdown("### 🧬 Column Lineage")
column_df = pd.DataFrame(base["columns_detail"])
st.dataframe(column_df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------
# Transformation history
# ------------------------------------------------------------
st.markdown("### 🕘 Transformation History")

history = st.session_state.get("lineage_history", [])

if latest_query:
    # Add current query to session history without duplicating the same question.
    signature = (
        latest_query.get("question"),
        latest_query.get("metric"),
        latest_query.get("group_by"),
        latest_query.get("intent"),
    )
    existing_signatures = {
        (
            x.get("question"),
            x.get("metric"),
            x.get("group_by"),
            x.get("intent"),
        )
        for x in history
    }
    if signature not in existing_signatures:
        history.append({
            "question": latest_question or latest_query.get("question", ""),
            "metric": latest_query.get("metric") or latest_query.get("intent"),
            "group_by": latest_query.get("group_by") or "None",
            "formula": latest_query.get("formula") or latest_query.get("calculation") or "Deterministic query",
            "engine": latest_query.get("engine", "InsightAI deterministic analytics"),
        })
        st.session_state.lineage_history = history

if history:
    history_df = pd.DataFrame(history)
    history_df.insert(0, "Step", range(1, len(history_df) + 1))
    st.dataframe(history_df, use_container_width=True, hide_index=True)
else:
    st.caption("No analytical transformation history recorded in this session.")

# ------------------------------------------------------------
# Human-readable summary
# ------------------------------------------------------------
st.markdown("### 🧾 Lineage Summary")
for line in summarize_lineage(base):
    st.markdown(f"- {line}")

st.caption(
    "InsightAI Data Lineage is deterministic audit metadata. "
    "It records evidence; it does not ask an AI model to invent or recalculate the result."
)
