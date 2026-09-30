
import io
import pandas as pd
import numpy as np
import streamlit as st

from core.reporting import (
    build_report_data,
    generate_management_report,
    generate_pdf_report,
    generate_docx_report,
    generate_excel_report,
)

st.set_page_config(page_title="InsightAI | Reports", page_icon="📄", layout="wide")

st.markdown("""
<style>
.report-header{padding:24px 28px;border-radius:16px;margin-bottom:22px;
background:linear-gradient(135deg,rgba(16,185,129,.12),rgba(59,130,246,.08));
border:1px solid rgba(100,116,139,.18)}
.report-header h1{margin:0;font-size:32px}
.section-title{font-size:21px;font-weight:700;margin:24px 0 12px}
.report-card{padding:16px;border:1px solid rgba(100,116,139,.18);border-radius:14px}
</style>
""", unsafe_allow_html=True)

df = st.session_state.get("active_dataframe")
if df is None or df.empty:
    st.warning("No active dataset found. Please select or upload a dataset first.")
    st.stop()

dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")
report_data = build_report_data(df)

st.markdown(f"""
<div class="report-header">
<h1>📄 Management Reports</h1>
<p>Create a management-ready summary from <b>{dataset_name}</b>.
Choose exactly what you want management to see.</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-title">🎛️ Report Builder</div>', unsafe_allow_html=True)

left, right = st.columns([1, 1])

with left:
    report_style = st.selectbox(
        "Report emphasis",
        ["Executive Summary", "Management + Detailed", "Full Analytical"],
        index=0,
    )

    st.markdown("**Management Content**")
    include_summary = st.checkbox("Executive Summary", True)
    include_kpis = st.checkbox("Important KPIs / Values", True)
    include_findings = st.checkbox("Key Findings & Issues", True)
    include_top_bottom = st.checkbox("Top / Bottom Performers", True)
    include_trend = st.checkbox("Trend / Time Analysis", True)

with right:
    st.markdown("**Supporting Content**")
    include_charts = st.checkbox("Graphs / Charts", True)
    include_anomalies = st.checkbox("Anomaly Summary", False)
    include_forecast = st.checkbox("Forecast Summary", False)
    include_quality = st.checkbox("Data Quality", False)
    include_appendix = st.checkbox("Filtered Data Appendix", False)

    st.caption("Executive reports should normally focus on KPIs, findings, top/bottom performers, trends and selected charts.")

# Presets
if report_style == "Executive Summary":
    # Keep user's choices intact; only show guidance.
    st.info("Executive mode: keep the report concise and management-focused.")
elif report_style == "Management + Detailed":
    st.info("Management + Detailed mode: includes the important numbers plus supporting analysis.")
else:
    st.info("Full Analytical mode: suitable for analysts as well as management.")

selected = {
    "summary": include_summary,
    "kpis": include_kpis,
    "findings": include_findings,
    "top_bottom": include_top_bottom,
    "trend": include_trend,
    "charts": include_charts,
    "anomalies": include_anomalies,
    "forecast": include_forecast,
    "quality": include_quality,
    "appendix": include_appendix,
}

st.markdown('<div class="section-title">👀 Report Preview</div>', unsafe_allow_html=True)

preview = generate_management_report(df, dataset_name, selected, preview=True)

p1, p2, p3 = st.columns(3)
if include_summary:
    p1.success("✓ Executive Summary")
else:
    p1.caption("Executive Summary excluded")
if include_kpis:
    p2.success("✓ KPIs / Important Values")
else:
    p2.caption("KPIs excluded")
if include_findings:
    p3.success("✓ Key Findings")
else:
    p3.caption("Key Findings excluded")

st.markdown("### 📌 Important Values")
if include_kpis and preview["kpis"]:
    kcols = st.columns(min(5, len(preview["kpis"])))
    for i, item in enumerate(preview["kpis"][:5]):
        with kcols[i]:
            st.metric(item["label"], item["value"])
else:
    st.caption("KPIs are not selected.")

if include_summary:
    st.markdown("### 💼 Executive Summary")
    for x in preview["summary"]:
        st.markdown(f"• {x}")

if include_top_bottom:
    st.markdown("### 🏆 Top / Bottom Performers")
    if not preview["top_bottom"].empty:
        st.dataframe(preview["top_bottom"], use_container_width=True, hide_index=True)
    else:
        st.caption("No suitable categorical/metric combination was detected.")

if include_trend:
    st.markdown("### 📈 Trend Analysis")
    if not preview["trend"].empty:
        st.line_chart(preview["trend"].set_index(preview["trend"].columns[0]))
    else:
        st.caption("No suitable date/time + metric combination was detected.")

if include_findings:
    st.markdown("### 🔎 Key Findings")
    for x in preview["findings"]:
        st.info(x)

if include_quality:
    st.markdown("### 🧹 Data Quality")
    q = preview["quality"]
    st.write(q)

st.markdown('<div class="section-title">⬇️ Generate Selected Report</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("📄 Generate PDF", type="primary", use_container_width=True):
        with st.spinner("Building management PDF..."):
            data = generate_pdf_report(df, dataset_name, selected)
            st.download_button(
                "⬇️ Download PDF",
                data=data,
                file_name="InsightAI_Management_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

with c2:
    if st.button("📝 Generate Word", type="primary", use_container_width=True):
        with st.spinner("Building management Word report..."):
            data = generate_docx_report(df, dataset_name, selected)
            st.download_button(
                "⬇️ Download Word",
                data=data,
                file_name="InsightAI_Management_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

with c3:
    if st.button("📊 Generate Excel", type="primary", use_container_width=True):
        with st.spinner("Building management Excel report..."):
            data = generate_excel_report(df, dataset_name, selected)
            st.download_button(
                "⬇️ Download Excel",
                data=data,
                file_name="InsightAI_Management_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

st.divider()
st.caption("InsightAI • Management reporting should summarize the important business story, not merely describe the raw dataset.")
