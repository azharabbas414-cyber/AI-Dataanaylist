"""InsightAI forecasting engine.

The forecasting layer converts raw observations into a regular time series,
backtests multiple models, selects a model when requested, and produces a
future forecast with a practical uncertainty range.

The important product concept is:
    Raw data -> choose time grain -> aggregate a metric -> forecast the series.

This makes the module usable for transactional data such as telecom billing,
CDRs, sales and network KPI data instead of requiring the source dataset to
already be a clean time series.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing, Holt
except Exception:  # pragma: no cover - optional runtime dependency
    ExponentialSmoothing = None
    Holt = None


TIME_GRAIN_OPTIONS = {
    "Auto": None,
    "Hourly": "h",
    "Daily": "D",
    "Weekly": "W",
    "Monthly": "ME",
    "Quarterly": "QE",
    "Yearly": "YE",
}

AGGREGATION_OPTIONS = ["Sum", "Mean", "Median", "Min", "Max", "Count"]


def detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that contain enough valid datetime values."""
    result: list[str] = []

    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            result.append(str(column))
            continue

        name = str(column).lower()
        looks_like_time = any(
            token in name
            for token in ("date", "time", "timestamp", "datetime", "month", "year")
        )
        if not looks_like_time:
            continue

        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().mean() >= 0.60:
            result.append(str(column))

    return result


def _normalise_grain(grain: str | None) -> str | None:
    if grain is None:
        return None
    text = str(grain).strip().lower()
    aliases = {
        "auto": None,
        "hour": "h",
        "hourly": "h",
        "day": "D",
        "daily": "D",
        "week": "W",
        "weekly": "W",
        "month": "ME",
        "monthly": "ME",
        "quarter": "QE",
        "quarterly": "QE",
        "year": "YE",
        "yearly": "YE",
    }
    return aliases.get(text, grain)


def _aggregate_series(values: pd.Series, aggregation: str) -> pd.Series:
    aggregation = str(aggregation or "Sum").strip().lower()
    if aggregation == "sum":
        return values.resample("D").sum()  # replaced by caller when needed
    if aggregation == "mean":
        return values.resample("D").mean()
    if aggregation == "median":
        return values.resample("D").median()
    if aggregation == "min":
        return values.resample("D").min()
    if aggregation == "max":
        return values.resample("D").max()
    if aggregation == "count":
        return values.resample("D").count()
    raise ValueError(f"Unsupported aggregation: {aggregation}")


def prepare_time_series(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    time_grain: str | None = "Auto",
    aggregation: str = "Sum",
) -> pd.DataFrame:
    """Convert raw records into one regular observation per selected period.

    Parameters
    ----------
    time_grain:
        Auto, Hourly, Daily, Weekly, Monthly, Quarterly or Yearly. Auto keeps
        the observed timestamps; the UI should normally use an explicit grain
        for transaction-level data.
    aggregation:
        Sum, Mean, Median, Min, Max or Count.
    """
    if date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' was not found.")
    if value_column not in df.columns:
        raise ValueError(f"Metric column '{value_column}' was not found.")

    prepared = df[[date_column, value_column]].copy()
    prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")
    prepared[value_column] = pd.to_numeric(prepared[value_column], errors="coerce")
    prepared = prepared.dropna(subset=[date_column])

    # Count is useful for CDR/billing rows even when the selected field is not
    # numeric. Other aggregations require a numeric metric.
    if str(aggregation).lower() != "count":
        prepared = prepared.dropna(subset=[value_column])

    if prepared.empty:
        return prepared

    prepared = prepared.sort_values(date_column).reset_index(drop=True)
    grain = _normalise_grain(time_grain)

    if grain is None:
        # Auto mode keeps the original timestamp granularity but combines
        # duplicate timestamps. This is backward compatible with the earlier
        # engine and is most appropriate when the data is already periodic.
        if str(aggregation).lower() == "count":
            grouped = prepared.groupby(date_column, as_index=False).size()
            grouped = grouped.rename(columns={"size": value_column})
        else:
            grouped = (
                prepared.groupby(date_column, as_index=False)[value_column]
                .agg(str(aggregation).lower())
            )
        return grouped.sort_values(date_column).reset_index(drop=True)

    indexed = prepared.set_index(date_column)
    numeric = indexed[value_column]
    agg_name = str(aggregation).lower()

    if agg_name == "count":
        series = numeric.resample(grain).count()
    elif agg_name == "sum":
        series = numeric.resample(grain).sum()
    elif agg_name == "mean":
        series = numeric.resample(grain).mean()
    elif agg_name == "median":
        series = numeric.resample(grain).median()
    elif agg_name == "min":
        series = numeric.resample(grain).min()
    elif agg_name == "max":
        series = numeric.resample(grain).max()
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation}")

    series = series.dropna()
    result = series.rename(value_column).reset_index()
    return result.sort_values(date_column).reset_index(drop=True)


