import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.analytics import analyze_dataset


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="InsightAI - Dashboard",
    page_icon="📈",
    layout="wide",
)


# =========================================================
# ACTIVE DATASET CHECK
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


# =========================================================
# DATA
# =========================================================

df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Dataset",
)

dataset_source = st.session_state.get(
    "active_source",
    "Unknown",
)


# =========================================================
# ANALYTICS ENGINE
# =========================================================

analysis = analyze_dataset(df)

health = analysis["health"]

classification = analysis[
    "classification"
]

numeric_summary = analysis[
    "numeric_summary"
]

categorical_summary = analysis[
    "categorical_summary"
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
# CUSTOM CSS
# =========================================================

st.markdown(
    """
<style>

.dashboard-header {
    padding: 28px 32px;
    border-radius: 18px;
    background: linear-gradient(
        135deg,
        #eef2ff,
        #f8fafc
    );
    border: 1px solid #e2e8f0;
    margin-bottom: 25px;
}

.dashboard-title {
    font-size: 38px;
    font-weight: 800;
    color: #1e293b;
}

.dashboard-subtitle {
    color: #64748b;
    font-size: 15px;
    margin-top: 5px;
}

.kpi-card {
    padding: 20px;
    border-radius: 16px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    min-height: 120px;
}

.kpi-label {
    color: #64748b;
    font-size: 13px;
    font-weight: 600;
}

.kpi-value {
    color: #0f172a;
    font-size: 30px;
    font-weight: 800;
    margin-top: 8px;
}

.section-card {
    padding: 20px;
    border-radius: 16px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
}

.insight-card {
    padding: 16px 20px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    margin-bottom: 10px;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    f"""
<div class="dashboard-header">

<div class="dashboard-title">
📈 Executive Dashboard
</div>

<div class="dashboard-subtitle">
Automated visual analytics for
<strong>{dataset_name}</strong>
</div>

<div class="dashboard-subtitle">
Source: {dataset_source}
</div>

</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# KPI CARDS
# =========================================================

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)


with kpi1:

    st.markdown(
        f"""
<div class="kpi-card">

<div class="kpi-label">
TOTAL RECORDS
</div>

<div class="kpi-value">
{health["rows"]:,}
</div>

</div>
""",
        unsafe_allow_html=True,
    )


with kpi2:

    st.markdown(
        f"""
<div class="kpi-card">

<div class="kpi-label">
COLUMNS
</div>

<div class="kpi-value">
{health["columns"]:,}
</div>

</div>
""",
        unsafe_allow_html=True,
    )


with kpi3:

    st.markdown(
        f"""
<div class="kpi-card">

<div class="kpi-label">
DATA COMPLETENESS
</div>

<div class="kpi-value">
{health["completeness"]:.1f}%
</div>

</div>
""",
        unsafe_allow_html=True,
    )


with kpi4:

    st.markdown(
        f"""
<div class="kpi-card">

<div class="kpi-label">
MISSING VALUES
</div>

<div class="kpi-value">
{health["missing_values"]:,}
</div>

</div>
""",
        unsafe_allow_html=True,
    )


with kpi5:

    st.markdown(
        f"""
<div class="kpi-card">

<div class="kpi-label">
QUALITY SCORE
</div>

<div class="kpi-value">
{health["quality_score"]:.0f}/100
</div>

</div>
""",
        unsafe_allow_html=True,
    )


st.write("")


# =========================================================
# DATASET SNAPSHOT
# =========================================================

st.subheader(
    "📊 Dataset Snapshot"
)

snapshot_col1, snapshot_col2, snapshot_col3 = (
    st.columns(3)
)


with snapshot_col1:

    st.metric(
        "Numeric Fields",
        len(
            classification[
                "numeric"
            ]
        ),
    )


with snapshot_col2:

    st.metric(
        "Categorical Fields",
        len(
            classification[
                "categorical"
            ]
        ),
    )


with snapshot_col3:

    st.metric(
        "Date Fields",
        len(
            classification[
                "datetime"
            ]
        ),
    )


# =========================================================
# TREND ANALYSIS
# =========================================================

st.divider()

st.subheader(
    "📈 Trend Analysis"
)

datetime_columns = list(
    classification["datetime"]
)

numeric_columns = list(
    classification["numeric"]
)


if datetime_columns and numeric_columns:

    trend_col1, trend_col2 = st.columns(
        [1, 3]
    )

    with trend_col1:

        selected_date = st.selectbox(
            "Date / Time",
            datetime_columns,
            key="dashboard_date_column",
        )

        selected_metric = st.selectbox(
            "Metric",
            numeric_columns,
            key="dashboard_trend_metric",
        )

    with trend_col2:

        trend_df = df[
            [
                selected_date,
                selected_metric,
            ]
        ].copy()

        trend_df[selected_date] = (
            pd.to_datetime(
                trend_df[selected_date],
                errors="coerce",
            )
        )

        trend_df[selected_metric] = (
            pd.to_numeric(
                trend_df[selected_metric],
                errors="coerce",
            )
        )

        trend_df = trend_df.dropna()

        if not trend_df.empty:

            trend_df = (
                trend_df
                .groupby(
                    selected_date,
                    as_index=False,
                )[selected_metric]
                .mean()
                .sort_values(
                    selected_date
                )
            )

            fig = px.line(
                trend_df,
                x=selected_date,
                y=selected_metric,
                markers=True,
                title=(
                    f"{selected_metric} over time"
                ),
            )

            fig.update_layout(
                height=430,
                margin=dict(
                    l=20,
                    r=20,
                    t=60,
                    b=20,
                ),
                hovermode="x unified",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.info(
                "No valid time-series data "
                "was found."
            )

else:

    st.info(
        "A date/time column and at least one "
        "numeric column are required for "
        "trend analysis."
    )


# =========================================================
# CATEGORY ANALYSIS
# =========================================================

st.divider()

st.subheader(
    "🏆 Category Performance"
)

categorical_columns = list(
    classification[
        "categorical"
    ]
)

if categorical_columns and numeric_columns:

    cat_col1, cat_col2 = st.columns(2)

    with cat_col1:

        selected_category_1 = st.selectbox(
            "Category",
            categorical_columns,
            key="dashboard_category_1",
        )

        selected_metric_1 = st.selectbox(
            "Metric",
            numeric_columns,
            key="dashboard_category_metric_1",
        )

        category_df_1 = df[
            [
                selected_category_1,
                selected_metric_1,
            ]
        ].copy()

        category_df_1[
            selected_metric_1
        ] = pd.to_numeric(
            category_df_1[
                selected_metric_1
            ],
            errors="coerce",
        )

        category_df_1 = (
            category_df_1
            .dropna()
            .groupby(
                selected_category_1,
                as_index=False,
            )[selected_metric_1]
            .sum()
            .sort_values(
                selected_metric_1,
                ascending=False,
            )
            .head(15)
        )

        fig1 = px.bar(
            category_df_1,
            x=selected_category_1,
            y=selected_metric_1,
            text_auto=".2s",
            title=(
                f"{selected_metric_1} by "
                f"{selected_category_1}"
            ),
        )

        fig1.update_layout(
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            fig1,
            use_container_width=True,
        )

    with cat_col2:

        selected_category_2 = st.selectbox(
            "Second Category",
            categorical_columns,
            index=(
                1
                if len(categorical_columns) > 1
                else 0
            ),
            key="dashboard_category_2",
        )

        selected_metric_2 = st.selectbox(
            "Metric",
            numeric_columns,
            index=(
                1
                if len(numeric_columns) > 1
                else 0
            ),
            key="dashboard_category_metric_2",
        )

        category_df_2 = df[
            [
                selected_category_2,
                selected_metric_2,
            ]
        ].copy()

        category_df_2[
            selected_metric_2
        ] = pd.to_numeric(
            category_df_2[
                selected_metric_2
            ],
            errors="coerce",
        )

        category_df_2 = (
            category_df_2
            .dropna()
            .groupby(
                selected_category_2,
                as_index=False,
            )[selected_metric_2]
            .sum()
            .sort_values(
                selected_metric_2,
                ascending=False,
            )
            .head(15)
        )

        fig2 = px.bar(
            category_df_2,
            x=selected_category_2,
            y=selected_metric_2,
            text_auto=".2s",
            title=(
                f"{selected_metric_2} by "
                f"{selected_category_2}"
            ),
        )

        fig2.update_layout(
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
            ),
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )

else:

    st.info(
        "Categorical and numeric columns are "
        "required for category analysis."
    )


# =========================================================
# NUMERIC DISTRIBUTION
# =========================================================

st.divider()

st.subheader(
    "📊 Numeric Distribution"
)

if numeric_columns:

    distribution_col1, distribution_col2 = (
        st.columns([1, 3])
    )

    with distribution_col1:

        distribution_metric = st.selectbox(
            "Select numeric field",
            numeric_columns,
            key="dashboard_distribution",
        )

    with distribution_col2:

        distribution_data = pd.to_numeric(
            df[distribution_metric],
            errors="coerce",
        ).dropna()

        fig3 = px.histogram(
            distribution_data,
            x=distribution_metric,
            nbins=25,
            marginal="box",
            title=(
                f"Distribution of "
                f"{distribution_metric}"
            ),
        )

        fig3.update_layout(
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=60,
                b=20,
        ),
        )

        st.plotly_chart(
            fig3,
            use_container_width=True,
        )

