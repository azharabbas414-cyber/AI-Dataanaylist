from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.forecasting import (
    AGGREGATION_OPTIONS,
    TIME_GRAIN_OPTIONS,
    build_forecast,
    calculate_model_accuracy,
    detect_datetime_columns,
    prepare_time_series,
)


st.set_page_config(
    page_title="InsightAI | Forecasting",
    page_icon="🔮",
    layout="wide",
)


st.markdown(
    """
    <style>
    .forecast-hero {
        padding: 30px 34px;
        border-radius: 22px;
        margin-bottom: 24px;
        background: linear-gradient(135deg, rgba(99,102,241,.14), rgba(14,165,233,.08));
        border: 1px solid rgba(100,116,139,.18);
    }
    .forecast-hero h1 { margin: 0; font-size: 36px; font-weight: 800; }
    .forecast-hero p { margin: 8px 0 0; opacity: .7; font-size: 15px; }
    .section-title { font-size: 22px; font-weight: 750; margin: 26px 0 12px; }
    .insight-box {
        padding: 18px 20px;
        border-radius: 16px;
        border: 1px solid rgba(100,116,139,.18);
        background: rgba(100,116,139,.045);
        line-height: 1.6;
    }
    .concept-card {
        padding: 18px;
        border-radius: 16px;
        border: 1px solid rgba(100,116,139,.18);
        background: rgba(100,116,139,.035);
        min-height: 150px;
    }
    .concept-card h4 { margin: 0 0 8px; }
    .concept-card p { margin: 0; opacity: .78; line-height: 1.55; }
    .example-box {
        padding: 16px 18px;
        border-radius: 14px;
        border-left: 4px solid rgba(99,102,241,.65);
        background: rgba(99,102,241,.06);
        line-height: 1.65;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


if st.session_state.get("active_dataframe") is None:
    st.warning("No active dataset found. Please upload or connect a dataset from the Home page.")
    if st.button("🏠 Go to Home", type="primary"):
        st.switch_page("streamlitapp.py")
    st.stop()


df = st.session_state.active_dataframe.copy()
if df.empty:
    st.warning("The active dataset is empty.")
    st.stop()


dataset_name = st.session_state.get("active_dataset", "Active Dataset")

st.markdown(
    f"""
    <div class="forecast-hero">
        <h1>🔮 Forecasting Intelligence</h1>
        <p>Predict the future of a metric from its historical time pattern — for example, monthly telecom revenue, daily data traffic, hourly bandwidth, or weekly orders.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Explain the concept before asking the user to configure a model.
# ------------------------------------------------------------------

st.markdown('<div class="section-title">❓ What does Forecasting do?</div>', unsafe_allow_html=True)

concepts = st.columns(3)
with concepts[0]:
    st.markdown(
        """
        <div class="concept-card">
            <h4>1️⃣ Learn from history</h4>
            <p>InsightAI looks at how a selected metric changed over time. It can use sales, billing, traffic, calls, revenue, users, or any other measurable value.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with concepts[1]:
    st.markdown(
        """
        <div class="concept-card">
            <h4>2️⃣ Find the pattern</h4>
            <p>The engine checks trend and recurring behaviour, then backtests available models against historical data before choosing an automatic model.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with concepts[2]:
    st.markdown(
        """
        <div class="concept-card">
            <h4>3️⃣ Estimate the future</h4>
            <p>The result is a future series plus an uncertainty range. The forecast is an estimate, not a guarantee, so historical accuracy should always be reviewed.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="example-box">
        <b>Telecom example:</b> If your dataset contains <b>Billing_Date</b> and <b>Total_Bill</b>, choose Billing_Date → Monthly → Total_Bill → Sum. InsightAI then creates a monthly billing history and forecasts the next few months.<br>
        <b>CDR example:</b> If every row is a call, choose Timestamp → Daily → Row Count. The forecast then estimates the number of calls per future day.<br>
        <b>Network example:</b> If you have hourly throughput, choose Timestamp → Hourly → Throughput → Mean to estimate future average throughput.
    </div>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Detect candidate fields
# ------------------------------------------------------------------

try:
    date_columns = detect_datetime_columns(df)
except Exception as exc:
    st.error(f"Date detection failed: {exc}")
    st.stop()

numeric_columns = []
for column in df.columns:
    converted = pd.to_numeric(df[column], errors="coerce")
    if converted.notna().sum() >= 5 and converted.nunique(dropna=True) > 1:
        numeric_columns.append(column)

if not date_columns:
    st.warning("No suitable date/time column was detected.")
    st.info("Add a Date, Time, Timestamp, Month or similar field to use forecasting.")
    st.stop()


# ------------------------------------------------------------------
# Forecast setup
# ------------------------------------------------------------------

st.markdown('<div class="section-title">⚙️ Build Your Forecast</div>', unsafe_allow_html=True)

with st.expander("📘 How to choose these fields", expanded=True):
    st.markdown(
        """
        **Date / Time** = when the measurement happened.

        **Metric** = what you want to predict in the future.

        **Time Grain** = the period of the forecast. This is very important for raw transaction data. A CDR file may contain thousands of individual calls, but you normally forecast **calls per day** or **calls per hour**, not each individual row.

        **Aggregation** = how multiple records inside one period are combined:
        - **Sum** → revenue, billing amount, traffic volume, number of MB/GB, sales
        - **Mean** → average throughput, latency, temperature, price
        - **Count** → number of calls, sessions, tickets, orders
        - **Median** → typical value when extreme values should have less influence
        """
    )


c1, c2, c3 = st.columns(3)
with c1:
    date_column = st.selectbox("1. Date / Time", date_columns, key="forecast_date_column_v3")

with c2:
    metric_options = ["Row Count"] + numeric_columns
    metric_column = st.selectbox(
        "2. What do you want to forecast?",
        metric_options,
        key="forecast_metric_column_v3",
        help="Choose Row Count to forecast the number of records per period, such as calls or sessions.",
    )

with c3:
    time_grain_label = st.selectbox(
        "3. Time Grain",
        list(TIME_GRAIN_OPTIONS.keys()),
        index=4,
        key="forecast_time_grain_v3",
        help="Monthly is a common choice for billing. Daily is common for CDRs and sales. Hourly is common for network traffic.",
    )


grain_code = TIME_GRAIN_OPTIONS[time_grain_label]

if metric_column == "Row Count":
    working_df = df.copy()
    working_df["__insightai_row_count__"] = 1
    value_column = "__insightai_row_count__"
    display_metric = "Number of Records"
else:
    working_df = df.copy()
    value_column = metric_column
    display_metric = str(metric_column)

c4, c5, c6 = st.columns(3)
with c4:
    aggregation = st.selectbox(
        "4. Aggregation",
        AGGREGATION_OPTIONS,
        index=0,
        key="forecast_aggregation_v3",
        help="How records in each time period are combined before forecasting.",
    )

with c5:
    if time_grain_label == "Hourly":
        horizon_options = [6, 12, 24, 48, 72, 168]
    elif time_grain_label == "Daily":
        horizon_options = [7, 14, 30, 60, 90]
    elif time_grain_label == "Weekly":
        horizon_options = [4, 8, 12, 26, 52]
    elif time_grain_label == "Monthly":
        horizon_options = [3, 6, 12, 18, 24]
    elif time_grain_label == "Quarterly":
        horizon_options = [2, 4, 8, 12]
    elif time_grain_label == "Yearly":
        horizon_options = [1, 2, 3, 5]
    else:
        horizon_options = [7, 14, 30, 60, 90]

    horizon = st.selectbox(
        "5. Future Periods",
        horizon_options,
        index=min(2, len(horizon_options) - 1),
        key="forecast_horizon_v3",
    )

with c6:
    model_choice = st.selectbox(
        "6. Forecast Model",
        ["Auto", "Holt-Winters", "Random Forest", "Seasonal Naive"],
        key="forecast_model_choice_v3",
        help="Auto backtests the available models and selects the strongest historical fit.",
    )


# Prepare a preview before the user runs the full forecast.
try:
    prepared_preview = prepare_time_series(
        working_df,
        date_column,
        value_column,
        time_grain=grain_code,
        aggregation=aggregation,
    )
except Exception as exc:
    st.error(f"Unable to prepare the selected time series: {exc}")
    st.stop()


if len(prepared_preview) < 5:
    st.warning(
        f"Only {len(prepared_preview)} time periods are available after aggregation. "
        "At least 5 are required; 12+ periods are preferable for a useful forecast."
    )
else:
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Historical Periods", f"{len(prepared_preview):,}")
    p2.metric("First Period", str(prepared_preview[date_column].iloc[0]))
    p3.metric("Last Period", str(prepared_preview[date_column].iloc[-1]))
    p4.metric("History Avg", f"{prepared_preview[value_column].mean():,.2f}")

    if len(prepared_preview) < 12:
        st.info("💡 The forecast can run, but a longer history will generally make trend/seasonality evaluation more informative.")


# Show the exact series InsightAI is going to forecast. This removes the
# biggest source of confusion when the source dataset contains transactions.
with st.expander("🔎 Preview the actual series that will be forecast", expanded=False):
    st.dataframe(prepared_preview.tail(30), use_container_width=True, hide_index=True)
    st.caption(
        f"InsightAI is forecasting **{display_metric}** at **{time_grain_label}** grain using **{aggregation}** aggregation."
    )


# ------------------------------------------------------------------
# Generate forecast
# ------------------------------------------------------------------

config_signature = (
    str(st.session_state.get("active_dataset")),
    date_column,
    value_column,
    time_grain_label,
    aggregation,
    int(horizon),
    model_choice,
)

if st.session_state.get("forecast_config_signature_v3") != config_signature:
    st.session_state["forecast_result_v3"] = None

if st.button("🚀 Generate Forecast", type="primary", use_container_width=True, key="generate_forecast_v3"):
    st.session_state["forecast_result_v3"] = None
    with st.spinner("Preparing the time series, backtesting models and forecasting the future..."):
        try:
            st.session_state["forecast_result_v3"] = build_forecast(
                working_df,
                date_column,
                value_column,
                forecast_periods=int(horizon),
                model_name=model_choice,
                time_grain=grain_code,
                aggregation=aggregation,
            )
            st.session_state["forecast_config_signature_v3"] = config_signature
        except Exception as exc:
            st.error(f"Forecast model could not be built: {exc}")
            st.exception(exc)

result = st.session_state.get("forecast_result_v3")

if result is None:
    st.info("Complete the six selections above and click **Generate Forecast**. The preview shows exactly what InsightAI will forecast.")
    st.stop()

forecast = result["forecast"].copy()
forecast_date = date_column
forecast_value = "forecast"
model_name = result["model_name"]
auto_best = result.get("auto_best_model", model_name)
diagnostics = result["diagnostics"]


# ------------------------------------------------------------------
# Model / diagnostics summary
# ------------------------------------------------------------------

st.markdown('<div class="section-title">🧠 Forecast Intelligence</div>', unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Selected Model", model_name)
s2.metric("Time Grain", time_grain_label)
s3.metric("Aggregation", aggregation)
s4.metric("Seasonal Pattern", f"{result.get('seasonal_period', 1)} periods")

final_change = diagnostics.get("final_change_pct")
s5.metric("End vs Latest", f"{final_change:+.2f}%" if final_change is not None else "N/A")


# ------------------------------------------------------------------
# Main forecast chart
# ------------------------------------------------------------------

st.markdown('<div class="section-title">📈 Historical + Forecast + 95% Range</div>', unsafe_allow_html=True)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=prepared_preview[date_column],
        y=prepared_preview[value_column],
        mode="lines+markers",
        name="Historical",
        line=dict(width=2.5),
        marker=dict(size=5),
    )
)

fig.add_trace(
    go.Scatter(
        x=forecast[forecast_date],
        y=forecast["upper_bound"],
        mode="lines",
        line=dict(width=0),
        name="Upper 95%",
        showlegend=False,
        hoverinfo="skip",
    )
)

fig.add_trace(
    go.Scatter(
        x=forecast[forecast_date],
        y=forecast["lower_bound"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        name="95% prediction range",
        hoverinfo="skip",
    )
)

fig.add_trace(
    go.Scatter(
        x=forecast[forecast_date],
        y=forecast[forecast_value],
        mode="lines+markers",
        name="Forecast",
        line=dict(width=3, dash="dash"),
        marker=dict(size=7),
    )
)

fig.update_layout(
    height=540,
    margin=dict(l=20, r=20, t=30, b=20),
    hovermode="x unified",
    legend=dict(orientation="h", y=1.05),
    xaxis_title="Date / Time",
    yaxis_title=display_metric,
)

st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# Trend interpretation
# ------------------------------------------------------------------

st.markdown('<div class="section-title">💡 What the Forecast Says</div>', unsafe_allow_html=True)

recent_change = diagnostics.get("recent_change_pct")
forecast_mean = diagnostics.get("forecast_mean")

if final_change is not None:
    if final_change > 10:
        direction = "upward"
    elif final_change < -10:
        direction = "downward"
    else:
        direction = "relatively stable"
else:
    direction = "uncertain"

message = (
    f"The selected model is **{model_name}**. The forecast is **{direction}** "
    f"over the next **{horizon} {time_grain_label.lower()} periods**. "
    f"The projected average is approximately **{forecast_mean:,.2f}**."
)
if auto_best:
    message += f" Historical holdout testing identified **{auto_best}** as the strongest available automatic model."
if recent_change is not None:
    message += f" The recent historical movement was approximately **{recent_change:+.2f}%** across the latest comparison window."

st.markdown(f'<div class="insight-box">{message}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# Model comparison
# ------------------------------------------------------------------

st.markdown('<div class="section-title">🏆 Model Comparison</div>', unsafe_allow_html=True)

scores = result.get("model_scores", {})
if scores:
    rows = []
    for name, metrics in scores.items():
        rows.append(
            {
                "Model": name,
                "MAE": metrics.get("mae"),
                "RMSE": metrics.get("rmse"),
                "MAPE %": metrics.get("mape"),
                "R²": metrics.get("r2"),
            }
        )
    comparison = pd.DataFrame(rows).sort_values("MAPE %", na_position="last")
    st.dataframe(
        comparison.style.format(
            {
                "MAE": "{:,.2f}",
                "RMSE": "{:,.2f}",
                "MAPE %": "{:,.2f}",
                "R²": "{:,.3f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("MAE, RMSE and MAPE measure historical prediction error on a chronological holdout. Lower error is generally better. R² is additional context, not a guarantee of future performance.")
else:
    st.info("The series is too short for a reliable model comparison.")


# ------------------------------------------------------------------
# Forecast KPIs
# ------------------------------------------------------------------

st.markdown('<div class="section-title">📊 Forecast Summary</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)
f1.metric("Forecast Points", f"{len(forecast):,}")
f2.metric("First Forecast", f"{forecast['forecast'].iloc[0]:,.2f}")
f3.metric("Final Forecast", f"{forecast['forecast'].iloc[-1]:,.2f}")
f4.metric("Forecast Average", f"{forecast['forecast'].mean():,.2f}")


# ------------------------------------------------------------------
# Accuracy
# ------------------------------------------------------------------

st.markdown('<div class="section-title">🎯 Historical Backtest Accuracy</div>', unsafe_allow_html=True)

accuracy = calculate_model_accuracy(
    working_df,
    date_column,
    value_column,
    time_grain=grain_code,
    aggregation=aggregation,
)
a1, a2, a3, a4 = st.columns(4)
for col, label, key, suffix in [
    (a1, "MAE", "mae", ""),
    (a2, "RMSE", "rmse", ""),
    (a3, "MAPE", "mape", "%"),
    (a4, "R²", "r2", ""),
]:
    value = accuracy.get(key)
    with col:
        if value is None or not np.isfinite(value):
            st.metric(label, "N/A")
        else:
            st.metric(label, f"{value:,.2f}{suffix}")


# ------------------------------------------------------------------
# Forecast table + download
# ------------------------------------------------------------------

st.markdown('<div class="section-title">📋 Forecast Values</div>', unsafe_allow_html=True)

display_forecast = forecast.copy()
display_forecast[forecast_date] = display_forecast[forecast_date].dt.strftime("%Y-%m-%d %H:%M")
st.dataframe(display_forecast, use_container_width=True, hide_index=True)

csv_data = forecast.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download Forecast CSV",
    data=csv_data,
    file_name="insightai_intelligent_forecast.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(
    "Prediction ranges are model-based uncertainty estimates, not guarantees. "
    "For business use, compare the backtest accuracy with the cost of being wrong and review the historical series before acting on the forecast."
)
