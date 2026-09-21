import streamlit as st

from core.reporting import (
    build_report_data,
    generate_executive_summary,
    generate_report_findings,
    generate_pdf_report,
    generate_docx_report,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="InsightAI | Reports",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .report-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(
            135deg,
            rgba(16, 185, 129, 0.12),
            rgba(59, 130, 246, 0.08)
        );
        border: 1px solid rgba(100, 116, 139, 0.18);
    }

    .report-header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
    }

    .report-header p {
        margin-top: 8px;
        color: #64748b;
    }

    .section-title {
        font-size: 21px;
        font-weight: 700;
        margin-top: 26px;
        margin-bottom: 12px;
    }

    .metric-card {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        min-height: 105px;
    }

    .metric-label {
        color: #64748b;
        font-size: 13px;
    }

    .metric-value {
        font-size: 27px;
        font-weight: 700;
        margin-top: 6px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ACTIVE DATASET
# ============================================================

if "active_dataframe" not in st.session_state:
    st.session_state.active_dataframe = None


if st.session_state.active_dataframe is None:

    st.warning(
        "No active dataset found. Please select or upload a dataset from the Home page."
    )

    if st.button("🏠 Go to Home", type="primary"):
        st.switch_page("streamlitapp.py")

    st.stop()


df = st.session_state.active_dataframe.copy()

if df.empty:

    st.warning("The active dataset is empty.")

    st.stop()


dataset_name = st.session_state.get(
    "active_dataset",
    "InsightAI Dataset",
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="report-header">
        <h1>📄 Reports</h1>
        <p>
            Generate professional analytics reports from
            <b>{dataset_name}</b>.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# REPORT DATA
# ============================================================

report_data = build_report_data(df)


# ============================================================
# KPI SECTION
# ============================================================

st.markdown(
    '<div class="section-title">📌 Report Summary</div>',
    unsafe_allow_html=True,
)


c1, c2, c3, c4, c5 = st.columns(5)


with c1:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Rows</div>
            <div class="metric-value">
                {report_data["rows"]:,}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with c2:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Columns</div>
            <div class="metric-value">
                {report_data["columns"]:,}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with c3:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Completeness</div>
            <div class="metric-value">
                {report_data["completeness"]:.1f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with c4:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Missing Cells</div>
            <div class="metric-value">
                {report_data["missing_cells"]:,}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with c5:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Duplicates</div>
            <div class="metric-value">
                {report_data["duplicate_rows"]:,}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">💼 Executive Summary</div>',
    unsafe_allow_html=True,
)


summary = generate_executive_summary(
    df,
    report_data,
)


for item in summary:

    st.markdown(
        f"• {item}"
    )


# ============================================================
# FINDINGS
# ============================================================

st.markdown(
    '<div class="section-title">💡 Key Findings</div>',
    unsafe_allow_html=True,
)


findings = generate_report_findings(df)


for finding in findings:

    st.info(finding)


# ============================================================
# REPORT CONTENT PREVIEW
# ============================================================

st.markdown(
    '<div class="section-title">📋 Report Contents</div>',
    unsafe_allow_html=True,
)


contents = [
    "Executive overview",
    "Dataset KPIs",
    "Data structure",
    "Data completeness",
    "Missing-value analysis",
    "Duplicate-row analysis",
    "Numeric statistics",
    "Categorical analysis",
    "Statistical outlier findings",
    "Correlation analysis",
    "Automatic findings",
]


for item in contents:

    st.markdown(
        f"✓ {item}"
    )


# ============================================================
# DOWNLOAD REPORTS
# ============================================================

st.markdown(
    '<div class="section-title">⬇️ Generate Report</div>',
    unsafe_allow_html=True,
)


report_col1, report_col2 = st.columns(2)


# ------------------------------------------------------------
# PDF
# ------------------------------------------------------------

with report_col1:

    st.markdown("### 📄 PDF Report")

    if st.button(
        "Generate PDF Report",
        type="primary",
        use_container_width=True,
        key="generate_pdf",
    ):

        with st.spinner("Generating PDF report..."):

            try:

                pdf_bytes = generate_pdf_report(
                    df,
                    dataset_name,
                )

                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name="InsightAI_Analytics_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_pdf",
                )

                st.success(
                    "PDF report generated successfully."
                )

            except Exception as exc:

                st.error(
                    f"PDF generation failed: {exc}"
                )


# ------------------------------------------------------------
# DOCX
# ------------------------------------------------------------

with report_col2:

    st.markdown("### 📝 Word Report")

    if st.button(
        "Generate Word Report",
        type="primary",
        use_container_width=True,
        key="generate_docx",
    ):

        with st.spinner("Generating Word report..."):

            try:

                docx_bytes = generate_docx_report(
                    df,
                    dataset_name,
                )

                st.download_button(
                    "⬇️ Download Word Report",
                    data=docx_bytes,
                    file_name="InsightAI_Analytics_Report.docx",
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.wordprocessingml.document"
                    ),
                    use_container_width=True,
                    key="download_docx",
                )

                st.success(
                    "Word report generated successfully."
                )

            except Exception as exc:

                st.error(
                    f"Word report generation failed: {exc}"
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InsightAI • AI-Powered Data Analytics & Decision Intelligence Platform"
)
