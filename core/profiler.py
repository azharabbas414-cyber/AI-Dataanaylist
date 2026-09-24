"""InsightAI semantic data profiler."""
from __future__ import annotations

from typing import Any
import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or not isinstance(df, pd.DataFrame):
        return {}

    numeric = [str(c) for c in df.select_dtypes(include="number").columns]
    categorical = [str(c) for c in df.select_dtypes(include=["object", "category", "bool"]).columns]
    datetime_cols = [str(c) for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]

    columns: list[dict[str, Any]] = []
    for col in df.columns:
        s = df[col]
        item: dict[str, Any] = {
            "name": str(col),
            "dtype": str(s.dtype),
            "nulls": int(s.isna().sum()),
            "null_percent": round(float(s.isna().mean() * 100), 2),
            "unique": int(s.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(s):
            item.update({
                "min": _safe_number(s.min()),
                "max": _safe_number(s.max()),
                "mean": _safe_number(s.mean()),
                "median": _safe_number(s.median()),
            })
        elif item["unique"] <= 50:
            item["top_values"] = s.astype("string").value_counts(dropna=False).head(10).to_dict()
        columns.append(item)

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "numeric_columns": numeric,
        "categorical_columns": categorical,
        "datetime_columns": datetime_cols,
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "columns_detail": columns,
    }


def _safe_number(value: Any) -> float | int | None:
    if pd.isna(value):
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else round(number, 6)
    except (TypeError, ValueError):
        return None
