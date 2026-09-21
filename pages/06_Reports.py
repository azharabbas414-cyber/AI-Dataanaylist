import streamlit as st

from core.analytics import analyze_dataset
from core.reporting import (
    build_report_data,
    generate_executive_summary,
    generate_html_report,
)


st.set_page_config(
    page_title="InsightAI - Reports",
    page_icon="📄",
    layout="wide",
)


# ---------------------------------------------------------
# ACTIVE DATASET CHECK
# ---------------------------------------------------------

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):

    st.warning(
        "No active dataset is selected."
    )

    st.info(
        "Return to Home and select an existing "
        "GitHub dataset or upload a new dataset."
    )

    if st.button("🏠 Go to Home"):
        st.switch_page("streamlitapp.py")

    st.stop()


# ---------------------------------------------------------
# ACTIVE DATASET
# ---------------------------------------------------------

df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Dataset"
)

dataset_source = st.session_state.get(
    "active_source",
    "Unknown"
)


# ---------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------

analysis = analyze_dataset(df)

report_data = build_report_data(
    df,
    dataset_name,
    analysis,
)

summary = generate_executive_summary(
    report_data
)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("📄 Reports")

st.caption(
    "Generate a professional analytics report from "
    "your active dataset."
)


st.info(
    f"**Dataset:** {dataset_name}  |  "
    f"**Source:** {dataset_source}"
)


# ---------------------------------------------------------
# REPORT SUMMARY
# ---------------------------------------------------------

st.subheader("📊 Report Overview")

health = analysis["health"]

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Rows",
        f"{health['rows']:,}"
    )

with col2:

    st.metric(
        "Columns",
        f"{health['columns']:,}"
    )

with col3:

    st.metric(
        "Completeness",
        f"{health['completeness']:.1f}%"
    )

with col4:

    st.metric(
        "Quality Score",
        f"{health['quality_score']:.0f}/100"
    )


st.divider()


# ---------------------------------------------------------
# EXECUTIVE SUMMARY
# ---------------------------------------------------------

st.subheader("🧠 Executive Summary")

st.write(summary)


# ---------------------------------------------------------
# REPORT CONTENT
# ---------------------------------------------------------

st.subheader("📋 Report Contents")

content_col1, content_col2 = st.columns(2)

with content_col1:

    st.markdown(
        """
        **Included in the report**

        ✓ Executive Summary  
        ✓ Dataset Overview  
        ✓ Data Quality  
        ✓ Key Findings  
        ✓ Numeric Statistics  
        ✓ Categorical Analysis  
        """
    )

with content_col2:

    st.markdown(
        """
        **Advanced Analysis**

        ✓ Potential Outliers  
        ✓ Correlation Analysis  
        ✓ Dataset Structure  
        ✓ Data Completeness  
        ✓ Duplicate Analysis  
        ✓ Analytical Summary  
        """
    )


st.divider()


# ---------------------------------------------------------
# KEY FINDINGS PREVIEW
# ---------------------------------------------------------

st.subheader("🔎 Key Findings Preview")

findings = analysis["findings"]

if findings:

    for finding in findings:

        st.info(
            f"• {finding}"
        )

else:

    st.info(
        "No automatic findings were generated."
    )


st.divider()


# ---------------------------------------------------------
# GENERATE REPORT
# ---------------------------------------------------------

st.subheader("📄 Generate Report")

st.write(
    "Generate a complete HTML report containing "
    "the analytical results above."
)


if st.button(
    "📄 Generate Full Report",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "Generating InsightAI report..."
    ):

        report_html = generate_html_report(
            report_data
        )

        st.session_state.generated_report = (
            report_html
        )

        st.success(
            "Report generated successfully."
        )


# ---------------------------------------------------------
# DOWNLOAD REPORT
# ---------------------------------------------------------

if (
    "generated_report"
    in st.session_state
):

    st.divider()

    st.subheader(
        "⬇️ Download Report"
    )

    report_html = (
        st.session_state.generated_report
    )

    st.download_button(
        label="⬇️ Download HTML Report",
        data=report_html,
        file_name="insightai_report.html",
        mime="text/html",
        use_container_width=True,
    )

    st.success(
        "Your report is ready. "
        "Open the downloaded HTML file in any browser."
    )


st.divider()


# ---------------------------------------------------------
# REPORT PREVIEW
# ---------------------------------------------------------

if (
    "generated_report"
    in st.session_state
):

    st.subheader(
        "👁️ Report Preview"
    )

    st.components.v1.html(
        st.session_state.generated_report,
        height=900,
        scrolling=True,
    )


st.divider()

st.caption(
    f"InsightAI • Reports • {dataset_name}"
)
