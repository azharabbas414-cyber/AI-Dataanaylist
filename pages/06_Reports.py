import streamlit as st
import pandas as pd
from core.reporting import (
    build_report_data, generate_executive_summary, generate_report_findings,
    generate_pdf_report, generate_docx_report, generate_excel_report,
    metric_candidates, top_category_tables, time_series_tables,
)

st.set_page_config(page_title="InsightAI | Management Reports", page_icon="📄", layout="wide")

st.markdown("""
<style>
.report-header{padding:24px 28px;border-radius:16px;margin-bottom:22px;background:linear-gradient(135deg,rgba(16,185,129,.12),rgba(59,130,246,.08));border:1px solid rgba(100,116,139,.18)}
.section-title{font-size:21px;font-weight:700;margin:24px 0 12px}
.metric-card{padding:16px;border-radius:14px;border:1px solid rgba(100,116,139,.18);min-height:95px}.metric-label{color:#64748b;font-size:13px}.metric-value{font-size:25px;font-weight:700;margin-top:6px}
</style>
""", unsafe_allow_html=True)

raw = st.session_state.get("active_dataframe")
if raw is None:
    st.warning("No active dataset found. Please select or upload a dataset from the Home page.")
    if st.button("🏠 Go to Home", type="primary"):
        st.switch_page("streamlitapp.py")
    st.stop()

raw_df = raw.copy()
dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")

# Reconstruct Dashboard slicers.
report_df = raw_df.copy()
filters = {}
for col in st.session_state.get("dashboard_filter_cat_fields", []):
    selected = st.session_state.get(f"dashboard_filter_value_{col}", [])
    if selected:
        report_df = report_df[report_df[col].fillna("Missing").astype(str).isin(selected)]
        filters[col] = ", ".join(map(str, selected))
for col in raw_df.columns:
    selected = st.session_state.get(f"dashboard_filter_date_{col}")
    if selected and isinstance(selected, (tuple, list)) and len(selected) == 2:
        parsed = pd.to_datetime(report_df[col], errors="coerce")
        start = pd.Timestamp(selected[0]); end = pd.Timestamp(selected[1]) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
        report_df = report_df[parsed.between(start, end, inclusive="both")]
        filters[col] = f"{selected[0]} → {selected[1]}"
for col in st.session_state.get("dashboard_filter_num_fields", []):
    selected = st.session_state.get(f"dashboard_filter_value_{col}")
    if selected and isinstance(selected, (tuple, list)) and len(selected) == 2:
        vals = pd.to_numeric(report_df[col], errors="coerce")
        report_df = report_df[vals.between(float(selected[0]), float(selected[1]), inclusive="both")]
        filters[col] = f"{selected[0]:g} → {selected[1]:g}"

if report_df.empty:
    st.error("Current Dashboard filters return no rows. Broaden the filters before generating a report.")
    st.stop()

st.markdown(f"<div class='report-header'><h1>📄 Management Reporting</h1><p>Create a management-ready report from <b>{dataset_name}</b>. Choose exactly what you want included.</p></div>", unsafe_allow_html=True)

r = build_report_data(report_df)
cols = st.columns(5)
for c, label, value in zip(cols, ["Rows", "Columns", "Completeness", "Missing Cells", "Duplicates"], [f"{r['rows']:,}", f"{r['columns']:,}", f"{r['completeness']:.1f}%", f"{r['missing_cells']:,}", f"{r['duplicate_rows']:,}"]):
    with c:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>", unsafe_allow_html=True)

