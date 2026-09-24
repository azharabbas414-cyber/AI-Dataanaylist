import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from core.anomaly import (
    detect_anomalies,
    explain_anomalies,
)


st.set_page_config(
    page_title="InsightAI | Anomaly Detection",
    page_icon="🚨",
    layout="wide",
)

st.markdown(
    """
    <style>
    .page-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(135deg, rgba(239,68,68,.12), rgba(249,115,22,.08));
        border: 1px solid rgba(100,116,139,.18);
    }
    .page-header h1 { margin: 0; font-size: 32px; font-weight: 700; }
    .page-header p { margin-top: 8px; color: #64748b; }
    .section-title { font-size: 21px; font-weight: 700; margin-top: 25px; margin-bottom: 12px; }
    .metric-card { padding: 18px; border-radius: 14px; border: 1px solid rgba(100,116,139,.18); min-height: 105px; }
    .metric-label { color: #64748b; font-size: 13px; }
    .metric-value { font-size: 27px; font-weight: 700; margin-top: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


if "active_dataframe" not in st.session_state:
    st.session_state.active_dataframe = None

if st.session_state.active_dataframe is None:
    st.warning("No active dataset found. Please select or upload a dataset from the Home page.")
    if st.button("🏠 Go to Home", type="primary"):
        st.switch_page("streamlitapp.py")
    st.stop()


df = st.session_state.active_dataframe.copy()

if df.empty:
    st.warning("The active dataset is empty.")
    st.stop()


st.markdown(
    f"""
    <div class="page-header">
        <h1>🚨 Anomaly Detection</h1>
        <p>Identify unusual values, statistical outliers and potentially abnormal observations in
        <b>{st.session_state.get("active_dataset", "Active Dataset")}</b>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# Numeric columns that contain enough usable observations.
numeric_columns = []
for column in df.columns:
    converted = pd.to_numeric(df[column], errors="coerce")
    if converted.notna().sum() >= 5:
        numeric_columns.append(column)

if not numeric_columns:
    st.info("No suitable numeric columns were found for anomaly detection.")
    st.stop()


# ------------------------------------------------------------------
# Controls
# ------------------------------------------------------------------
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
        ["IQR", "Z-Score", "Isolation Forest"],
        key="anomaly_method",
    )


# Method-specific controls.
parameter_col1, parameter_col2 = st.columns([2, 2])

with parameter_col1:
    if method == "IQR":
        iqr_multiplier = st.slider(
            "IQR multiplier",
            min_value=0.5,
            max_value=5.0,
            value=1.5,
            step=0.1,
            help="Values outside Q1/Q3 ± multiplier × IQR are treated as anomalies.",
        )
        threshold_text = f"Multiplier: {iqr_multiplier:.1f}"

    elif method == "Z-Score":
        z_threshold = st.slider(
            "Z-score threshold",
            min_value=1.0,
            max_value=5.0,
            value=3.0,
            step=0.1,
            help="Higher values make the detector less sensitive.",
        )
        threshold_text = f"Threshold: {z_threshold:.1f}"

    else:
        contamination_pct = st.slider(
            "Expected contamination",
            min_value=0.01,
            max_value=0.20,
            value=0.05,
            step=0.01,
            format="%.0f%%",
            help="Expected approximate proportion of observations that may be anomalous.",
        )
        threshold_text = f"Contamination: {contamination_pct:.0%}"

with parameter_col2:
    st.caption(f"**Method:** {method}  •  **{threshold_text}**")


# ------------------------------------------------------------------
# Unified anomaly engine
# ------------------------------------------------------------------
method_key = {
    "IQR": "iqr",
    "Z-Score": "zscore",
    "Isolation Forest": "isolation_forest",
}[method]

kwargs = {}
if method == "IQR":
    kwargs["multiplier"] = iqr_multiplier
elif method == "Z-Score":
    kwargs["threshold"] = z_threshold
else:
    kwargs["contamination"] = contamination_pct

try:
    anomalies, summary = detect_anomalies(
        df,
        method=method_key,
        columns=[selected_column],
        **kwargs,
    )
except Exception as exc:
    st.error(f"Anomaly detection failed: {exc}")
    st.stop()


values = pd.to_numeric(df[selected_column], errors="coerce")
working = pd.DataFrame(
    {
        "Original_Index": df.index,
        "Value": values,
    }
).dropna()

# Rebuild the boolean mask from the returned anomaly indexes.
working["Anomaly"] = working["Original_Index"].isin(anomalies.index)

total_values = len(working)
anomaly_count = int(working["Anomaly"].sum())
normal_count = total_values - anomaly_count
anomaly_percentage = anomaly_count / total_values * 100 if total_values else 0


