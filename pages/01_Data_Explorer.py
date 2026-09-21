import streamlit as st
import pandas as pd
import plotly.express as px


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="InsightAI - Data Explorer",
    page_icon="📊",
    layout="wide",
)


# =========================================================
# CHECK ACTIVE DATASET
# =========================================================

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):

    st.warning(
        "No active dataset is selected."
    )

    st.info(
        "Please return to Home and select an existing "
        "GitHub dataset or upload a new dataset."
    )

    if st.button("🏠 Go to Home"):

        st.switch_page(
            "streamlitapp.py"
        )

    st.stop()


# =========================================================
# ACTIVE DATASET
# =========================================================

df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Unknown Dataset"
)

dataset_source = st.session_state.get(
    "active_source",
    "Unknown Source"
)


# =========================================================
# HEADER
# =========================================================

st.title("📊 Data Explorer")

st.caption(
    "Explore, understand and profile your active dataset."
)


# =========================================================
# DATASET INFORMATION
# =========================================================

st.info(
    f"**Dataset:** {dataset_name}  |  "
    f"**Source:** {dataset_source}"
)


# =========================================================
# KPI CARDS
# =========================================================

total_rows = len(df)

total_columns = len(df.columns)

missing_values = int(
    df.isna().sum().sum()
)

duplicate_rows = int(
    df.duplicated().sum()
)

numeric_columns = len(
    df.select_dtypes(include="number").columns
)

categorical_columns = len(
    df.select_dtypes(exclude="number").columns
)


col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:

    st.metric(
        "Rows",
        f"{total_rows:,}"
    )

with col2:

    st.metric(
        "Columns",
        f"{total_columns:,}"
    )

with col3:

    st.metric(
        "Missing Values",
        f"{missing_values:,}"
    )

with col4:

    st.metric(
        "Duplicate Rows",
        f"{duplicate_rows:,}"
    )

with col5:

    st.metric(
        "Numeric Columns",
        f"{numeric_columns:,}"
    )

with col6:

    st.metric(
        "Categorical Columns",
        f"{categorical_columns:,}"
    )


st.divider()


# =========================================================
# TABS
# =========================================================

tab_preview, tab_quality, tab_statistics, tab_visual, tab_correlation = st.tabs(
    [
        "📋 Data Preview",
        "🔍 Data Quality",
        "📊 Statistics",
        "📈 Visualization",
        "🔗 Correlations",
    ]
)


# =========================================================
# TAB 1 - DATA PREVIEW
# =========================================================

with tab_preview:

    st.subheader("Dataset Preview")

    st.dataframe(
        df,
        use_container_width=True,
        height=500,
    )

    st.divider()

    st.subheader("Column Information")

    column_information = pd.DataFrame(
        {
            "Column": df.columns,
            "Data Type": [
                str(df[column].dtype)
                for column in df.columns
            ],
            "Non-Null": [
                int(df[column].notna().sum())
                for column in df.columns
            ],
            "Missing": [
                int(df[column].isna().sum())
                for column in df.columns
            ],
            "Missing %": [
                round(
                    df[column].isna().mean() * 100,
                    2,
                )
                for column in df.columns
            ],
            "Unique Values": [
                int(df[column].nunique(dropna=True))
                for column in df.columns
            ],
        }
    )

    st.dataframe(
        column_information,
        use_container_width=True,
    )


# =========================================================
# TAB 2 - DATA QUALITY
# =========================================================

