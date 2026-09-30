import io
from pathlib import Path

import pandas as pd
import streamlit as st

from core.data_modeling import infer_relationships, join_tables, relationship_frame, validate_relationship

st.set_page_config(page_title="InsightAI | Data Modeling", page_icon="🔗", layout="wide")

st.markdown(
    """
    <style>
    .model-header {padding:26px 30px;border-radius:18px;margin-bottom:22px;
        background:linear-gradient(135deg,rgba(37,99,235,.13),rgba(99,102,241,.08));
        border:1px solid rgba(100,116,139,.18)}
    .model-header h1 {margin:0;font-size:32px}
    .model-header p {margin:8px 0 0;color:#64748b}
    .card {padding:18px;border-radius:14px;border:1px solid rgba(100,116,139,.18);margin-bottom:12px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="model-header">
      <h1>🔗 Data Modeling</h1>
      <p>Connect multiple datasets, validate relationships, preview joins, and create a combined analytical dataset.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "data_model_tables" not in st.session_state:
    st.session_state.data_model_tables = {}
if "data_model_relationships" not in st.session_state:
    st.session_state.data_model_relationships = []
if "data_model_result" not in st.session_state:
    st.session_state.data_model_result = None

# Register current dataset as the first table.
active = st.session_state.get("active_dataframe")
active_name = st.session_state.get("active_dataset") or "Active Dataset"
if isinstance(active, pd.DataFrame) and not active.empty:
    st.session_state.data_model_tables.setdefault(active_name, active.copy())

st.subheader("1. Tables")
col1, col2 = st.columns([2, 1])
with col1:
    uploads = st.file_uploader(
        "Add related datasets",
        type=["csv", "xlsx", "xls", "json", "parquet", "tsv", "ods"],
        accept_multiple_files=True,
    )
with col2:
    if st.button("🧹 Clear Model", use_container_width=True):
        st.session_state.data_model_tables = {}
        st.session_state.data_model_relationships = []
        st.session_state.data_model_result = None
        st.rerun()

if uploads:
    for upload in uploads:
        name = Path(upload.name).stem
        try:
            suffix = Path(upload.name).suffix.lower()
            if suffix == ".csv":
                frame = pd.read_csv(upload)
            elif suffix in (".xlsx", ".xls"):
                frame = pd.read_excel(upload)
            elif suffix == ".json":
                frame = pd.read_json(upload)
            elif suffix == ".parquet":
                frame = pd.read_parquet(upload)
            elif suffix == ".tsv":
                frame = pd.read_csv(upload, sep="\t")
            elif suffix == ".ods":
                frame = pd.read_excel(upload, engine="odf")
            else:
                continue
            st.session_state.data_model_tables[name] = frame
        except Exception as exc:
            st.error(f"Could not load {upload.name}: {exc}")

if not st.session_state.data_model_tables:
    st.info("Add at least two datasets to build a relationship model.")
    st.stop()

summary = []
for name, frame in st.session_state.data_model_tables.items():
    summary.append({"Table": name, "Rows": len(frame), "Columns": len(frame.columns), "Size": f"{frame.memory_usage(deep=True).sum()/1024/1024:.1f} MB"})
st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

if len(st.session_state.data_model_tables) < 2:
    st.warning("Add a second dataset to enable relationship discovery.")
    st.stop()

# Automatic discovery
st.subheader("2. Relationship Discovery")
if st.button("🔎 Detect Relationships", type="primary"):
    st.session_state.data_model_relationships = infer_relationships(st.session_state.data_model_tables)
    st.session_state.data_model_result = None

rels = st.session_state.data_model_relationships
if rels:
    st.dataframe(relationship_frame(rels), use_container_width=True, hide_index=True)
else:
    st.info("No relationships detected yet. You can define one manually below.")

st.subheader("3. Define / Select Relationship")
table_names = list(st.session_state.data_model_tables)
left_table = st.selectbox("Left table", table_names, key="model_left_table")
left_df = st.session_state.data_model_tables[left_table]
left_col = st.selectbox("Left key", list(left_df.columns), key="model_left_col")

right_options = [n for n in table_names if n != left_table]
right_table = st.selectbox("Right table", right_options, key="model_right_table")
right_df = st.session_state.data_model_tables[right_table]
right_col = st.selectbox("Right key", list(right_df.columns), key="model_right_col")

join_type_label = st.selectbox("Join type", ["Left", "Inner", "Right", "Outer"], index=0)
how = join_type_label.lower()

validation = validate_relationship(left_df, left_col, right_df, right_col)
if validation["valid"]:
    st.success(
        f"Matching keys: {validation['matched_keys']:,} | "
        f"Left unmatched: {validation['left_unmatched_keys']:,} | "
        f"Right unmatched: {validation['right_unmatched_keys']:,}"
    )
else:
    st.error(validation["message"])

if st.button("🔗 Preview Relationship", use_container_width=True):
    if validation["valid"]:
        try:
            preview, stats = join_tables(left_df, left_col, right_df, right_col, how=how, right_prefix=right_table)
            st.session_state.data_model_preview = preview.head(100)
            st.session_state.data_model_preview_stats = stats
        except Exception as exc:
            st.error(f"Join failed: {exc}")

if "data_model_preview" in st.session_state:
    st.caption(f"Preview rows: {len(st.session_state.data_model_preview):,}")
    st.dataframe(st.session_state.data_model_preview, use_container_width=True, height=350)
    stats = st.session_state.get("data_model_preview_stats", {})
    if stats:
        st.info(f"Output rows: {stats.get('output_rows', 0):,} | Row multiplier: {stats.get('row_multiplier', 1)}x")

st.subheader("4. Create Combined Analytical Dataset")
st.caption("The combined dataset becomes the active dataset only when you explicitly apply the model.")

if st.button("🚀 Apply Relationship to Active Dataset", type="primary", use_container_width=True):
    if not validation["valid"]:
        st.error("Cannot apply the model because the selected relationship has no matching keys.")
    else:
        try:
            combined, stats = join_tables(left_df, left_col, right_df, right_col, how=how, right_prefix=right_table)
            st.session_state.model_original_dataframe = st.session_state.get("active_dataframe")
            st.session_state.model_original_dataset = st.session_state.get("active_dataset")
            st.session_state.active_dataframe = combined
            st.session_state.active_dataset = f"{left_table} + {right_table} (modeled)"
            st.session_state.data_model_result = combined
            st.success(f"Model applied successfully: {len(combined):,} rows × {len(combined.columns):,} columns.")
            st.info("Dashboard, AI Analyst, Query Engine, Anomaly Detection and Reports can now analyze the modeled dataset.")
        except Exception as exc:
            st.error(f"Could not apply relationship: {exc}")

if st.session_state.get("data_model_result") is not None:
    st.divider()
    st.subheader("5. Model Result")
    result = st.session_state.data_model_result
    st.dataframe(result.head(100), use_container_width=True, height=350)
    st.download_button(
        "⬇️ Download Modeled Dataset",
        data=result.to_csv(index=False).encode("utf-8"),
        file_name="insightai_modeled_dataset.csv",
        mime="text/csv",
        use_container_width=True,
    )