else:

    st.info(
        "No numeric columns available."
    )


# =========================================================
# CORRELATION ANALYSIS
# =========================================================

st.divider()

st.subheader(
    "🔗 Relationships Between Variables"
)

if len(numeric_columns) >= 2:

    correlation_matrix = (
        df[numeric_columns]
        .corr()
    )

    fig4 = px.imshow(
        correlation_matrix,
        text_auto=".2f",
        aspect="auto",
        title="Correlation Matrix",
    )

    fig4.update_layout(
        height=600,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
    )

    st.plotly_chart(
        fig4,
        use_container_width=True,
    )

else:

    st.info(
        "At least two numeric columns are "
        "required for correlation analysis."
    )


# =========================================================
# ANOMALY SUMMARY
# =========================================================

st.divider()

st.subheader(
    "🚨 Anomaly Summary"
)

if outliers.empty:

    st.info(
        "No numeric fields are available "
        "for outlier analysis."
    )

else:

    significant_outliers = (
        outliers[
            outliers["outliers"] > 0
        ]
        .copy()
    )

    if significant_outliers.empty:

        st.success(
            "✅ No statistical outliers were detected."
        )

    else:

        anomaly_col1, anomaly_col2 = (
            st.columns([1, 2])
        )

        with anomaly_col1:

            total_outliers = int(
                significant_outliers[
                    "outliers"
                ].sum()
            )

            st.metric(
                "Potential Outliers",
                f"{total_outliers:,}",
            )

            st.dataframe(
                significant_outliers,
                use_container_width=True,
                hide_index=True,
            )

        with anomaly_col2:

            fig5 = px.bar(
                significant_outliers,
                x="column",
                y="outliers",
                text="outliers",
                title="Potential Outliers by Field",
            )

            fig5.update_layout(
                height=400,
                margin=dict(
                    l=20,
                    r=20,
                    t=60,
                    b=20,
                ),
            )

            st.plotly_chart(
                fig5,
                use_container_width=True,
            )