def _infer_frequency(dates: pd.Series) -> tuple[str | None, pd.Timedelta]:
    dates = pd.to_datetime(dates).sort_values()
    frequency = pd.infer_freq(dates) if len(dates) >= 3 else None

    deltas = dates.diff().dropna()
    step = deltas.median() if not deltas.empty else pd.Timedelta(days=1)
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(days=1)

    return frequency, step


def _seasonal_period(frequency: str | None, step: pd.Timedelta) -> int:
    if frequency:
        f = str(frequency).upper()
        if f.startswith("H") or "HOUR" in f:
            return 24
        if f.startswith("D") or "DAY" in f:
            return 7
        if f.startswith("W") or "WEEK" in f:
            return 52
        if f.startswith("M") or "MONTH" in f:
            return 12
        if f.startswith("Q") or "QUARTER" in f:
            return 4
        if f.startswith("Y") or "YEAR" in f:
            return 1

    days = step.total_seconds() / 86400
    if 0.03 <= days <= 0.06:
        return 24
    if 0.75 <= days <= 1.25:
        return 7
    if 6 <= days <= 8:
        return 52
    if 27 <= days <= 32:
        return 12
    if 80 <= days <= 100:
        return 4
    return 1


def _future_dates(
    last_date: pd.Timestamp,
    horizon: int,
    frequency: str | None,
    step: pd.Timedelta,
) -> pd.DatetimeIndex:
    if frequency:
        try:
            return pd.date_range(start=last_date, periods=horizon + 1, freq=frequency)[1:]
        except Exception:
            pass

    return pd.DatetimeIndex([last_date + step * i for i in range(1, horizon + 1)])


def _seasonal_naive(values: np.ndarray, horizon: int, season: int) -> np.ndarray:
    if len(values) >= season and season > 1:
        pattern = values[-season:]
        return np.resize(pattern, horizon).astype(float)
    return np.repeat(float(values[-1]), horizon)


def _holt_forecast(values: np.ndarray, horizon: int, season: int) -> np.ndarray:
    if ExponentialSmoothing is None or len(values) < 8:
        if Holt is None or len(values) < 5:
            raise ValueError("Statsmodels smoothing is unavailable or the series is too short.")
        return np.asarray(
            Holt(values, damped_trend=True).fit(optimized=True).forecast(horizon),
            dtype=float,
        )

    if season > 1 and len(values) >= max(2 * season, 12):
        model = ExponentialSmoothing(
            values,
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=season,
            initialization_method="estimated",
        )
    else:
        model = ExponentialSmoothing(
            values,
            trend="add",
            damped_trend=True,
            initialization_method="estimated",
        )

    fitted = model.fit(optimized=True, remove_bias=True)
    return np.asarray(fitted.forecast(horizon), dtype=float)


