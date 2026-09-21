import streamlit as st
import plotly.graph_objects as go

from core.forecasting import (
    detect_datetime_columns,
    build_forecast,
    calculate_model_accuracy,
)


st.set_page_config(
    page_title="InsightAI - Forecasting",
    page_icon="🔮",
    layout="wide",
)


# ---------------------------------------------------------
# ACTIVE DATASET CHECK
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


df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Dataset"
)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🔮 Forecasting")

st.caption(
    f"Predict future trends from **{dataset_name}**."
)


# ---------------------------------------------------------
# DETECT DATE COLUMNS
# ---------------------------------------------------------

datetime_columns = detect_datetime_columns(df)

numeric_columns = list(
    df.select_dtypes(
        include="number"
    ).columns
)


if not datetime_columns:

    st.warning(
        "No suitable date/time column was detected "
        "in this dataset."
    )

    st.info(
        "Forecasting requires a date/time column and "
        "a numeric value column."
    )

    st.stop()


if not numeric_columns:

    st.warning(
        "No numeric columns were detected."
    )

    st.info(
        "Forecasting requires at least one numeric "
        "column to predict."
    )

    st.stop()


# ---------------------------------------------------------
# FORECAST CONFIGURATION
# ---------------------------------------------------------

st.subheader("⚙️ Forecast Configuration")

col1, col2, col3 = st.columns(3)

with col1:

    date_column = st.selectbox(
        "Date / Time Column",
        datetime_columns,
    )

with col2:

    value_column = st.selectbox(
        "Value to Forecast",
        numeric_columns,
    )

with col3:

    forecast_periods = st.number_input(
        "Forecast Periods",
        min_value=1,
        max_value=90,
        value=7,
        step=1,
    )


st.divider()


# ---------------------------------------------------------
# FORECAST BUTTON
# ---------------------------------------------------------

if st.button(
    "🔮 Generate Forecast",
    type="primary",
    use_container_width=True,
):

    with st.spinner(
        "Training forecasting model..."
    ):

        try:

            historical, forecast, model = (
                build_forecast(
                    df,
                    date_column,
                    value_column,
                    int(forecast_periods),
                )
            )

            accuracy = calculate_model_accuracy(
                df,
                date_column,
                value_column,
            )

            st.session_state.forecast_historical = (
                historical
            )

            st.session_state.forecast_result = (
                forecast
            )

            st.session_state.forecast_accuracy = (
                accuracy
            )

            st.session_state.forecast_date_column = (
                date_column
            )

            st.session_state.forecast_value_column = (
                value_column
            )

            st.success(
                "Forecast generated successfully."
            )

        except Exception as error:

            st.error(
                f"Unable to generate forecast: {error}"
            )


# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------

if (
    "forecast_result"
    not in st.session_state
):

    st.info(
        "Configure the forecast above and click "
        "**Generate Forecast**."
    )

    st.stop()


historical = (
    st.session_state.forecast_historical
)

forecast = (
    st.session_state.forecast_result
)

accuracy = (
    st.session_state.forecast_accuracy
)


# ---------------------------------------------------------
# KPI SUMMARY
# ---------------------------------------------------------

last_actual = historical["Actual"].iloc[-1]

first_forecast = forecast["Forecast"].iloc[0]

last_forecast = forecast["Forecast"].iloc[-1]

change = (
    last_forecast - last_actual
)

if last_actual != 0:

    change_percentage = (
        change / abs(last_actual)
    ) * 100

else:

    change_percentage = 0


col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Historical Observations",
        f"{len(historical):,}",
    )

with col2:

    st.metric(
        "Forecast Periods",
        f"{len(forecast):,}",
    )

with col3:

    st.metric(
        "Last Actual",
        f"{last_actual:,.2f}",
    )

with col4:

    st.metric(
        "Final Forecast",
        f"{last_forecast:,.2f}",
        delta=f"{change_percentage:+.2f}%",
    )


st.divider()


# ---------------------------------------------------------
# FORECAST CHART
# ---------------------------------------------------------

st.subheader("📈 Historical vs Forecast")

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=historical[
            date_column
        ],
        y=historical["Actual"],
        mode="lines",
        name="Actual",
    )
)

fig.add_trace(
    go.Scatter(
        x=forecast[
            date_column
        ],
        y=forecast["Forecast"],
        mode="lines+markers",
        name="Forecast",
    )
)

fig.update_layout(
    height=550,
    xaxis_title="Date",
    yaxis_title=value_column,
    hovermode="x unified",
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ---------------------------------------------------------
# FORECAST TABLE
# ---------------------------------------------------------

st.subheader("🔮 Forecast Values")

display_forecast = forecast.copy()

display_forecast["Forecast"] = (
    display_forecast["Forecast"]
    .round(2)
)

st.dataframe(
    display_forecast,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# MODEL PERFORMANCE
# ---------------------------------------------------------

st.divider()

st.subheader("📊 Model Performance")

if accuracy is None:

    st.info(
        "There are not enough historical observations "
        "to calculate a reliable holdout evaluation."
    )

else:

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "MAE",
            f"{accuracy['MAE']:,.2f}",
        )

    with col2:

        st.metric(
            "RMSE",
            f"{accuracy['RMSE']:,.2f}",
        )

    with col3:

        if accuracy["MAPE"] is not None:

            st.metric(
                "MAPE",
                f"{accuracy['MAPE']:.2f}%",
            )

        else:

            st.metric(
                "MAPE",
                "N/A",
            )


st.divider()


# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------

csv_data = forecast.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "⬇️ Download Forecast",
    data=csv_data,
    file_name="insightai_forecast.csv",
    mime="text/csv",
    use_container_width=True,
)


st.divider()

st.caption(
    f"InsightAI • Forecasting • {dataset_name}"
)
