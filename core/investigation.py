"""Deterministic investigation engine for InsightAI.

Builds an evidence package from existing InsightAI engines. It never asks an
LLM to calculate metrics; an LLM may only summarize the evidence package.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from core.anomaly import detect_anomalies, explain_anomalies
from core.analytics import analyze_dataset
from core.calculated_metrics import _metric_definition, calculate_metric_series


def _numeric_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for col in df.select_dtypes(include=np.number).columns:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append({
            "column": str(col),
            "count": int(s.count()),
            "mean": float(s.mean()),
            "min": float(s.min()),
            "max": float(s.max()),
            "std": float(s.std()) if len(s) > 1 else 0.0,
        })
    return rows


def _correlations(df: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    numeric = df.select_dtypes(include=np.number)
    if numeric.shape[1] < 2:
        return []
    corr = numeric.corr(numeric_only=True)
    pairs: list[dict[str, Any]] = []
    cols = list(corr.columns)
    for i, left in enumerate(cols):
        for right in cols[i + 1:]:
            value = corr.loc[left, right]
            if pd.isna(value):
                continue
            pairs.append({"left": str(left), "right": str(right), "correlation": float(value)})
    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return pairs[:limit]


def _time_columns(df: pd.DataFrame) -> list[str]:
    found = []
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            found.append(str(col))
            continue
        if not any(t in str(col).lower() for t in ("date", "time", "timestamp", "datetime", "month", "year")):
            continue
        parsed = pd.to_datetime(s, errors="coerce")
        if parsed.notna().mean() >= 0.60:
            found.append(str(col))
    return found


def _trend_evidence(df: pd.DataFrame) -> dict[str, Any]:
    dates = _time_columns(df)
    numeric = list(df.select_dtypes(include=np.number).columns)
    if not dates or not numeric:
        return {"available": False, "reason": "No suitable date/time and numeric metric pair found."}
    date_col = dates[0]
    metric = numeric[0]
    work = df[[date_col, metric]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna().sort_values(date_col)
    if len(work) < 4:
        return {"available": False, "reason": "Not enough time observations."}
    grouped = work.set_index(date_col)[metric].resample("ME").sum().dropna()
    if len(grouped) < 2:
        grouped = work.groupby(date_col)[metric].sum().sort_index()
    if len(grouped) < 2:
        return {"available": False, "reason": "Not enough distinct periods."}
    latest = float(grouped.iloc[-1])
    previous = float(grouped.iloc[-2])
    change = ((latest - previous) / abs(previous) * 100) if previous else 0.0
    peak_period = grouped.idxmax()
    low_period = grouped.idxmin()
    return {
        "available": True,
        "date_column": date_col,
        "metric": str(metric),
        "periods": int(len(grouped)),
        "latest": latest,
        "previous": previous,
        "change_pct": float(change),
        "peak_period": str(peak_period),
        "peak_value": float(grouped.max()),
        "low_period": str(low_period),
        "low_value": float(grouped.min()),
    }


def build_investigation(df: pd.DataFrame, dataset_name: str = "Active Dataset") -> dict[str, Any]:
    """Create a cross-engine evidence package for an investigation."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("An active, non-empty dataframe is required.")

    analysis = analyze_dataset(df)
    health = analysis.get("health", {})

    anomaly_df, anomaly_summary = detect_anomalies(
        df,
        method="isolation_forest",
        contamination=0.05,
    )
    anomaly_explanations = explain_anomalies(df, anomaly_df)

    metric_evidence = None
    try:
        definition = _metric_definition(df, "What is the total sales value")
        if definition:
            values = pd.to_numeric(calculate_metric_series(df, definition), errors="coerce")
            metric_evidence = {
                "metric": definition.get("label", definition.get("name")),
                "formula": definition.get("formula"),
                "fields": definition.get("columns", []),
                "total": float(values.sum()),
                "valid_rows": int(values.notna().sum()),
            }
    except Exception:
        metric_evidence = None

    return {
        "dataset": dataset_name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "health": {
            "quality_score": float(health.get("quality_score", 0) or 0),
            "completeness": float(health.get("completeness", 0) or 0),
            "missing_values": int(health.get("missing_values", 0) or 0),
            "duplicate_rows": int(health.get("duplicate_rows", 0) or 0),
        },
        "metric": metric_evidence,
        "numeric_summary": _numeric_summary(df),
        "correlations": _correlations(df),
        "anomalies": {
            **anomaly_summary,
            "examples": anomaly_df.head(10).to_dict(orient="records"),
            "explanations": anomaly_explanations,
        },
        "trend": _trend_evidence(df),
        "findings": analysis.get("findings", [])[:10],
    }


def investigation_prompt(evidence: dict[str, Any]) -> str:
    """Build an evidence-grounded prompt for an AI narrative."""
    return f"""You are InsightAI Investigation Mode.

Use ONLY the deterministic evidence below. Do not invent causes, numbers, or relationships.
Clearly label a possible cause as a hypothesis when the evidence does not prove causality.

EVIDENCE:
{evidence}

Respond with exactly these sections:
### What happened?
Summarize the most important observed facts.

### Why does it matter?
Explain the business/operational significance supported by the evidence.

### What should I investigate next?
Give 3-5 concrete follow-up investigations using available fields or modules.

### Evidence to verify
List the key metrics, anomalies, trends, or relationships that support the response.
"""
