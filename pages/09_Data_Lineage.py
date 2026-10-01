"""InsightAI | Data Lineage & Evidence"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from core.data_lineage import build_dataset_lineage, summarize_lineage

st.set_page_config(page_title="InsightAI | Data Lineage", page_icon="🔍", layout="wide")

df = st.session_state.get("active_dataframe")
if df is None or not isinstance(df, pd.DataFrame) or df.empty:
    st.warning("No active dataset found. Please select or upload a dataset first.")
    st.stop()

dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")

st.title("🔍 Data Lineage & Evidence")
st.caption(
    "Trace InsightAI results back to the dataset, fields, calculations, filters and "
    "deterministic query evidence."
)

base = build_dataset_lineage(df, dataset_name)

# Capture the latest deterministic query if available.
latest_query = st.session_state.get("last_query_result")
latest_question = st.session_state.get("ai_last_question", "")
if latest_query:
    base["query"] = {
        "question": latest_question or latest_query.get("question", ""),
        "intent": latest_query.get("intent"),
        "metric": latest_query.get("metric"),
        "group_by": latest_query.get("group_by"),
        "aggregation": latest_query.get("aggregation"),
        "formula": latest_query.get("formula") or latest_query.get("calculation"),
        "engine": latest_query.get("engine", "InsightAI deterministic analytics"),
        "rows_used": latest_query.get("rows_used"),
        "result": latest_query.get("results", latest_query.get("value")),
    }

st.markdown("### 📌 Dataset Source")
a, b, c, d = st.columns(4)
a.metric("Rows", f"{base['rows']:,}")
b.metric("Columns", f"{base['columns']:,}")
c.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")
d.metric("Duplicate Rows", f"{int(df.duplicated().sum()):,}")

st.info(f"**Dataset:** {dataset_name}")

st.markdown("### 🧬 Column Lineage")
column_df = pd.DataFrame(base["columns_detail"])
st.dataframe(column_df, use_container_width=True, hide_index=True)

st.markdown("### 🧮 Latest Calculation / Query Evidence")

if latest_query:
    st.success("A deterministic query result is available for tracing.")
    q1, q2 = st.columns(2)
    with q1:
        st.markdown("**Question**")
        st.write(latest_query.get("question", latest_question) or "Not recorded")
        st.markdown("**Metric**")
        st.write(latest_query.get("metric") or latest_query.get("intent") or "Query")
        st.markdown("**Group By**")
        st.write(latest_query.get("group_by") or "None")
    with q2:
        st.markdown("**Formula / Calculation**")
        st.write(latest_query.get("formula") or latest_query.get("calculation") or "Deterministic query")
        st.markdown("**Engine**")
        st.write(latest_query.get("engine", "InsightAI deterministic analytics"))
        st.markdown("**Rows Used**")
        rows_used = latest_query.get("rows_used")
        st.write(f"{rows_used:,}" if isinstance(rows_used, int) else (rows_used or "Not recorded"))

    if latest_query.get("results") is not None:
        st.markdown("**Result Evidence**")
        result = latest_query["results"]
        if isinstance(result, list) and result and isinstance(result[0], dict):
            st.dataframe(pd.DataFrame(result), use_container_width=True, hide_index=True)
        else:
            st.write(result)
    elif latest_query.get("value") is not None:
        st.metric("Result", str(latest_query["value"]))
else:
    st.info(
        "No query result has been recorded yet. Go to AI Analyst, ask a deterministic "
        "data question, then return here to trace the result."
    )

st.markdown("### 🔗 Lineage Summary")
for line in summarize_lineage(base):
    st.markdown(f"- {line}")

st.caption(
    "Lineage is deterministic metadata. It does not ask the AI model to calculate or "
    "rewrite the underlying result."
)
