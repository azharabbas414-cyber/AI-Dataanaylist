import streamlit as st
import pandas as pd
from core.reporting import (
    build_report_data, generate_executive_summary, generate_report_findings,
    generate_pdf_report, generate_docx_report, generate_excel_report,
)

st.set_page_config(page_title="InsightAI | Reports", page_icon="📄", layout="wide")

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
    if st.button("🏠 Go to Home", type="primary"): st.switch_page("streamlitapp.py")
    st.stop()

raw_df = raw.copy()
dataset_name = st.session_state.get("active_dataset", "InsightAI Dataset")

# Reconstruct the same dashboard filters from session state so Reports reflects
# the user's current Dashboard slicer selections even after navigating here.
report_df = raw_df.copy()
filters = {}
cat_fields = st.session_state.get("dashboard_filter_cat_fields", [])
for col in cat_fields:
    key=f"dashboard_filter_value_{col}"; selected=st.session_state.get(key, [])
    if selected:
        report_df=report_df[report_df[col].fillna("Missing").astype(str).isin(selected)]
        filters[col] = ", ".join(map(str, selected))

# Date filters
for col in raw_df.columns:
    key=f"dashboard_filter_date_{col}"
    selected=st.session_state.get(key)
    if selected and isinstance(selected,(tuple,list)) and len(selected)==2:
        try:
            parsed=pd.to_datetime(report_df[col],errors="coerce")
            start=pd.Timestamp(selected[0]); end=pd.Timestamp(selected[1])+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1)
            report_df=report_df[parsed.between(start,end,inclusive="both")]
            filters[col]=f"{selected[0]} → {selected[1]}"
        except Exception: pass

num_fields=st.session_state.get("dashboard_filter_num_fields", [])
for col in num_fields:
    key=f"dashboard_filter_value_{col}"; selected=st.session_state.get(key)
    if selected and isinstance(selected,(tuple,list)) and len(selected)==2:
        try:
            vals=pd.to_numeric(report_df[col],errors="coerce")
            report_df=report_df[vals.between(float(selected[0]),float(selected[1]),inclusive="both")]
            filters[col]=f"{selected[0]:g} → {selected[1]:g}"
        except Exception: pass

if report_df.empty:
    st.error("Current Dashboard filters return no rows. Broaden the filters before generating a report.")
    st.stop()

st.markdown(f"<div class='report-header'><h1>📄 Reports 2.0</h1><p>Professional reports from <b>{dataset_name}</b>, using the current dashboard filter context.</p></div>",unsafe_allow_html=True)

r=build_report_data(report_df)
cols=st.columns(5)
for c,label,value in zip(cols,["Rows","Columns","Completeness","Missing Cells","Duplicates"],[f"{r['rows']:,}",f"{r['columns']:,}",f"{r['completeness']:.1f}%",f"{r['missing_cells']:,}",f"{r['duplicate_rows']:,}"]):
    with c: st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>",unsafe_allow_html=True)

st.markdown("<div class='section-title'>🔎 Report Context</div>",unsafe_allow_html=True)
if filters:
    st.success(f"Report uses the currently filtered dataset: {len(report_df):,} rows.")
    st.dataframe(pd.DataFrame({"Filter":list(filters.keys()),"Selection":list(filters.values())}),use_container_width=True,hide_index=True)
else:
    st.info("No Dashboard filters are active. Report uses the complete active dataset.")

st.markdown("<div class='section-title'>💼 Executive Summary</div>",unsafe_allow_html=True)
for item in generate_executive_summary(report_df,r): st.markdown("• "+item)

story=st.session_state.get("dashboard_executive_story")
if story:
    st.markdown("<div class='section-title'>📖 Dashboard Data Story</div>",unsafe_allow_html=True)
    st.markdown(story)

st.markdown("<div class='section-title'>💡 Key Findings</div>",unsafe_allow_html=True)
for finding in generate_report_findings(report_df): st.info(finding)

saved=st.session_state.get("dashboard_saved_charts",[])
st.markdown("<div class='section-title'>📊 Dashboard Visualizations</div>",unsafe_allow_html=True)
if saved:
    rows=[]
    for item in saved:
        cfg=item.get("config",{})
        rows.append({"Title":item.get("title",cfg.get("title","Saved Chart")),"Section":item.get("section","Other"),"Chart Type":cfg.get("chart_type",cfg.get("type","")),"Category":cfg.get("x",cfg.get("category","")),"Metric":cfg.get("y",cfg.get("metric","")),"Aggregation":cfg.get("aggregation","")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else: st.caption("No saved dashboard charts are currently available.")

st.markdown("<div class='section-title'>⬇️ Generate Professional Report</div>",unsafe_allow_html=True)
if "report2_pdf" not in st.session_state: st.session_state.report2_pdf=None
if "report2_docx" not in st.session_state: st.session_state.report2_docx=None
if "report2_xlsx" not in st.session_state: st.session_state.report2_xlsx=None

c1,c2,c3=st.columns(3)
with c1:
    if st.button("📄 Generate PDF",type="primary",use_container_width=True):
        with st.spinner("Generating PDF..."): st.session_state.report2_pdf=generate_pdf_report(report_df,dataset_name,filters)
    if st.session_state.report2_pdf: st.download_button("⬇️ Download PDF",st.session_state.report2_pdf,"InsightAI_Analytics_Report.pdf","application/pdf",use_container_width=True)
with c2:
    if st.button("📝 Generate Word",type="primary",use_container_width=True):
        with st.spinner("Generating Word report..."): st.session_state.report2_docx=generate_docx_report(report_df,dataset_name,filters)
    if st.session_state.report2_docx: st.download_button("⬇️ Download Word",st.session_state.report2_docx,"InsightAI_Analytics_Report.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
with c3:
    if st.button("📊 Generate Excel",type="primary",use_container_width=True):
        with st.spinner("Generating Excel..."): st.session_state.report2_xlsx=generate_excel_report(report_df,dataset_name,filters)
    if st.session_state.report2_xlsx: st.download_button("⬇️ Download Excel",st.session_state.report2_xlsx,"InsightAI_Analytics_Report.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

st.divider(); st.caption("InsightAI • Analyze → Explain → Report")
