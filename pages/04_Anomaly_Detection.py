import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="InsightAI | Anomaly Detection",
    page_icon="🚨",
    layout="wide",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .page-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(
            135deg,
            rgba(239, 68, 68, 0.12),
            rgba(249, 115, 22, 0.08)
        );
        border: 1px solid rgba(100, 116, 139, 0.18);
    }

    .page-header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
    }

    .page-header p {
        margin-top: 8px;
        color: #64748b;
    }

    .section-title {
        font-size: 21px;
        font-weight: 700;
        margin-top: 25px;
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


# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
    <div class="page-header">
        <h1>🚨 Anomaly Detection</h1>
        <p>
            Identify unusual values, statistical outliers and
            potentially abnormal observations in
            <b>{st.session_state.get("active_dataset", "Active Dataset")}</b>.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# NUMERIC COLUMNS
# ============================================================

numeric_columns = []

for column in df.columns:

    converted = pd.to_numeric(
        df[column],
        errors="coerce",
    )

    if converted.notna().sum() >= 5:
        numeric_columns.append(column)


if not numeric_columns:

    st.info(
        "No suitable numeric columns were found for anomaly detection."
    )

    st.stop()


# ============================================================
# CONTROLS
# ============================================================

control1, control2 = st.columns([2, 1])

with control1:

    selected_column = st.selectbox(
        "Select numeric field",
        numeric_columns,
        key="anomaly_selected_column",
    )

with control2:

    method = st.selectbox(
        "Detection method",
        [
            "IQR",
            "Z-Score",
        ],
        key="anomaly_method",
    )


values = pd.to_numeric(
    df[selected_column],
    errors="coerce",
)

working = pd.DataFrame(
    {
        "Original_Index": df.index,
        "Value": values,
    }
)

working = working.dropna().copy()


# ============================================================
# ANOMALY DETECTION
# ============================================================

if method == "IQR":

    q1 = working["Value"].quantile(0.25)
    q3 = working["Value"].quantile(0.75)

    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    working["Anomaly"] = (
        (working["Value"] < lower_bound)
        | (working["Value"] > upper_bound)
    )

else:

    mean = working["Value"].mean()
    std = working["Value"].std()

    if std == 0 or pd.isna(std):

        working["Z_Score"] = 0.0
        working["Anomaly"] = False

    else:

        working["Z_Score"] = (
            (working["Value"] - mean) / std
        )

        working["Anomaly"] = (
            working["Z_Score"].abs() >= 3
        )


# ============================================================
# SUMMARY
# ============================================================

total_values = len(working)

anomaly_count = int(
    working["Anomaly"].sum()
)

normal_count = total_values - anomaly_count

anomaly_percentage = (
    anomaly_count / total_values * 100
    if total_values > 0
    else 0
)


st.markdown(
    '<div class="section-title">📌 Detection Summary</div>',
    unsafe_allow_html=True,
)


m1, m2, m3, m4 = st.columns(4)


with m1:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Analyzed Values</div>
            <div class="metric-value">{total_values:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with m2:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Normal Values</div>
            <div class="metric-value">{normal_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with m3:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Anomalies</div>
            <div class="metric-value">{anomaly_count:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with m4:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Anomaly Rate</div>
            <div class="metric-value">{anomaly_percentage:.2f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PIE CHART
# ============================================================

st.markdown(
    '<div class="section-title">🥧 Normal vs Anomaly</div>',
    unsafe_allow_html=True,
)

pie_df = pd.DataFrame(
    {
        "Status": [
            "Normal",
            "Anomaly",
        ],
        "Count": [
            normal_count,
            anomaly_count,
        ],
    }
)

pie_col1, pie_col2 = st.columns([1, 1])


with pie_col1:

    fig = px.pie(
        pie_df,
        names="Status",
        values="Count",
        hole=0.45,
        title=f"{selected_column} — Data Composition",
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
    )

    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# BOX PLOT
# ============================================================

with pie_col2:

    fig = px.box(
        working,
        y="Value",
        points="outliers",
        title=f"{selected_column} — Outlier Distribution",
    )

    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
        yaxis_title=selected_column,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# DISTRIBUTION
# ============================================================

st.markdown(
    '<div class="section-title">📊 Value Distribution</div>',
    unsafe_allow_html=True,
)

distribution_df = working.copy()

distribution_df["Status"] = np.where(
    distribution_df["Anomaly"],
    "Anomaly",
    "Normal",
)

fig = px.scatter(
    distribution_df,
    x="Original_Index",
    y="Value",
    color="Status",
    title=f"{selected_column} — Normal vs Anomalous Observations",
    hover_data=["Value"],
)

fig.update_layout(
    height=450,
    margin=dict(l=20, r=20, t=60, b=20),
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ============================================================
# ANOMALY DETAILS
# ============================================================

st.markdown(
    '<div class="section-title">🔍 Detected Anomalies</div>',
    unsafe_allow_html=True,
)

anomalies = working[
    working["Anomaly"]
].copy()


if not anomalies.empty:

    if method == "IQR":

        anomalies["Distance_From_Limit"] = np.where(
            anomalies["Value"] > upper_bound,
            anomalies["Value"] - upper_bound,
            lower_bound - anomalies["Value"],
        )

    else:

        anomalies["Absolute_Z_Score"] = (
            anomalies["Z_Score"].abs()
        )

    anomalies = anomalies.sort_values(
        "Value",
        ascending=False,
    )

    display_anomalies = anomalies.copy()

    display_anomalies.insert(
        0,
        "Row",
        display_anomalies["Original_Index"],
    )

    display_anomalies = display_anomalies.drop(
        columns=["Original_Index"]
    )

    st.dataframe(
        display_anomalies,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.success(
        f"No anomalies were detected in '{selected_column}' using {method}."
    )


# ============================================================
# THRESHOLDS
# ============================================================

st.markdown(
    '<div class="section-title">📐 Detection Thresholds</div>',
    unsafe_allow_html=True,
)

if method == "IQR":

    t1, t2, t3 = st.columns(3)

    with t1:
        st.metric(
            "Q1",
            f"{q1:,.4g}",
        )

    with t2:
        st.metric(
            "Q3",
            f"{q3:,.4g}",
        )

    with t3:
        st.metric(
            "IQR",
            f"{iqr:,.4g}",
        )

    st.info(
        f"Values below {lower_bound:,.4g} or above "
        f"{upper_bound:,.4g} are classified as potential outliers."
    )

else:

    mean_value = working["Value"].mean()
    std_value = working["Value"].std()

    t1, t2, t3 = st.columns(3)

    with t1:
        st.metric(
            "Mean",
            f"{mean_value:,.4g}",
        )

    with t2:
        st.metric(
            "Std. Deviation",
            f"{std_value:,.4g}",
        )

    with t3:
        st.metric(
            "Threshold",
            "±3σ",
        )

    st.info(
        "Values with an absolute Z-score of 3 or greater "
        "are classified as potential anomalies."
    )


# ============================================================
# AUTOMATIC INTERPRETATION
# ============================================================

st.markdown(
    '<div class="section-title">🤖 Automatic Interpretation</div>',
    unsafe_allow_html=True,
)

if anomaly_count == 0:

    st.success(
        f"No statistical anomalies were detected in "
        f"'{selected_column}'."
    )

elif anomaly_percentage < 1:

    st.info(
        f"{anomaly_count:,} potential anomaly/anomalies were detected "
        f"({anomaly_percentage:.2f}% of analyzed values). "
        "These observations may deserve further investigation."
    )

elif anomaly_percentage < 5:

    st.warning(
        f"{anomaly_count:,} potential anomalies were detected "
        f"({anomaly_percentage:.2f}% of analyzed values). "
        "Review these observations for unusual business or operational conditions."
    )

else:

    st.error(
        f"{anomaly_count:,} potential anomalies were detected "
        f"({anomaly_percentage:.2f}% of analyzed values). "
        "A relatively large portion of the data is outside the selected statistical threshold."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InsightAI • Statistical anomaly detection using IQR and Z-score methods"
)
