"""
Forecasting facade.

This file intentionally keeps the existing forecasting implementation
compatible while exposing a clean accuracy interface.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def find_date_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return str(col)

    for col in df.columns:
        name = str(col).lower()
        if any(x in name for x in ("date", "time", "timestamp")):
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().mean() >= 0.70:
                return str(col)
    return None


def prepare_time_series(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
) -> pd.DataFrame:
    prepared = df[[date_column, value_column]].copy()
    prepared[date_column] = pd.to_datetime(
        prepared[date_column],
        errors="coerce",
    )
    prepared[value_column] = pd.to_numeric(
        prepared[value_column],
        errors="coerce",
    )
    prepared = prepared.dropna()
    prepared = (
        prepared.groupby(date_column, as_index=False)[value_column]
        .sum()
        .sort_values(date_column)
        .reset_index(drop=True)
    )
    return prepared


def _feature_frame(dates: pd.Series) -> pd.DataFrame:
    dates = pd.to_datetime(dates)
    return pd.DataFrame(
        {
            "year": dates.dt.year,
            "month": dates.dt.month,
            "day": dates.dt.day,
            "dayofweek": dates.dt.dayofweek,
            "dayofyear": dates.dt.dayofyear,
            "weekofyear": dates.dt.isocalendar().week.astype(int),
            "trend": np.arange(len(dates)),
        }
    )


def build_forecast(
    df: pd.DataFrame,
    date_column: str,
    value_column: str,
    forecast_periods: int = 7,
) -> dict[str, Any]:
    prepared = prepare_time_series(df, date_column, value_column)

    if len(prepared) < 5:
        raise ValueError("At least 5 valid time-series observations are required.")

    model = RandomForestRegressor(
        n_estimators=250,
        random_state=42,
        n_jobs=-1,
    )

    X = _feature_frame(prepared[date_column])
    y = prepared[value_column].to_numpy()
    model.fit(X, y)

    frequency = pd.infer_freq(prepared[date_column])
    if frequency is None:
        deltas = prepared[date_column].diff().dropna()
        step = deltas.median()
    else:
        step = None

    future_dates = []
    last_date = prepared[date_column].iloc[-1]

    if frequency:
        future_dates = list(
            pd.date_range(
                start=last_date,
                periods=forecast_periods + 1,
                freq=frequency,
            )[1:]
        )
    else:
        if pd.isna(step) or step <= pd.Timedelta(0):
            step = pd.Timedelta(days=1)
        future_dates = [
            last_date + step * i
            for i in range(1, forecast_periods + 1)
        ]

    future_dates = pd.to_datetime(future_dates)
    future_X = _feature_frame(future_dates)
    predictions = model.predict(future_X)

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
    """Simple holdout evaluation with the same feature family."""
    prepared = prepare_time_series(df, date_column, value_column)

    if len(prepared) < 10:
        return {"mae": None, "mape": None, "r2": None}

    split = max(int(len(prepared) * 0.8), 5)
    train = prepared.iloc[:split]
    test = prepared.iloc[split:]

    if test.empty:
        return {"mae": None, "mape": None, "r2": None}

    model = RandomForestRegressor(
        n_estimators=250,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        _feature_frame(train[date_column]),
        train[value_column],
    )

    predictions = model.predict(_feature_frame(test[date_column]))
    actual = test[value_column].to_numpy()

    mae = float(np.mean(np.abs(actual - predictions)))
    nonzero = actual != 0
    mape = (
        float(
            np.mean(
                np.abs(
                    (actual[nonzero] - predictions[nonzero])
                    / actual[nonzero]
                )
            )
            * 100
        )
        if nonzero.any()
        else None
    )

    ss_res = float(np.sum((actual - predictions) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else None

    return {"mae": mae, "mape": mape, "r2": r2}
