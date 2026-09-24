"""Forecasting engine for InsightAI.

Provides a stable API used by the Forecasting Streamlit page.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that contain enough values to be interpreted as dates."""
    if df is None or df.empty:
        return []

    result: list[str] = []

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            result.append(str(col))
            continue

        name = str(col).lower()
        name_hint = any(
            token in name
            for token in ("date", "time", "timestamp", "datetime", "month", "year")
        )

        parsed = pd.to_datetime(series, errors="coerce")
        valid_ratio = float(parsed.notna().mean()) if len(series) else 0.0

        # For columns with an obvious date/time name, allow a lower threshold.
        threshold = 0.60 if name_hint else 0.80
        if valid_ratio >= threshold and parsed.notna().sum() >= 5:
            # Reject numeric columns that pandas interpreted as nanoseconds.
            if pd.api.types.is_numeric_dtype(series) and not name_hint:
                continue
            result.append(str(col))

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(result))


def find_date_column(df: pd.DataFrame) -> str | None:
    columns = detect_datetime_columns(df)
    return columns[0] if columns else None


def prepare_time_series(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
) -> pd.DataFrame:
    if date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' was not found.")
    if value_column not in df.columns:
        raise ValueError(f"Metric column '{value_column}' was not found.")

    prepared = df[[date_column, value_column]].copy()
    prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")
    prepared[value_column] = pd.to_numeric(prepared[value_column], errors="coerce")
    prepared = prepared.dropna(subset=[date_column, value_column])

    if prepared.empty:
        return prepared

    prepared = (
        prepared.groupby(date_column, as_index=False)[value_column]
        .sum()
        .sort_values(date_column)
        .reset_index(drop=True)
    )
    return prepared


def _feature_frame(dates: pd.Series) -> pd.DataFrame:
    dates = pd.to_datetime(dates)
    iso_week = dates.dt.isocalendar().week.astype(int)
    return pd.DataFrame(
        {
            "year": dates.dt.year.astype(int),
            "month": dates.dt.month.astype(int),
            "day": dates.dt.day.astype(int),
            "dayofweek": dates.dt.dayofweek.astype(int),
            "dayofyear": dates.dt.dayofyear.astype(int),
            "weekofyear": iso_week,
            "trend": np.arange(len(dates), dtype=float),
        },
        index=dates.index,
    )


def _future_dates(prepared: pd.DataFrame, date_column: str, periods: int) -> pd.DatetimeIndex:
    last_date = prepared[date_column].iloc[-1]
    frequency = pd.infer_freq(prepared[date_column]) if len(prepared) >= 3 else None

    if frequency:
        return pd.date_range(
            start=last_date,
            periods=periods + 1,
            freq=frequency,
        )[1:]

    deltas = prepared[date_column].diff().dropna()
    step = deltas.median() if not deltas.empty else pd.Timedelta(days=1)
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(days=1)

    return pd.DatetimeIndex([last_date + step * i for i in range(1, periods + 1)])


def build_forecast(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    forecast_periods: int = 7,
) -> dict[str, Any]:
    if forecast_periods < 1:
        raise ValueError("Forecast horizon must be at least 1.")

    prepared = prepare_time_series(df, date_column, value_column)
    if len(prepared) < 5:
        raise ValueError("At least 5 valid time-series observations are required.")

    model = RandomForestRegressor(
        n_estimators=250,
        random_state=42,
        n_jobs=-1,
    )

    X = _feature_frame(prepared[date_column])
    y = prepared[value_column].to_numpy(dtype=float)
    model.fit(X, y)

    future_dates = _future_dates(prepared, date_column, int(forecast_periods))
    predictions = model.predict(_feature_frame(pd.Series(future_dates)))

    forecast = pd.DataFrame(
        {
            date_column: future_dates,
            "forecast": predictions,
        }
    )

    return {
        "prepared": prepared,
        "model": model,
        "forecast": forecast,
        "date_column": date_column,
        "value_column": value_column,
    }


def calculate_model_accuracy(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
) -> dict[str, float | None]:
    prepared = prepare_time_series(df, date_column, value_column)

    if len(prepared) < 10:
        return {"mae": None, "mape": None, "r2": None}

    split = max(int(len(prepared) * 0.8), 5)
    if split >= len(prepared):
        split = len(prepared) - 1

    train = prepared.iloc[:split]
    test = prepared.iloc[split:]

    if train.empty or test.empty:
        return {"mae": None, "mape": None, "r2": None}

    model = RandomForestRegressor(
        n_estimators=250,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(_feature_frame(train[date_column]), train[value_column].to_numpy(dtype=float))

    predictions = model.predict(_feature_frame(test[date_column]))
    actual = test[value_column].to_numpy(dtype=float)

    mae = float(np.mean(np.abs(actual - predictions)))
    nonzero = actual != 0
    mape = (
        float(np.mean(np.abs((actual[nonzero] - predictions[nonzero]) / actual[nonzero])) * 100)
        if nonzero.any()
        else None
    )

    ss_res = float(np.sum((actual - predictions) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else None

    return {"mae": mae, "mape": mape, "r2": r2}