# =========================================================
# STRONGEST RELATIONSHIPS
# =========================================================

st.divider()

st.subheader(
    "🔗 Strongest Relationships"
)

if correlations.empty:

    st.info(
        "No correlation pairs are available."
    )

else:

    top_correlations = correlations.head(
        10
    ).copy()

    st.dataframe(
        top_correlations,
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# AUTOMATIC INSIGHTS
# =========================================================

st.divider()

st.subheader(
    "🧠 Automatic Insights"
)

if findings:

    for finding in findings:

        st.markdown(
            f"""
<div class="insight-card">

🔎 {finding}

</div>
""",
            unsafe_allow_html=True,
        )

else:

    st.info(
        "No automatic insights were generated."
    )


# =========================================================
# DATA STRUCTURE
# =========================================================

st.divider()

st.subheader(
    "🧩 Data Structure"
)

structure_col1, structure_col2, structure_col3 = (
    st.columns(3)
)


with structure_col1:

    st.markdown(
        "### 🔢 Numeric Fields"
    )

    if numeric_columns:

        for column in numeric_columns:

            st.write(
                f"• {column}"
            )

    else:

        st.caption(
            "None detected."
        )


with structure_col2:

    st.markdown(
        "### 🔤 Categorical Fields"
    )

    if categorical_columns:

        for column in categorical_columns:

            st.write(
                f"• {column}"
            )

    else:

        st.caption(
            "None detected."
        )


with structure_col3:

    st.markdown(
        "### 📅 Date Fields"
    )

    if datetime_columns:

        for column in datetime_columns:

            st.write(
                f"• {column}"
            )

    else:

        st.caption(
            "None detected."
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    f"InsightAI • Executive Dashboard • "
    f"{dataset_name}"
)