with tab_quality:

    st.subheader("🔍 Data Quality Analysis")

    quality = pd.DataFrame(
        {
            "Column": df.columns,
            "Data Type": [
                str(df[column].dtype)
                for column in df.columns
            ],
            "Missing": [
                int(df[column].isna().sum())
                for column in df.columns
            ],
            "Missing %": [
                round(
                    df[column].isna().mean() * 100,
                    2,
                )
                for column in df.columns
            ],
            "Unique": [
                int(df[column].nunique(dropna=True))
                for column in df.columns
            ],
        }
    )

    st.dataframe(
        quality,
        use_container_width=True,
    )

    # -----------------------------------------------------
    # Missing values chart
    # -----------------------------------------------------

    missing_data = quality[
        quality["Missing"] > 0
    ].copy()

    if not missing_data.empty:

        st.subheader("Missing Values")

        fig = px.bar(
            missing_data,
            x="Column",
            y="Missing",
            text="Missing",
            title="Missing Values by Column",
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:

        st.success(
            "✅ No missing values detected."
        )


    # -----------------------------------------------------
    # Duplicate rows
    # -----------------------------------------------------

    st.subheader("Duplicate Records")

    if duplicate_rows == 0:

        st.success(
            "✅ No duplicate rows detected."
        )

    else:

        st.warning(
            f"{duplicate_rows:,} duplicate rows detected."
        )


# =========================================================
# TAB 3 - STATISTICS
# =========================================================

with tab_statistics:

    st.subheader("📊 Statistical Summary")

    numeric_df = df.select_dtypes(
        include="number"
    )

    if numeric_df.empty:

        st.info(
            "No numeric columns were detected."
        )

    else:

        statistics = numeric_df.describe().T

        statistics["median"] = (
            numeric_df.median()
        )

        statistics["missing"] = (
            numeric_df.isna().sum()
        )

        statistics = statistics[
            [
                "count",
                "mean",
                "std",
                "min",
                "25%",
                "50%",
                "median",
                "75%",
                "max",
                "missing",
            ]
        ]

        st.dataframe(
            statistics,
            use_container_width=True,
        )


    # -----------------------------------------------------
    # Categorical analysis
    # -----------------------------------------------------

    categorical_columns_list = list(
        df.select_dtypes(
            exclude="number"
        ).columns
    )

    if categorical_columns_list:

        st.divider()

        st.subheader(
            "🔤 Categorical Analysis"
        )

        selected_category = st.selectbox(
            "Select a categorical column",
            categorical_columns_list,
        )

        value_counts = (
            df[selected_category]
            .value_counts(
                dropna=False
            )
            .head(20)
            .reset_index()
        )

        value_counts.columns = [
            selected_category,
            "Count",
        ]

        st.dataframe(
            value_counts,
            use_container_width=True,
        )

        fig = px.bar(
            value_counts,
            x=selected_category,
            y="Count",
            title=f"Top Values — {selected_category}",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# TAB 4 - VISUALIZATION
# =========================================================

with tab_visual:

    st.subheader("📈 Interactive Visualization")

    all_columns = list(df.columns)

    numeric_columns_list = list(
        df.select_dtypes(
            include="number"
        ).columns
    )

    if not numeric_columns_list:

        st.info(
            "This dataset does not contain numeric "
            "columns suitable for visualization."
        )

    else:

        chart_type = st.selectbox(
            "Chart Type",
            [
                "Histogram",
                "Bar Chart",
                "Scatter Plot",
                "Line Chart",
                "Box Plot",
            ],
        )

        if chart_type == "Histogram":

            selected_column = st.selectbox(
                "Select numeric column",
                numeric_columns_list,
            )

            fig = px.histogram(
                df,
                x=selected_column,
                title=f"Distribution — {selected_column}",
            )

        else:

            x_column = st.selectbox(
                "X Axis",
                all_columns,
            )

            y_column = st.selectbox(
                "Y Axis",
                numeric_columns_list,
            )

            if chart_type == "Bar Chart":

                fig = px.bar(
                    df.head(100),
                    x=x_column,
                    y=y_column,
                    title=f"{y_column} by {x_column}",
                )

            elif chart_type == "Scatter Plot":

                fig = px.scatter(
                    df,
                    x=x_column,
                    y=y_column,
                    title=f"{y_column} vs {x_column}",
                )

            elif chart_type == "Line Chart":

                fig = px.line(
                    df,
                    x=x_column,
                    y=y_column,
                    title=f"{y_column} over {x_column}",
                )

            else:

                fig = px.box(
                    df,
                    x=x_column,
                    y=y_column,
                    title=f"{y_column} Distribution",
                )

        fig.update_layout(
            height=550
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# TAB 5 - CORRELATION
# =========================================================

with tab_correlation:

    st.subheader(
        "🔗 Correlation Analysis"
    )

    numeric_df = df.select_dtypes(
        include="number"
    )

    if len(numeric_df.columns) < 2:

        st.info(
            "At least two numeric columns are required "
            "for correlation analysis."
        )

    else:

        correlation = numeric_df.corr()

        fig = px.imshow(
            correlation,
            text_auto=True,
            aspect="auto",
            title="Correlation Matrix",
        )

        fig.update_layout(
            height=650
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    f"InsightAI • {dataset_name}"
)
