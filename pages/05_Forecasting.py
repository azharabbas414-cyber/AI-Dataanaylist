from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.forecasting import (
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
        <p>Discover trend, seasonality and future movement in <b>{dataset_name}</b> — with automatic model selection and uncertainty ranges.</p>
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

if not numeric_columns:
    st.warning("No suitable numeric metric was found for forecasting.")
    st.stop()


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

st.markdown('<div class="section-title">⚙️ Forecast Setup</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1.35, 1.35, 1, 1.2])

with c1:
    date_column = st.selectbox("Date / Time", date_columns, key="forecast_date_column_v2")

with c2:
    metric_column = st.selectbox("Metric", numeric_columns, key="forecast_metric_column_v2")

with c3:
    horizon = st.selectbox("Future periods", [7, 14, 30, 60, 90], index=2, key="forecast_horizon_v2")

with c4:
    model_choice = st.selectbox(
        "Forecast model",
        ["Auto", "Holt-Winters", "Random Forest", "Seasonal Naive"],
        key="forecast_model_choice_v2",
        help="Auto evaluates the available models on a chronological holdout and selects the strongest historical fit.",
    )


try:
    prepared = prepare_time_series(df, date_column, metric_column)
except Exception as exc:
    st.error(f"Unable to prepare the time series: {exc}")
    st.stop()

if len(prepared) < 5:
    st.warning("At least 5 valid time-series observations are required.")
    st.stop()

latest_value = float(prepared[metric_column].iloc[-1])
first_value = float(prepared[metric_column].iloc[0])


# ------------------------------------------------------------------
# Historical KPI cards
# ------------------------------------------------------------------

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Observations", f"{len(prepared):,}")
k2.metric("Latest", f"{latest_value:,.2f}")
k3.metric("Average", f"{prepared[metric_column].mean():,.2f}")
k4.metric("Minimum", f"{prepared[metric_column].min():,.2f}")
k5.metric("Maximum", f"{prepared[metric_column].max():,.2f}")


# ------------------------------------------------------------------
# Generate
# ------------------------------------------------------------------

if st.button("🚀 Generate Intelligent Forecast", type="primary", use_container_width=True):
    st.session_state["forecast_result_v2"] = None
    with st.spinner("Testing forecasting patterns and building the prediction..."):
        try:
            st.session_state["forecast_result_v2"] = build_forecast(
                prepared,
                date_column,
                metric_column,
                forecast_periods=int(horizon),
                model_name=model_choice,
            )
        except Exception as exc:
            st.error(f"Forecast model could not be built: {exc}")
            st.exception(exc)

result = st.session_state.get("forecast_result_v2")

if result is None:
    st.info("Choose your fields and click **Generate Intelligent Forecast** to begin.")
    st.stop()

forecast = result["forecast"].copy()
forecast_date = date_column
forecast_value = "forecast"


# ------------------------------------------------------------------
# Model / diagnostics summary
# ------------------------------------------------------------------

model_name = result["model_name"]
auto_best = result.get("auto_best_model", model_name)
diagnostics = result["diagnostics"]

st.markdown('<div class="section-title">🧠 Forecast Intelligence</div>', unsafe_allow_html=True)

s1, s2, s3, s4 = st.columns(4)
s1.metric("Selected Model", model_name)
s2.metric("Detected Frequency", str(result.get("frequency") or "Irregular"))
s3.metric("Seasonal Pattern", f"{result.get('seasonal_period', 1)} periods")

final_change = diagnostics.get("final_change_pct")
with s4:
    st.metric(
        "End vs Latest",
        f"{final_change:+.2f}%" if final_change is not None else "N/A",
    )


# ------------------------------------------------------------------
# Main forecast chart
# ------------------------------------------------------------------

st.markdown('<div class="section-title">📈 Historical + Forecast + 95% Range</div>', unsafe_allow_html=True)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=prepared[date_column],
        y=prepared[metric_column],
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
    yaxis_title=str(metric_column),
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
    f"over the selected horizon. The projected average is approximately "
    f"**{forecast_mean:,.2f}**."
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
    st.caption("Lower MAE/RMSE/MAPE generally indicates better historical holdout performance; R² is provided as additional context.")
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

accuracy = calculate_model_accuracy(prepared, date_column, metric_column)
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
    "Use the historical backtest metrics and business context when interpreting the forecast."
)