st.markdown('<div class="section-title">📌 Detection Summary</div>', unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Analyzed Values</div><div class="metric-value">{total_values:,}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Normal Values</div><div class="metric-value">{normal_count:,}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Anomalies</div><div class="metric-value">{anomaly_count:,}</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Anomaly Rate</div><div class="metric-value">{anomaly_percentage:.2f}%</div></div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------
st.markdown('<div class="section-title">🥧 Normal vs Anomaly</div>', unsafe_allow_html=True)

pie_df = pd.DataFrame({
    "Status": ["Normal", "Anomaly"],
    "Count": [normal_count, anomaly_count],
})

pie_col1, pie_col2 = st.columns(2)

with pie_col1:
    fig = px.pie(
        pie_df,
        names="Status",
        values="Count",
        hole=0.45,
        title=f"{selected_column} — Data Composition",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, use_container_width=True)

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
    st.plotly_chart(fig, use_container_width=True)


st.markdown('<div class="section-title">📊 Value Distribution</div>', unsafe_allow_html=True)

distribution_df = working.copy()
distribution_df["Status"] = np.where(distribution_df["Anomaly"], "Anomaly", "Normal")

fig = px.scatter(
    distribution_df,
    x="Original_Index",
    y="Value",
    color="Status",
    title=f"{selected_column} — Normal vs Anomalous Observations",
    hover_data=["Value"],
)
fig.update_layout(height=450, margin=dict(l=20, r=20, t=60, b=20))
st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# Details
# ------------------------------------------------------------------
st.markdown('<div class="section-title">🔍 Detected Anomalies</div>', unsafe_allow_html=True)

if not anomalies.empty:
    display_anomalies = anomalies.copy()
    display_anomalies.insert(0, "Row", display_anomalies.index)
    display_anomalies = display_anomalies.reset_index(drop=True)

    # For a single-column analysis, add useful method-specific evidence.
    anomaly_values = pd.to_numeric(display_anomalies[selected_column], errors="coerce")

    if method == "IQR":
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr
        display_anomalies["Distance_From_Limit"] = np.where(
            anomaly_values > upper_bound,
            anomaly_values - upper_bound,
            lower_bound - anomaly_values,
        )
    elif method == "Z-Score":
        mean = values.mean()
        std = values.std()
        display_anomalies["Z_Score"] = (
            (anomaly_values - mean) / std if std else 0.0
        )
        display_anomalies["Absolute_Z_Score"] = display_anomalies["Z_Score"].abs()
    else:
        display_anomalies["Detection"] = "Isolation Forest"

    display_anomalies = display_anomalies.sort_values(
        selected_column,
        ascending=False,
        na_position="last",
    )

    st.dataframe(display_anomalies, use_container_width=True, hide_index=True)

    explanations = explain_anomalies(
        df,
        anomalies,
        max_items=5,
    )
    if explanations:
        st.markdown("**Why these values are unusual**")
        for explanation in explanations:
            st.write(f"• {explanation}")
else:
    st.success(f"No anomalies were detected in '{selected_column}' using {method}.")


# ------------------------------------------------------------------
# Method information
# ------------------------------------------------------------------
st.markdown('<div class="section-title">📐 Detection Method Details</div>', unsafe_allow_html=True)

if method == "IQR":
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - iqr_multiplier * iqr
    upper_bound = q3 + iqr_multiplier * iqr

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Q1", f"{q1:,.4g}")
    t2.metric("Q3", f"{q3:,.4g}")
    t3.metric("IQR", f"{iqr:,.4g}")
    t4.metric("Multiplier", f"{iqr_multiplier:.1f}×")
    st.info(
        f"Values below {lower_bound:,.4g} or above {upper_bound:,.4g} are classified as potential outliers."
    )

elif method == "Z-Score":
    mean = values.mean()
    std = values.std()

    t1, t2, t3 = st.columns(3)
    t1.metric("Mean", f"{mean:,.4g}")
    t2.metric("Std. Deviation", f"{std:,.4g}")
    t3.metric("Threshold", f"±{z_threshold:.1f}")
    st.info(
        f"Observations with an absolute Z-score of at least {z_threshold:.1f} are classified as anomalies."
    )

else:
    t1, t2 = st.columns(2)
    t1.metric("Contamination", f"{contamination_pct:.0%}")
    t2.metric("Estimator", "Isolation Forest")
    st.info(
        "Isolation Forest is an ML-based detector that identifies observations that are easier to isolate from the rest of the data. "
        "The contamination value controls the expected proportion of anomalies."
    )
