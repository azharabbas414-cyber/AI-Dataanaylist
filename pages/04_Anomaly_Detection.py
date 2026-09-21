import streamlit as st
import plotly.express as px

from core.anomaly import (
    anomaly_summary,
    explain_anomalies,
)


st.set_page_config(
    page_title="InsightAI - Anomaly Detection",
    page_icon="🚨",
    layout="wide",
)


# ---------------------------------------------------------
# CHECK ACTIVE DATASET
# ---------------------------------------------------------

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):
    st.warning("No active dataset is selected.")

    st.info(
        "Return to Home and select an existing GitHub dataset "
        "or upload a new dataset."
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


# ---------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------

analysis = anomaly_summary(df)

total_rows = analysis["total_rows"]
anomaly_rows = analysis["anomaly_rows"]
anomaly_percentage = analysis["anomaly_percentage"]

statistical_anomalies = analysis[
    "statistical_anomalies"
]

isolation_results = analysis[
    "isolation_results"
]


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🚨 Anomaly Detection")

st.caption(
    f"Automatically identify unusual patterns in **{dataset_name}**."
)


# ---------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Rows",
        f"{total_rows:,}"
    )

with col2:
    st.metric(
        "Detected Anomalies",
        f"{anomaly_rows:,}"
    )

with col3:
    st.metric(
        "Anomaly Rate",
        f"{anomaly_percentage:.2f}%"
    )

with col4:
    numeric_columns = len(
        df.select_dtypes(include="number").columns
    )

    st.metric(
        "Numeric Fields",
        f"{numeric_columns:,}"
    )


st.divider()


# ---------------------------------------------------------
# EXPLANATION
# ---------------------------------------------------------

st.subheader("🧠 How InsightAI Detects Anomalies")

st.write(
    """
InsightAI uses two complementary approaches:

**1. Statistical Detection — IQR**

Identifies values that fall significantly outside the
normal range of an individual numeric column.

**2. Multivariate Detection — Isolation Forest**

Looks at multiple numeric variables together and identifies
rows whose overall pattern differs from the rest of the dataset.
"""
)


st.divider()


# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------

tab_overview, tab_statistical, tab_ai, tab_records = st.tabs(
    [
        "📊 Overview",
        "📐 Statistical Anomalies",
        "🤖 Pattern Detection",
        "🔎 Anomaly Records",
    ]
)


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------

with tab_overview:

    st.subheader("Anomaly Overview")

    if isolation_results.empty:

        st.info(
            "There is not enough numeric data to perform "
            "multivariate anomaly detection."
        )

    else:

        normal_count = int(
            (isolation_results["Anomaly"] == "Normal").sum()
        )

        anomaly_count = int(
            (isolation_results["Anomaly"] == "Anomaly").sum()
        )

        chart_data = {
            "Status": [
                "Normal",
                "Anomaly",
            ],
            "Records": [
                normal_count,
                anomaly_count,
            ],
        }

        fig = px.pie(
            chart_data,
            names="Status",
            values="Records",
            title="Normal vs Anomalous Records",
            hole=0.45,
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ---------------------------------------------------------
# STATISTICAL ANOMALIES
# ---------------------------------------------------------

with tab_statistical:

    st.subheader("📐 Statistical Anomalies")

    if statistical_anomalies.empty:

        st.success(
            "No statistical anomalies were detected."
        )

    else:

        st.dataframe(
            statistical_anomalies,
            use_container_width=True,
            hide_index=True,
        )

        fig = px.bar(
            statistical_anomalies,
            x="column",
            y="anomalies",
            text="anomalies",
            title="Anomalies by Numeric Column",
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# ---------------------------------------------------------
# PATTERN DETECTION
# ---------------------------------------------------------

with tab_ai:

    st.subheader(
        "🤖 Multivariate Pattern Detection"
    )

    if isolation_results.empty:

        st.info(
            "Not enough numeric data is available "
            "for Isolation Forest analysis."
        )

    else:

        anomaly_count = int(
            (
                isolation_results["Anomaly"]
                == "Anomaly"
            ).sum()
        )

        if anomaly_count == 0:

            st.success(
                "No multivariate anomalies were detected."
            )

        else:

            st.warning(
                f"{anomaly_count:,} records were identified "
                "as potentially anomalous."
            )

            explanations = explain_anomalies(
                df,
                isolation_results,
                max_rows=20,
            )

            if not explanations.empty:

                st.dataframe(
                    explanations,
                    use_container_width=True,
                    hide_index=True,
                )


# ---------------------------------------------------------
# ANOMALY RECORDS
# ---------------------------------------------------------

with tab_records:

    st.subheader(
        "🔎 Detected Anomaly Records"
    )

    if isolation_results.empty:

        st.info(
            "No anomaly records are available."
        )

    else:

        anomaly_records = isolation_results[
            isolation_results["Anomaly"]
            == "Anomaly"
        ].copy()

        if anomaly_records.empty:

            st.success(
                "No anomalous records detected."
            )

        else:

            st.write(
                f"Showing {len(anomaly_records):,} "
                "detected anomalous records."
            )

            display_columns = [
                column
                for column in anomaly_records.columns
                if column not in ["_anomaly_score"]
            ]

            st.dataframe(
                anomaly_records[
                    display_columns
                ],
                use_container_width=True,
                height=500,
            )

            st.download_button(
                label="⬇️ Download Anomaly Records",
                data=anomaly_records.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name="insightai_anomalies.csv",
                mime="text/csv",
                use_container_width=True,
            )


st.divider()

st.caption(
    f"InsightAI • Anomaly Detection • {dataset_name}"
)