def _rf_features(
    values: np.ndarray,
    dates: pd.DatetimeIndex,
    season: int,
) -> tuple[pd.DataFrame, np.ndarray]:
    rows = []
    targets = []
    lags = sorted(
        set(
            [
                1,
                2,
                3,
                season,
                min(7, max(1, season)),
                min(14, max(1, season * 2)),
            ]
        )
    )
    max_lag = max(lags)

    for i in range(max_lag, len(values)):
        row = {
            "trend": i,
            "month": dates[i].month,
            "dayofweek": dates[i].dayofweek,
            "dayofyear": dates[i].dayofyear,
        }
        for lag in lags:
            row[f"lag_{lag}"] = values[i - lag]
        row["roll_mean_3"] = float(np.mean(values[max(0, i - 3) : i]))
        row["roll_mean_7"] = float(np.mean(values[max(0, i - 7) : i]))
        rows.append(row)
        targets.append(values[i])

    return pd.DataFrame(rows), np.asarray(targets, dtype=float)


def _rf_recursive_forecast(
    values: np.ndarray,
    dates: pd.DatetimeIndex,
    future_dates: pd.DatetimeIndex,
    season: int,
) -> np.ndarray:
    X, y = _rf_features(values, dates, season)
    if len(X) < 8:
        raise ValueError("Not enough history for the lag-based model.")

    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y)

    history = list(values.astype(float))
    predictions: list[float] = []
    lags = sorted(
        set(
            [
                1,
                2,
                3,
                season,
                min(7, max(1, season)),
                min(14, max(1, season * 2)),
            ]
        )
    )

    for date in future_dates:
        i = len(history)
        row = {
            "trend": i,
            "month": date.month,
            "dayofweek": date.dayofweek,
            "dayofyear": date.dayofyear,
        }
        for lag in lags:
            row[f"lag_{lag}"] = history[-lag] if len(history) >= lag else history[-1]
        row["roll_mean_3"] = float(np.mean(history[-3:]))
        row["roll_mean_7"] = float(np.mean(history[-7:]))
        pred = float(model.predict(pd.DataFrame([row], columns=X.columns))[0])
        predictions.append(pred)
        history.append(pred)

    return np.asarray(predictions, dtype=float)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    error = actual - predicted
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    nonzero = actual != 0
    mape = (
        float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100)
        if nonzero.any()
        else None
    )
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    ss_res = float(np.sum(error**2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot else None
    return {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2}


def _evaluate_models(
    prepared: pd.DataFrame,
    date_column: str,
    value_column: str,
    season: int,
) -> tuple[dict[str, dict[str, float | None]], str, np.ndarray]:
    values = prepared[value_column].to_numpy(dtype=float)
    dates = pd.DatetimeIndex(prepared[date_column])
    if len(values) < 10:
        return {}, "Seasonal Naive", _seasonal_naive(values, 1, season)

    test_size = max(3, min(14, int(round(len(values) * 0.20))))
    if len(values) - test_size < 5:
        test_size = max(1, len(values) - 5)

    train_values = values[:-test_size]
    test_values = values[-test_size:]
    train_dates = dates[:-test_size]
    test_dates = dates[-test_size:]

    candidates: dict[str, np.ndarray] = {}
    candidates["Seasonal Naive"] = _seasonal_naive(train_values, test_size, season)

    try:
        candidates["Holt-Winters"] = _holt_forecast(train_values, test_size, season)
    except Exception:
        pass

    try:
        candidates["Random Forest"] = _rf_recursive_forecast(
            train_values,
            train_dates,
            test_dates,
            season,
        )
    except Exception:
        pass

    scores = {
        name: _metrics(test_values, prediction)
        for name, prediction in candidates.items()
    }

    def score(item: tuple[str, dict[str, float | None]]) -> float:
        mape = item[1].get("mape")
        mae = item[1].get("mae")
        return float(mape if mape is not None else (mae if mae is not None else 1e99))

    best_name = min(scores.items(), key=score)[0]
    return scores, best_name, candidates[best_name]


def build_forecast(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    forecast_periods: int = 7,
    model_name: str = "Auto",
    time_grain: str | None = "Auto",
    aggregation: str = "Sum",
) -> dict[str, Any]:
    prepared = prepare_time_series(
        df,
        date_column,
        value_column,
        time_grain=time_grain,
        aggregation=aggregation,
    )
    if len(prepared) < 5:
        raise ValueError("At least 5 valid time-series observations are required after aggregation.")
    if forecast_periods < 1:
        raise ValueError("Forecast horizon must be at least 1.")

    frequency, step = _infer_frequency(prepared[date_column])
    season = _seasonal_period(frequency, step)
    values = prepared[value_column].to_numpy(dtype=float)
    dates = pd.DatetimeIndex(prepared[date_column])
    future_dates = _future_dates(dates[-1], forecast_periods, frequency, step)

    backtest_scores, auto_best, _ = _evaluate_models(
        prepared,
        date_column,
        value_column,
        season,
    )
    selected = auto_best if model_name == "Auto" else model_name

    if selected == "Seasonal Naive":
        predictions = _seasonal_naive(values, forecast_periods, season)
    elif selected == "Holt-Winters":
        predictions = _holt_forecast(values, forecast_periods, season)
    elif selected == "Random Forest":
        predictions = _rf_recursive_forecast(values, dates, future_dates, season)
    else:
        raise ValueError(f"Unknown forecasting model: {selected}")

    predictions = np.asarray(predictions, dtype=float)
    if np.nanmin(values) >= 0:
        predictions = np.maximum(predictions, 0)

    residual_std = None
    if selected in backtest_scores:
        rmse = backtest_scores[selected].get("rmse")
        if rmse is not None:
            residual_std = float(rmse)
    if residual_std is None:
        residual_std = float(np.std(np.diff(values))) if len(values) > 2 else float(np.std(values))
    if not np.isfinite(residual_std) or residual_std <= 0:
        residual_std = max(float(np.std(values)) * 0.05, 1e-9)

    horizon_scale = np.sqrt(np.arange(1, forecast_periods + 1))
    lower = predictions - 1.96 * residual_std * horizon_scale
    upper = predictions + 1.96 * residual_std * horizon_scale
    if np.nanmin(values) >= 0:
        lower = np.maximum(lower, 0)

    forecast = pd.DataFrame(
        {
            date_column: future_dates,
            "forecast": predictions,
            "lower_bound": lower,
            "upper_bound": upper,
        }
    )

    recent = values[-min(7, len(values)) :]
    recent_mean = float(np.mean(recent))
    base = values[-min(8, len(values))]
    final_change = ((predictions[-1] - values[-1]) / abs(values[-1]) * 100) if values[-1] != 0 else None
    recent_change = ((values[-1] - base) / abs(base) * 100) if len(values) > 1 and base != 0 else None

    diagnostics = {
        "observations": int(len(values)),
        "frequency": frequency or str(step),
        "time_grain": time_grain or "Auto",
        "aggregation": aggregation,
        "seasonal_period": int(season),
        "latest_value": float(values[-1]),
        "historical_mean": float(np.mean(values)),
        "recent_mean": recent_mean,
        "historical_min": float(np.min(values)),
        "historical_max": float(np.max(values)),
        "forecast_mean": float(np.mean(predictions)),
        "final_change_pct": float(final_change) if final_change is not None else None,
        "recent_change_pct": float(recent_change) if recent_change is not None else None,
    }

    return {
        "prepared": prepared,
        "forecast": forecast,
        "model_name": selected,
        "auto_best_model": auto_best,
        "model_scores": backtest_scores,
        "date_column": date_column,
        "value_column": value_column,
        "frequency": frequency,
        "time_grain": time_grain or "Auto",
        "aggregation": aggregation,
        "seasonal_period": season,
        "confidence_level": 95,
        "diagnostics": diagnostics,
        "model": None,
    }


def calculate_model_accuracy(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    time_grain: str | None = "Auto",
    aggregation: str = "Sum",
) -> dict[str, float | None]:
    """Return chronological holdout metrics for the automatically selected model."""
    prepared = prepare_time_series(
        df,
        date_column,
        value_column,
        time_grain=time_grain,
        aggregation=aggregation,
    )
    if len(prepared) < 10:
        return {"mae": None, "rmse": None, "mape": None, "r2": None}

    frequency, step = _infer_frequency(prepared[date_column])
    season = _seasonal_period(frequency, step)
    scores, best, _ = _evaluate_models(prepared, date_column, value_column, season)
    return scores.get(best, {"mae": None, "rmse": None, "mape": None, "r2": None})
