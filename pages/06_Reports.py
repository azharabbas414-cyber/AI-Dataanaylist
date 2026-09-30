
import streamlit as st
import pandas as pd

from core.reporting import (
    build_report_data,
    generate_management_report,
    generate_pdf_report,
    generate_docx_report,
    generate_excel_report,
)

st.set_page_config(page_title="InsightAI | Reports", page_icon="📄", layout="wide")

df = st.session_state.get("active_dataframe")
if df is None or df.empty:
    st.warning("No active dataset found. Please select or upload a dataset first.")
    st.stop()

dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")

st.title("📄 Management Intelligence Reports")
st.caption(
    "Build a concise management report from the actual dataset. "
    "Select the information management needs to see."
)

st.subheader("🎛️ Report Content")

a, b = st.columns(2)

with a:
    st.markdown("**Executive & Business Intelligence**")
    include_summary = st.checkbox("Executive Summary", True)
    include_kpis = st.checkbox("Important KPIs / Values", True)
    include_findings = st.checkbox("Key Findings & Issues", True)
    include_actions = st.checkbox("Recommended Investigation / Management Attention", True)
    include_top_bottom = st.checkbox("Top Contributors / Top & Bottom Performers", True)

with b:
    st.markdown("**Supporting Analysis**")
    include_trend = st.checkbox("Trend / Time Analysis", True)
    include_charts = st.checkbox("Graphs / Charts", True)
    include_quality = st.checkbox("Data Quality", False)
    include_anomalies = st.checkbox("Anomaly Summary", False)
    include_forecast = st.checkbox("Forecast Summary", False)
    include_appendix = st.checkbox("Filtered Data Appendix", False)

selected = {
    "summary": include_summary,
    "kpis": include_kpis,
    "findings": include_findings,
    "actions": include_actions,
    "top_bottom": include_top_bottom,
    "trend": include_trend,
    "charts": include_charts,
    "quality": include_quality,
    "anomalies": include_anomalies,
    "forecast": include_forecast,
    "appendix": include_appendix,
}

st.divider()
st.subheader("👀 Management Report Preview")

preview = generate_management_report(df, dataset_name, selected, preview=True)

if include_kpis and preview["kpis"]:
    st.markdown("### 📌 Important KPIs")
    cols = st.columns(min(5, len(preview["kpis"])))
    for i, item in enumerate(preview["kpis"][:5]):
        with cols[i]:
            st.metric(item["label"], item["value"])

if include_summary:
    st.markdown("### 💼 Executive Summary")
    for item in preview["summary"]:
        st.markdown(f"• {item}")

if include_top_bottom and not preview["top_bottom"].empty:
    st.markdown("### 🏆 Top Contributors")
    st.dataframe(preview["top_bottom"], use_container_width=True, hide_index=True)

if include_trend and not preview["trend"].empty:
    st.markdown("### 📈 Trend")
    chart_df = preview["trend"].set_index(preview["trend"].columns[0])
    st.line_chart(chart_df)

if include_findings:
    st.markdown("### 🔎 Key Findings")
    for item in preview["findings"]:
        st.info(item)

if include_actions:
    st.markdown("### 🎯 Recommended Investigation / Management Attention")
    for item in preview["actions"]:
        st.warning(item)

if include_quality:
    q = preview["quality"]
    st.markdown("### 🧹 Data Quality")
    q1, q2, q3 = st.columns(3)
    q1.metric("Completeness", f"{q['completeness']:.1f}%")
    q2.metric("Missing Cells", f"{q['missing_cells']:,}")
    q3.metric("Duplicate Rows", f"{q['duplicate_rows']:,}")

st.divider()
st.subheader("⬇️ Generate Report")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("📄 Generate PDF", type="primary", use_container_width=True):
        with st.spinner("Building management intelligence PDF..."):
            data = generate_pdf_report(df, dataset_name, selected)
        st.download_button(
            "⬇️ Download PDF",
            data=data,
            file_name="InsightAI_Management_Intelligence_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

with c2:
    if st.button("📝 Generate Word", type="primary", use_container_width=True):
        with st.spinner("Building management intelligence Word report..."):
            data = generate_docx_report(df, dataset_name, selected)
        st.download_button(
            "⬇️ Download Word",
            data=data,
            file_name="InsightAI_Management_Intelligence_Report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

with c3:
    if st.button("📊 Generate Excel", type="primary", use_container_width=True):
        with st.spinner("Building management intelligence Excel report..."):
            data = generate_excel_report(df, dataset_name, selected)
        st.download_button(
            "⬇️ Download Excel",
            data=data,
            file_name="InsightAI_Management_Intelligence_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

st.caption(
    "Management Intelligence focuses on important values, contributors, changes, "
    "findings and recommended investigation — not raw dataset statistics."
)
