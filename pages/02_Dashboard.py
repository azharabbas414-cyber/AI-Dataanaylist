import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from core.analytics import analyze_dataset


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="InsightAI | Dashboard",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .dashboard-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(
            135deg,
            rgba(37, 99, 235, 0.14),
            rgba(99, 102, 241, 0.08)
        );
        border: 1px solid rgba(100, 116, 139, 0.18);
    }

    .dashboard-header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
    }

    .dashboard-header p {
        margin-top: 8px;
        color: #64748b;
        font-size: 15px;
    }

    .section-title {
        font-size: 21px;
        font-weight: 700;
        margin-top: 26px;
        margin-bottom: 12px;
    }

    .kpi-card {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        background: rgba(255, 255, 255, 0.03);
        min-height: 115px;
    }

    .kpi-label {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 8px;
    }

    .kpi-value {
        font-size: 27px;
        font-weight: 700;
    }

    .insight-card {
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        margin-bottom: 10px;
    }

    .small-muted {
        color: #64748b;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CHECK ACTIVE DATASET
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


# ============================================================
# ANALYSIS
# ============================================================

analysis = analyze_dataset(df)

classification = analysis.get("classification", {})

numeric_columns = classification.get("numeric", [])
categorical_columns = classification.get("categorical", [])
datetime_columns = classification.get("datetime", [])


# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="dashboard-header">
        <h1>📊 Analytics Dashboard</h1>
        <p>
            Interactive overview of
            <b>{st.session_state.get("active_dataset", "Active Dataset")}</b>
            using {len(df):,} rows and {len(df.columns):,} columns.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# KPI SECTION
# ============================================================

st.markdown('<div class="section-title">📌 Dataset Overview</div>', unsafe_allow_html=True)

total_cells = df.shape[0] * df.shape[1]
missing_cells = int(df.isna().sum().sum())

if total_cells > 0:
    completeness = ((total_cells - missing_cells) / total_cells) * 100
else:
    completeness = 100

duplicate_rows = int(df.duplicated().sum())

numeric_count = len(numeric_columns)
categorical_count = len(categorical_columns)

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Rows</div>
            <div class="kpi-value">{len(df):,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Columns</div>
            <div class="kpi-value">{len(df.columns):,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Numeric Fields</div>
            <div class="kpi-value">{numeric_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi4:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Category Fields</div>
            <div class="kpi-value">{categorical_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi5:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Completeness</div>
            <div class="kpi-value">{completeness:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi6:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Duplicates</div>
            <div class="kpi-value">{duplicate_rows:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DATASET SNAPSHOT
# ============================================================

st.markdown('<div class="section-title">🔎 Dataset Snapshot</div>', unsafe_allow_html=True)

snapshot_col1, snapshot_col2 = st.columns([1.5, 1])

with snapshot_col1:

    preview_columns = list(df.columns[:8])

    st.dataframe(
        df[preview_columns].head(10),
        use_container_width=True,
        hide_index=True,
    )

with snapshot_col2:

    structure_data = []

    for column in df.columns:
        structure_data.append(
            {
                "Column": column,
                "Type": str(df[column].dtype),
                "Missing": int(df[column].isna().sum()),
                "Unique": int(df[column].nunique(dropna=True)),
            }
        )

    structure_df = pd.DataFrame(structure_data)

    st.dataframe(
        structure_df,
        use_container_width=True,
        hide_index=True,
        height=330,
    )


# ============================================================
# PIE CHARTS
# ============================================================

st.markdown(
    '<div class="section-title">🥧 Composition Analysis</div>',
    unsafe_allow_html=True,
)

pie_col1, pie_col2 = st.columns(2)


# ------------------------------------------------------------
# PIE 1 — CATEGORY DISTRIBUTION
# ------------------------------------------------------------

with pie_col1:

    if categorical_columns:

        selected_category = st.selectbox(
            "Category",
            categorical_columns,
            key="dashboard_pie_category",
        )

        category_counts = (
            df[selected_category]
            .fillna("Missing")
            .astype(str)
            .value_counts()
            .reset_index()
        )

        category_counts.columns = ["Category", "Count"]

        # Keep pie charts readable
        if len(category_counts) > 8:

            top_values = category_counts.head(7).copy()

            other_count = category_counts.iloc[7:]["Count"].sum()

            if other_count > 0:
                top_values.loc[len(top_values)] = [
                    "Other",
                    other_count,
                ]

            category_counts = top_values

        fig = px.pie(
            category_counts,
            names="Category",
            values="Count",
            hole=0.42,
            title=f"Distribution of {selected_category}",
        )

        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=60, b=20),
            legend_title_text="",
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info(
            "No categorical columns are available for a distribution pie chart."
        )


# ------------------------------------------------------------
# PIE 2 — NUMERIC CONTRIBUTION BY CATEGORY
# ------------------------------------------------------------

with pie_col2:

    if categorical_columns and numeric_columns:

        selected_category_2 = st.selectbox(
            "Category for contribution",
            categorical_columns,
            key="dashboard_pie_category_2",
        )

        selected_metric = st.selectbox(
            "Numeric metric",
            numeric_columns,
            key="dashboard_pie_metric",
        )

        contribution_df = df[
            [selected_category_2, selected_metric]
        ].copy()

        contribution_df[selected_category_2] = (
            contribution_df[selected_category_2]
            .fillna("Missing")
            .astype(str)
        )

        contribution_df[selected_metric] = pd.to_numeric(
            contribution_df[selected_metric],
            errors="coerce",
        )

        contribution_df = contribution_df.dropna(
            subset=[selected_metric]
        )

        contribution_df = (
            contribution_df
            .groupby(selected_category_2, as_index=False)[selected_metric]
            .sum()
            .sort_values(selected_metric, ascending=False)
        )

        if not contribution_df.empty:

            if len(contribution_df) > 8:

                top_values = contribution_df.head(7).copy()

                other_value = contribution_df.iloc[7:][
                    selected_metric
                ].sum()

                if other_value != 0:

                    other_row = pd.DataFrame(
                        {
                            selected_category_2: ["Other"],
                            selected_metric: [other_value],
                        }
                    )

                    top_values = pd.concat(
                        [top_values, other_row],
                        ignore_index=True,
                    )

                contribution_df = top_values

            fig = px.pie(
                contribution_df,
                names=selected_category_2,
                values=selected_metric,
                hole=0.42,
                title=f"{selected_metric} Contribution by {selected_category_2}",
            )

            fig.update_layout(
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
                legend_title_text="",
            )

            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.info(
                "No valid numeric data is available for this contribution chart."
            )

    else:

        st.info(
            "A categorical and numeric column are required for contribution analysis."
        )


# ============================================================
# TREND ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">📈 Trend Analysis</div>',
    unsafe_allow_html=True,
)

if datetime_columns and numeric_columns:

    trend_date = st.selectbox(
        "Date / Time Field",
        datetime_columns,
        key="dashboard_trend_date",
    )

    trend_metric = st.selectbox(
        "Metric",
        numeric_columns,
        key="dashboard_trend_metric",
    )

    trend_df = df[[trend_date, trend_metric]].copy()

    trend_df[trend_date] = pd.to_datetime(
        trend_df[trend_date],
        errors="coerce",
    )

    trend_df[trend_metric] = pd.to_numeric(
        trend_df[trend_metric],
        errors="coerce",
    )

    trend_df = trend_df.dropna()

    if not trend_df.empty:

        trend_df = (
            trend_df
            .groupby(trend_date, as_index=False)[trend_metric]
            .sum()
            .sort_values(trend_date)
        )

        fig = px.line(
            trend_df,
            x=trend_date,
            y=trend_metric,
            markers=True,
            title=f"{trend_metric} Over Time",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info("The selected date and metric do not contain enough valid data.")

else:

    st.info(
        "A recognizable date/time column and numeric column are required for trend analysis."
    )


# ============================================================
# CATEGORY PERFORMANCE
# ============================================================

st.markdown(
    '<div class="section-title">📊 Category Performance</div>',
    unsafe_allow_html=True,
)

if categorical_columns and numeric_columns:

    category_col, metric_col = st.columns(2)

    with category_col:

        performance_category = st.selectbox(
            "Category",
            categorical_columns,
            key="dashboard_performance_category",
        )

    with metric_col:

        performance_metric = st.selectbox(
            "Metric",
            numeric_columns,
            key="dashboard_performance_metric",
        )

    performance_df = df[
        [performance_category, performance_metric]
    ].copy()

    performance_df[performance_category] = (
        performance_df[performance_category]
        .fillna("Missing")
        .astype(str)
    )

    performance_df[performance_metric] = pd.to_numeric(
        performance_df[performance_metric],
        errors="coerce",
    )

    performance_df = performance_df.dropna(
        subset=[performance_metric]
    )

    performance_df = (
        performance_df
        .groupby(performance_category, as_index=False)[performance_metric]
        .sum()
        .sort_values(performance_metric, ascending=False)
    )

    if not performance_df.empty:

        fig = px.bar(
            performance_df,
            x=performance_category,
            y=performance_metric,
            text_auto=".2s",
            title=f"{performance_metric} by {performance_category}",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

else:

    st.info(
        "Categorical and numeric fields are required for category performance."
    )


# ============================================================
# NUMERIC DISTRIBUTION
# ============================================================

st.markdown(
    '<div class="section-title">📦 Numeric Distribution</div>',
    unsafe_allow_html=True,
)

if numeric_columns:

    distribution_metric = st.selectbox(
        "Select numeric field",
        numeric_columns,
        key="dashboard_distribution_metric",
    )

    distribution_values = pd.to_numeric(
        df[distribution_metric],
        errors="coerce",
    ).dropna()

    if not distribution_values.empty:

        distribution_df = pd.DataFrame(
            {
                distribution_metric: distribution_values
            }
        )

        fig = px.histogram(
            distribution_df,
            x=distribution_metric,
            marginal="box",
            nbins=30,
            title=f"Distribution of {distribution_metric}",
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.info("No valid numeric values available.")

else:

    st.info("No numeric columns detected.")


# ============================================================
# CORRELATION HEATMAP
# ============================================================

st.markdown(
    '<div class="section-title">🔥 Correlation Analysis</div>',
    unsafe_allow_html=True,
)

if len(numeric_columns) >= 2:

    correlation_df = df[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    corr_matrix = correlation_df.corr()

    fig = px.imshow(
        corr_matrix,
        text_auto=".2f",
        aspect="auto",
        title="Numeric Correlation Matrix",
    )

    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

else:

    st.info(
        "At least two numeric columns are required for correlation analysis."
    )


# ============================================================
# ANOMALY SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">🚨 Anomaly Summary</div>',
    unsafe_allow_html=True,
)

try:

    outliers = analysis.get("outliers", {})

    if isinstance(outliers, dict) and outliers:

        anomaly_rows = []

        for column, values in outliers.items():

            if isinstance(values, pd.DataFrame):

                count = len(values)

            elif isinstance(values, (list, tuple, np.ndarray, pd.Series)):

                count = len(values)

            elif isinstance(values, int):

                count = values

            else:

                count = 0

            anomaly_rows.append(
                {
                    "Column": column,
                    "Anomalies": count,
                }
            )

        anomaly_df = pd.DataFrame(anomaly_rows)

        if not anomaly_df.empty:

            anomaly_df = anomaly_df.sort_values(
                "Anomalies",
                ascending=False,
            )

            fig = px.bar(
                anomaly_df,
                x="Column",
                y="Anomalies",
                text_auto=True,
                title="Potential Outliers by Column",
            )

            fig.update_layout(
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.success("No significant anomalies detected.")

    else:

        st.success("No significant anomalies detected.")

except Exception:

    st.info(
        "Anomaly information is not available for this dataset."
    )


# ============================================================
# AUTOMATIC INSIGHTS
# ============================================================

st.markdown(
    '<div class="section-title">💡 Automatic Insights</div>',
    unsafe_allow_html=True,
)

findings = analysis.get("findings", [])

if findings:

    for finding in findings[:8]:

        st.markdown(
            f"""
            <div class="insight-card">
                💡 {finding}
            </div>
            """,
            unsafe_allow_html=True,
        )

else:

    # Generate a few generic insights when the analytics engine
    # does not return findings.

    if duplicate_rows > 0:

        st.markdown(
            f"""
            <div class="insight-card">
                ⚠️ The dataset contains {duplicate_rows:,} duplicate rows.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if missing_cells > 0:

        st.markdown(
            f"""
            <div class="insight-card">
                ⚠️ The dataset contains {missing_cells:,} missing cells.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not duplicate_rows and not missing_cells:

        st.markdown(
            """
            <div class="insight-card">
                ✅ No duplicate rows or missing cells were detected.
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# DATA STRUCTURE
# ============================================================

st.markdown(
    '<div class="section-title">🧬 Data Structure</div>',
    unsafe_allow_html=True,
)

structure_cols = st.columns(3)

with structure_cols[0]:

    st.metric(
        "Numeric Fields",
        len(numeric_columns),
    )

    if numeric_columns:
        st.caption(", ".join(numeric_columns[:10]))

with structure_cols[1]:

    st.metric(
        "Categorical Fields",
        len(categorical_columns),
    )

    if categorical_columns:
        st.caption(", ".join(categorical_columns[:10]))

with structure_cols[2]:

    st.metric(
        "Date / Time Fields",
        len(datetime_columns),
    )

    if datetime_columns:
        st.caption(", ".join(datetime_columns[:10]))


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InsightAI • AI-Powered Data Analytics & Decision Intelligence Platform"
)