st.markdown("<div class='section-title'>🎛️ Report Builder — Choose What Management Should Receive</div>", unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.markdown("**Management Summary**")
    include_exec = st.checkbox("📌 Executive Summary", True)
    include_kpi = st.checkbox("💰 KPI / Important Values", True)
    include_findings = st.checkbox("🔎 Key Findings & Issues", True)
    include_top = st.checkbox("🏆 Top / Bottom Categories", True)
    include_trends = st.checkbox("📈 Trend / Time Analysis", True)
with right:
    st.markdown("**Visual & Supporting Data**")
    include_charts = st.checkbox("📊 Graphs / Charts", True)
    include_quality = st.checkbox("🧹 Data Quality", False)
    include_filters = st.checkbox("🎛️ Applied Filter Context", True)
    include_raw = st.checkbox("📋 Raw / Filtered Data Appendix", False)
    raw_rows = st.number_input("Raw data rows to include", min_value=25, max_value=5000, value=250, step=25, disabled=not include_raw)

st.markdown("**Chart Selection**")
saved = st.session_state.get("dashboard_saved_charts", [])
chart_options = [item.get("title", item.get("config", {}).get("title", "Saved Chart")) for item in saved]
selected_chart_titles = st.multiselect("Include saved dashboard charts", chart_options, default=chart_options if include_charts else []) if chart_options else []

st.markdown("**Report Style**")
style = st.selectbox("Management report emphasis", ["Executive Summary", "Management + Detailed", "Full Analytical"])
if style == "Executive Summary":
    # Keep user choices, but encourage a concise report.
    pass
elif style == "Management + Detailed":
    include_top = True; include_trends = True
elif style == "Full Analytical":
    include_top = True; include_trends = True; include_quality = True

options = {
    "Executive Summary": include_exec,
    "KPI Summary": include_kpi,
    "Key Findings": include_findings,
    "Top/Bottom Analysis": include_top,
    "Trend Analysis": include_trends,
    "Charts": include_charts and bool(selected_chart_titles or not saved),
    "Data Quality": include_quality,
    "Raw Data": include_raw,
    "Raw Data Rows": int(raw_rows),
    "Chart Register": True,
    "Applied Filters": include_filters,
}
selected_saved = [x for x in saved if x.get("title", x.get("config", {}).get("title", "Saved Chart")) in selected_chart_titles]

st.markdown("<div class='section-title'>👀 Report Preview</div>", unsafe_allow_html=True)
preview_cols = st.columns(3)
preview_items = [("Executive Summary", include_exec), ("KPIs / Important Values", include_kpi), ("Key Findings", include_findings), ("Top / Bottom", include_top), ("Trends", include_trends), ("Graphs", include_charts), ("Data Quality", include_quality), ("Raw Data", include_raw)]
for i, (label, enabled) in enumerate(preview_items):
    with preview_cols[i % 3]:
        st.success(f"✓ {label}") if enabled else st.caption(f"— {label}")

if include_exec:
    with st.expander("Executive Summary Preview", expanded=True):
        for x in generate_executive_summary(report_df, r): st.markdown("• " + x)
if include_kpi:
    with st.expander("Important Values Preview", expanded=True):
        metrics = metric_candidates(report_df)
        kpi_rows = []
        for name, series in metrics.items():
            v = series.dropna()
            if len(v): kpi_rows.append({"Metric": name, "Total": v.sum(), "Average": v.mean(), "Maximum": v.max()})
        if kpi_rows: st.dataframe(pd.DataFrame(kpi_rows), use_container_width=True, hide_index=True)
if include_top:
    with st.expander("Top Category Preview"):
        for title, frame in top_category_tables(report_df, 10)[:3]:
            st.markdown(f"**{title}**"); st.dataframe(frame, use_container_width=True, hide_index=True)
if include_trends:
    with st.expander("Trend Preview"):
        for title, frame in time_series_tables(report_df)[:2]:
            st.markdown(f"**{title}**"); st.dataframe(frame, use_container_width=True, hide_index=True)

st.markdown("<div class='section-title'>⬇️ Generate Report</div>", unsafe_allow_html=True)
if "report3_pdf" not in st.session_state: st.session_state.report3_pdf = None
if "report3_docx" not in st.session_state: st.session_state.report3_docx = None
if "report3_xlsx" not in st.session_state: st.session_state.report3_xlsx = None

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📄 Generate PDF", type="primary", use_container_width=True):
        with st.spinner("Building management PDF..."):
            st.session_state.report3_pdf = generate_pdf_report(report_df, dataset_name, filters if include_filters else None, options, selected_saved)
    if st.session_state.report3_pdf:
        st.download_button("⬇️ Download PDF", st.session_state.report3_pdf, "InsightAI_Management_Report.pdf", "application/pdf", use_container_width=True)
with c2:
    if st.button("📝 Generate Word", type="primary", use_container_width=True):
        with st.spinner("Building management Word report..."):
            st.session_state.report3_docx = generate_docx_report(report_df, dataset_name, filters if include_filters else None, options, selected_saved)
    if st.session_state.report3_docx:
        st.download_button("⬇️ Download Word", st.session_state.report3_docx, "InsightAI_Management_Report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
with c3:
    if st.button("📊 Generate Excel", type="primary", use_container_width=True):
        with st.spinner("Building management Excel workbook..."):
            st.session_state.report3_xlsx = generate_excel_report(report_df, dataset_name, filters if include_filters else None, options, selected_saved)
    if st.session_state.report3_xlsx:
        st.download_button("⬇️ Download Excel", st.session_state.report3_xlsx, "InsightAI_Management_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

st.divider(); st.caption("InsightAI • Management Reporting • Choose the story, values, graphs and supporting data you want to deliver.")
