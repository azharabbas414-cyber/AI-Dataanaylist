import streamlit as st
import plotly.express as px

from core.analytics import analyze_dataset


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="InsightAI - Dashboard",
    page_icon="📈",
    layout="wide",
)


# =========================================================
# ACTIVE DATASET
# =========================================================

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):

    st.warning(
        "No active dataset is selected."
    )

    st.info(
        "Return to Home and select or upload a dataset."
    )

    if st.button("🏠 Go to Home"):

        st.switch_page(
            "streamlitapp.py"
        )

    st.stop()


df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Dataset"
)


# =========================================================
# ANALYZE
# =========================================================

analysis = analyze_dataset(df)

health = analysis["health"]

classification = analysis[
    "classification"
]

numeric_summary = analysis[
    "numeric_summary"
]

outliers = analysis[
    "outliers"
]

correlations = analysis[
    "correlations"
]

findings = analysis[
    "findings"
]


# =========================================================
# HEADER
# =========================================================

st.title("📈 InsightAI Dashboard")

st.caption(
    f"Automated analytics for **{dataset_name}**"
)


# =========================================================
# KPI ROW
# =========================================================

col1, col2, col3, col4, col5 = st.columns(5)

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
        "Duplicates",
        f"{health['duplicate_rows']:,}"
    )

with col5:

    st.metric(
        "Quality Score",
        f"{health['quality_score']:.0f}/100"
    )


st.divider()


# =========================================================
# AUTOMATIC INSIGHTS
# =========================================================

st.subheader("🧠 Automatic Insights")

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


# =========================================================
# NUMERIC OVERVIEW
# =========================================================

st.subheader("📊 Numeric Overview")

if numeric_summary.empty:

    st.info(
        "No numeric columns detected."
    )

else:

    display_summary = numeric_summary.copy()

    st.dataframe(
        display_summary,
        use_container_width=True,
    )


# =========================================================
# OUTLIERS
# =========================================================

st.divider()

st.subheader("🚨 Outlier Analysis")

if outliers.empty:

    st.info(
        "No numeric columns available for outlier analysis."
    )

else:

    significant_outliers = outliers[
        outliers["outliers"] > 0
    ].copy()

    if significant_outliers.empty:

        st.success(
            "No significant outliers detected."
        )

    else:

        st.dataframe(
            significant_outliers,
            use_container_width=True,
        )

        fig = px.bar(
            significant_outliers,
            x="column",
            y="outliers",
            text="outliers",
            title="Potential Outliers by Column",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# CORRELATION
# =========================================================

st.divider()

st.subheader("🔗 Strongest Relationships")

if correlations.empty:

    st.info(
        "At least two numeric columns are required "
        "for correlation analysis."
    )

else:

    st.dataframe(
        correlations.head(10),
        use_container_width=True,
    )

    correlation_matrix = df[
        classification["numeric"]
    ].corr()

    if not correlation_matrix.empty:

        fig = px.imshow(
            correlation_matrix,
            text_auto=True,
            aspect="auto",
            title="Correlation Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# DATASET CLASSIFICATION
# =========================================================

st.divider()

st.subheader("🔎 Dataset Structure")

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Numeric Fields",
        len(
            classification["numeric"]
        )
    )

    if classification["numeric"]:

        for column in classification["numeric"]:

            st.caption(
                f"• {column}"
            )

with col2:

    st.metric(
        "Categorical Fields",
        len(
            classification["categorical"]
        )
    )

    if classification["categorical"]:

        for column in classification["categorical"]:

            st.caption(
                f"• {column}"
            )

with col3:

    st.metric(
        "Date Fields",
        len(
            classification["datetime"]
        )
    )

    if classification["datetime"]:

        for column in classification["datetime"]:

            st.caption(
                f"• {column}"
            )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "InsightAI • Automated Analytics Engine"
)
