"""InsightAI Data Lineage & Evidence Engine.

Deterministic metadata/evidence only. This module does not ask an LLM to
calculate results. It records where a displayed metric can be traced back to:
source dataset, fields, formulas, filters, aggregation, row counts and
recent analytical questions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import pandas as pd


def _dtype_label(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    return "categorical/text"


def build_dataset_lineage(df: pd.DataFrame, dataset_name: str = "Active Dataset") -> dict[str, Any]:
    """Build a deterministic source/profile lineage record for a dataframe."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    columns = []
    for col in df.columns:
        s = df[col]
        columns.append({
            "column": str(col),
            "dtype": str(s.dtype),
            "semantic_type": _dtype_label(s),
            "rows": int(len(df)),
            "missing": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
        })

    return {
        "dataset": dataset_name,
        "source_type": "active_dataframe",
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "columns_detail": columns,
    }


def build_calculation_lineage(
    *,
    metric: str,
    formula: str | None = None,
    fields: list[str] | None = None,
    aggregation: str | None = None,
    group_by: str | None = None,
    filters: dict[str, Any] | None = None,
    rows_used: int | None = None,
    result: Any = None,
    engine: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Create an auditable record describing how a metric/result was produced."""
    return {
        "metric": metric,
        "formula": formula or "Direct field / deterministic calculation",
        "fields": fields or [],
        "aggregation": aggregation or "None",
        "group_by": group_by or "None",
        "filters": filters or {},
        "rows_used": rows_used,
        "result": result,
        "engine": engine or "InsightAI deterministic analytics",
        "question": question,
        "type": "calculation",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_query_lineage(query_result: dict[str, Any], question: str) -> dict[str, Any]:
    """Convert the deterministic Query Engine result into lineage metadata."""
    return {
        "metric": query_result.get("metric") or query_result.get("intent", "Query"),
        "formula": query_result.get("formula") or query_result.get("calculation") or "Deterministic query",
        "fields": query_result.get("fields") or [
            x for x in [query_result.get("metric"), query_result.get("group_by")] if x
        ],
        "aggregation": query_result.get("aggregation") or query_result.get("intent", "Query"),
        "group_by": query_result.get("group_by") or "None",
        "filters": query_result.get("filters") or {},
        "rows_used": query_result.get("rows_used"),
        "result": query_result.get("results", query_result.get("value")),
        "engine": query_result.get("engine", "InsightAI deterministic analytics"),
        "question": question,
        "type": "query",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def store_lineage(
    df: pd.DataFrame,
    dataset_name: str,
    *,
    calculation: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and return the current lineage package."""
    package = build_dataset_lineage(df, dataset_name)
    package["calculation"] = calculation
    package["query"] = query
    return package


def summarize_lineage(package: dict[str, Any]) -> list[str]:
    """Return concise human-readable lineage statements."""
    lines = [
        f"Source dataset: {package.get('dataset', 'Active Dataset')}",
        f"Rows available: {package.get('rows', 0):,}",
        f"Columns available: {package.get('columns', 0):,}",
    ]
    calc = package.get("calculation")
    if calc:
        lines.append(f"Calculation: {calc.get('metric', 'Metric')} → {calc.get('formula', 'Deterministic calculation')}")
        if calc.get("fields"):
            lines.append("Fields used: " + ", ".join(map(str, calc["fields"])))
        if calc.get("aggregation"):
            lines.append(f"Aggregation: {calc['aggregation']}")
        if calc.get("group_by") and calc.get("group_by") != "None":
            lines.append(f"Grouped by: {calc['group_by']}")
        if calc.get("rows_used") is not None:
            lines.append(f"Rows used: {int(calc['rows_used']):,}")
    query = package.get("query")
    if query:
        lines.append(f"Question: {query.get('question', '')}")
        lines.append(f"Query engine: {query.get('engine', 'Deterministic analytics')}")
    return lines
