import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from core.forecasting import (
    detect_datetime_columns,
    prepare_time_series,
    build_forecast,
    calculate_model_accuracy,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="InsightAI | Forecasting",
    page_icon="🔮",
    layout="wide",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .forecast-header {
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        background: linear-gradient(
            135deg,
            rgba(99, 102, 241, 0.14),
            rgba(59, 130, 246, 0.08)
        );
        border: 1px solid rgba(100, 116, 139, 0.18);
    }

    .forecast-header h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
    }

    .forecast-header p {
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

    .metric-card {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(100, 116, 139, 0.18);
        min-height: 110px;
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

dataset_name = st.session_state.get(
    "active_dataset",
    "Active Dataset",
)

st.markdown(
    f"""
    <div class="forecast-header">
        <h1>🔮 Forecasting</h1>
        <p>
            Analyze historical trends and generate future predictions
            from <b>{dataset_name}</b>.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATE DETECTION
# ============================================================

try:

    date_columns = detect_datetime_columns(df)

except Exception as exc:

    st.error(
        f"Date detection failed: {exc}"
    )

    st.stop()


if not date_columns:

    st.warning(
        "No suitable date/time column was automatically detected."
    )

    st.markdown(
        """
        ### What Forecasting Needs

        Your dataset should contain a column such as:

        - Date
        - Time
        - Timestamp
        - Month
        - Year
        - DateTime
        - Period

        Example:

        `2026-01-01`, `2026-02-01`, `2026-03-01`
        """
    )

    st.stop()


# ============================================================
# NUMERIC COLUMN DETECTION
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

    st.warning(
        "No suitable numeric metric was found for forecasting."
    )

    st.stop()


# ============================================================
# FORECAST CONFIGURATION
# ============================================================

st.markdown(
    '<div class="section-title">⚙️ Forecast Configuration</div>',
    unsafe_allow_html=True,
)


control1, control2, control3 = st.columns(
    [1.5, 1.5, 1]
)


with control1:

    date_column = st.selectbox(
        "Date / Time Column",
        date_columns,
        key="forecast_date_column",
    )


with control2:

    metric_column = st.selectbox(
        "Metric to Forecast",
        numeric_columns,
        key="forecast_metric_column",
    )


with control3:

    horizon = st.selectbox(
        "Forecast Horizon",
        [7, 14, 30, 60, 90],
        index=2,
        key="forecast_horizon",
    )


# ============================================================
# PREPARE TIME SERIES
# ============================================================

try:

    prepared = prepare_time_series(
        df,
        date_column,
        metric_column,
    )

except Exception as exc:

    st.error(
        f"Unable to prepare the time series: {exc}"
    )

    st.stop()


if prepared is None or len(prepared) < 5:

    st.warning(
        "There are not enough valid historical observations "
        "to generate a forecast."
    )

    st.stop()


# ============================================================
# NORMALIZE PREPARED DATA
# ============================================================

prepared = prepared.copy()


# Find date column returned by prepare_time_series()

date_candidates = [
    column
    for column in prepared.columns
    if (
        "date" in str(column).lower()
        or "time" in str(column).lower()
        or "timestamp" in str(column).lower()
    )
]


if date_candidates:

    prepared_date_column = date_candidates[0]

else:

    prepared_date_column = prepared.columns[0]


# Find numeric value column

if metric_column in prepared.columns:

    prepared_value_column = metric_column

else:

    prepared_numeric_columns = [
        column
        for column in prepared.columns
        if pd.api.types.is_numeric_dtype(
            prepared[column]
        )
    ]

    if not prepared_numeric_columns:

        st.error(
            "Could not identify the numeric value column "
            "after preparing the time series."
        )

        st.stop()

    prepared_value_column = (
        prepared_numeric_columns[-1]
    )


prepared[prepared_date_column] = pd.to_datetime(
    prepared[prepared_date_column],
    errors="coerce",
)


prepared[prepared_value_column] = pd.to_numeric(
    prepared[prepared_value_column],
    errors="coerce",
)


prepared = prepared.dropna(
    subset=[
        prepared_date_column,
        prepared_value_column,
    ]
)


prepared = prepared.sort_values(
    prepared_date_column
)


if len(prepared) < 5:

    st.warning(
        "Not enough valid observations remain after cleaning "
        "the time series."
    )

    st.stop()


# ============================================================
# HISTORICAL SUMMARY
# ============================================================

latest_value = prepared[
    prepared_value_column
].iloc[-1]


average_value = prepared[
    prepared_value_column
].mean()


minimum_value = prepared[
    prepared_value_column
].min()


maximum_value = prepared[
    prepared_value_column
].max()


# ============================================================
# KPI CARDS
# ============================================================

st.markdown(
    '<div class="section-title">📌 Historical Summary</div>',
    unsafe_allow_html=True,
)


k1, k2, k3, k4 = st.columns(4)


with k1:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Observations</div>
            <div class="metric-value">
                {len(prepared):,}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with k2:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Latest Value</div>
            <div class="metric-value">
                {latest_value:,.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with k3:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Average</div>
            <div class="metric-value">
                {average_value:,.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with k4:

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Range</div>
            <div class="metric-value">
                {minimum_value:,.2f} — {maximum_value:,.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HISTORICAL TREND
# ============================================================

st.markdown(
    '<div class="section-title">📈 Historical Trend</div>',
    unsafe_allow_html=True,
)


historical_fig = go.Figure()


historical_fig.add_trace(
    go.Scatter(
        x=prepared[prepared_date_column],
        y=prepared[prepared_value_column],
        mode="lines+markers",
        name="Historical",
    )
)


historical_fig.update_layout(
    title=f"Historical {metric_column}",
    height=450,
    margin=dict(
        l=20,
        r=20,
        t=60,
        b=20,
    ),
    xaxis_title="Date",
    yaxis_title=metric_column,
    hovermode="x unified",
)


st.plotly_chart(
    historical_fig,
    use_container_width=True,
)


# ============================================================
# BUILD FORECAST
# ============================================================

st.markdown(
    '<div class="section-title">🔮 Generate Forecast</div>',
    unsafe_allow_html=True,
)


with st.spinner(
    "Building forecasting model..."
):

    try:

        # IMPORTANT:
        # Existing core.forecasting.py expects:
        #
        # build_forecast(
        #     df,
        #     date_column,
        #     value_column,
        #     forecast_periods
        # )

        forecast_result = build_forecast(
            prepared,
            prepared_date_column,
            prepared_value_column,
            forecast_periods=horizon,
        )

    except Exception as exc:

        st.error(
            f"Forecast model could not be built: {exc}"
        )

        st.stop()


# ============================================================
# NORMALIZE FORECAST RESULT
# ============================================================

forecast_df = None
model = None


if isinstance(
    forecast_result,
    pd.DataFrame,
):

    forecast_df = forecast_result


elif isinstance(
    forecast_result,
    tuple,
):

    for item in forecast_result:

        if isinstance(
            item,
            pd.DataFrame,
        ):

            forecast_df = item

        else:

            model = item


elif isinstance(
    forecast_result,
    dict,
):

    for key in [
        "forecast",
        "forecast_df",
        "predictions",
        "result",
    ]:

        if isinstance(
            forecast_result.get(key),
            pd.DataFrame,
        ):

            forecast_df = forecast_result[key]

            break

    model = forecast_result.get(
        "model"
    )


if forecast_df is None:

    st.error(
        "The forecasting engine returned an "
        "unsupported result format."
    )

    st.stop()


forecast_df = forecast_df.copy()


# ============================================================
# IDENTIFY FORECAST DATE COLUMN
# ============================================================

forecast_date_candidates = [
    column
    for column in forecast_df.columns
    if (
        "date" in str(column).lower()
        or "time" in str(column).lower()
        or "timestamp" in str(column).lower()
    )
]


if forecast_date_candidates:

    forecast_date_column = (
        forecast_date_candidates[0]
    )

else:

    forecast_date_column = (
        forecast_df.columns[0]
    )


# ============================================================
# IDENTIFY FORECAST VALUE COLUMN
# ============================================================

forecast_numeric_candidates = [
    column
    for column in forecast_df.columns
    if pd.api.types.is_numeric_dtype(
        forecast_df[column]
    )
]


if not forecast_numeric_candidates:

    st.error(
        "No numeric forecast values were returned "
        "by the model."
    )

    st.stop()


prediction_candidates = [
    column
    for column in forecast_numeric_candidates
    if any(
        word in str(column).lower()
        for word in [
            "forecast",
            "prediction",
            "predicted",
            "yhat",
        ]
    )
]


if prediction_candidates:

    forecast_value_column = (
        prediction_candidates[0]
    )

else:

    forecast_value_column = (
        forecast_numeric_candidates[-1]
    )


# ============================================================
# CLEAN FORECAST
# ============================================================

forecast_df[
    forecast_date_column
] = pd.to_datetime(
    forecast_df[
        forecast_date_column
    ],
    errors="coerce",
)


forecast_df[
    forecast_value_column
] = pd.to_numeric(
    forecast_df[
        forecast_value_column
    ],
    errors="coerce",
)


forecast_df = forecast_df.dropna(
    subset=[
        forecast_date_column,
        forecast_value_column,
    ]
)


if forecast_df.empty:

    st.error(
        "The forecast result contains no valid "
        "prediction values."
    )

    st.stop()


# ============================================================
# FORECAST CHART
# ============================================================

st.markdown(
    '<div class="section-title">📈 Forecast Result</div>',
    unsafe_allow_html=True,
)


forecast_fig = go.Figure()


forecast_fig.add_trace(
    go.Scatter(
        x=prepared[prepared_date_column],
        y=prepared[prepared_value_column],
        mode="lines",
        name="Historical",
    )
)


forecast_fig.add_trace(
    go.Scatter(
        x=forecast_df[forecast_date_column],
        y=forecast_df[forecast_value_column],
        mode="lines+markers",
        name="Forecast",
        line=dict(
            dash="dash"
        ),
    )
)


forecast_fig.update_layout(
    title=(
        f"{metric_column} — "
        "Historical vs Forecast"
    ),
    height=500,
    margin=dict(
        l=20,
        r=20,
        t=60,
        b=20,
    ),
    xaxis_title="Date",
    yaxis_title=metric_column,
    hovermode="x unified",
)


st.plotly_chart(
    forecast_fig,
    use_container_width=True,
)


# ============================================================
# FORECAST SUMMARY
# ============================================================

forecast_values = forecast_df[
    forecast_value_column
].dropna()


if not forecast_values.empty:

    first_forecast = forecast_values.iloc[0]

    last_forecast = forecast_values.iloc[-1]

    forecast_average = forecast_values.mean()

    if latest_value != 0:

        forecast_change = (
            (
                last_forecast
                - latest_value
            )
            / abs(latest_value)
            * 100
        )

    else:

        forecast_change = np.nan


    st.markdown(
        '<div class="section-title">📊 Forecast Summary</div>',
        unsafe_allow_html=True,
    )


    f1, f2, f3, f4 = st.columns(4)


    with f1:

        st.metric(
            "Forecast Points",
            f"{len(forecast_values):,}",
        )


    with f2:

        st.metric(
            "First Forecast",
            f"{first_forecast:,.2f}",
        )


    with f3:

        st.metric(
            "Final Forecast",
            f"{last_forecast:,.2f}",
        )


    with f4:

        if np.isfinite(
            forecast_change
        ):

            st.metric(
                "Change vs Latest",
                f"{forecast_change:+.2f}%",
            )

        else:

            st.metric(
                "Change vs Latest",
                "N/A",
            )


# ============================================================
# MODEL ACCURACY
# ============================================================

st.markdown(
    '<div class="section-title">🎯 Model Accuracy</div>',
    unsafe_allow_html=True,
)


accuracy = None


try:

    accuracy = calculate_model_accuracy(
        prepared,
        model,
    )

except Exception:

    accuracy = None


if isinstance(
    accuracy,
    dict,
):

    accuracy_items = list(
        accuracy.items()
    )

    accuracy_cols = st.columns(
        max(1, len(accuracy_items))
    )

    for index, (
        key,
        value,
    ) in enumerate(
        accuracy_items
    ):

        with accuracy_cols[index]:

            label = (
                str(key)
                .replace("_", " ")
                .title()
            )

            if isinstance(
                value,
                (
                    int,
                    float,
                    np.number,
                ),
            ):

                st.metric(
                    label,
                    f"{float(value):.2f}",
                )

            else:

                st.metric(
                    label,
                    str(value),
                )


elif isinstance(
    accuracy,
    (
        int,
        float,
        np.number,
    ),
):

    st.metric(
        "Accuracy Score",
        f"{float(accuracy):.2f}",
    )


else:

    st.info(
        "Model accuracy information is not available "
        "for this forecast."
    )


# ============================================================
# FORECAST TABLE
# ============================================================

st.markdown(
    '<div class="section-title">📋 Forecast Values</div>',
    unsafe_allow_html=True,
)


display_forecast = forecast_df.copy()


display_forecast[
    forecast_date_column
] = (
    display_forecast[
        forecast_date_column
    ].dt.strftime("%Y-%m-%d")
)


st.dataframe(
    display_forecast,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# DOWNLOAD
# ============================================================

csv_data = forecast_df.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    "⬇️ Download Forecast CSV",
    data=csv_data,
    file_name="insightai_forecast.csv",
    mime="text/csv",
    use_container_width=True,
)


# ============================================================
# AUTOMATIC INTERPRETATION
# ============================================================

st.markdown(
    '<div class="section-title">🤖 Forecast Interpretation</div>',
    unsafe_allow_html=True,
)


if not forecast_values.empty:

    if np.isfinite(
        forecast_change
    ):

        if forecast_change > 10:

            st.success(
                f"The forecast indicates an upward movement "
                f"of approximately {forecast_change:.2f}% "
                f"from the latest observed value to the "
                f"end of the forecast horizon."
            )

        elif forecast_change < -10:

            st.warning(
                f"The forecast indicates a downward movement "
                f"of approximately {abs(forecast_change):.2f}% "
                f"from the latest observed value to the "
                f"end of the forecast horizon."
            )

        else:

            st.info(
                f"The forecast indicates relatively stable "
                f"movement, with an estimated change of "
                f"{forecast_change:+.2f}% from the latest "
                f"observed value."
            )

    st.caption(
        "Forecasts are statistical/model-based estimates "
        "and should be interpreted together with historical "
        "patterns and business context."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "InsightAI • AI-Powered Data Analytics & "
    "Decision Intelligence Platform"
)
