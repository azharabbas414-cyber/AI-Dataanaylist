"""
Unified InsightAI anomaly engine.

Methods:
- IQR
- Z-score
- Isolation Forest

The page layer should call this module rather than maintaining separate
anomaly implementations.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def iqr_mask(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    q1 = numeric.quantile(0.25)
    q3 = numeric.quantile(0.75)
    iqr = q3 - q1

    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=series.index)

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return (numeric < lower) | (numeric > upper)


def zscore_mask(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std()

    if pd.isna(std) or std == 0:
        return pd.Series(False, index=series.index)

    z = (numeric - numeric.mean()) / std
    return z.abs() > threshold


def isolation_forest_mask(
    series: pd.Series,
    contamination: float = 0.05,
    random_state: int = 42,
) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.notna()

    result = pd.Series(False, index=series.index)

    if valid.sum() < 10:
        return result

    values = numeric.loc[valid].to_numpy().reshape(-1, 1)
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
    )
    predictions = model.fit_predict(values)
    result.loc[valid] = predictions == -1
    return result


def detect_anomalies(
    df: pd.DataFrame,
    method: str = "iqr",
    columns: list[str] | None = None,
    **kwargs: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return anomaly rows and a summary."""
    if df is None or df.empty:
        return df.copy(), {
            "method": method,
            "total_anomalies": 0,
            "columns": [],
        }

    numeric_columns = [
        str(c) for c in df.select_dtypes(include=np.number).columns
    ]
    selected = columns or numeric_columns
    selected = [c for c in selected if c in df.columns]

    if not selected:
        return df.iloc[0:0].copy(), {
            "method": method,
            "total_anomalies": 0,
            "columns": [],
        }

    combined = pd.Series(False, index=df.index)

    for column in selected:
        if method == "zscore":
            mask = zscore_mask(df[column], kwargs.get("threshold", 3.0))
        elif method == "isolation_forest":
            mask = isolation_forest_mask(
                df[column],
                kwargs.get("contamination", 0.05),
            )
        else:
            mask = iqr_mask(
                df[column],
                kwargs.get("multiplier", 1.5),
            )
        combined |= mask

    anomalies = df.loc[combined].copy()

    return anomalies, {
        "method": method,
        "total_anomalies": int(combined.sum()),
        "percentage": round(float(combined.mean() * 100), 2),
        "columns": selected,
    }


def get_anomaly_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Backward-compatible summary used by existing dashboard code."""
    anomalies, summary = detect_anomalies(df, method="iqr")
    return {
        **summary,
        "anomalies": anomalies,
    }


def explain_anomalies(
    df: pd.DataFrame,
    anomalies: pd.DataFrame,
    max_items: int = 10,
) -> list[str]:
    """Generate deterministic human-readable explanations."""
    if anomalies is None or anomalies.empty:
        return []

    numeric = df.select_dtypes(include=np.number).columns.tolist()
    explanations: list[str] = []

    for column in numeric:
        if column not in anomalies.columns:
            continue

        full = pd.to_numeric(df[column], errors="coerce")
        values = pd.to_numeric(anomalies[column], errors="coerce")

        if values.empty:
            continue

        median = full.median()
        if pd.isna(median) or median == 0:
            continue

        for value in values.head(max_items):
            if pd.isna(value):
                continue
            ratio = abs(float(value) / float(median))
            if ratio >= 3:
                explanations.append(
                    f"{column}: value {value:g} is about {ratio:.1f}× "
                    f"the dataset median."
                )
                break

    return explanations[:max_items]
