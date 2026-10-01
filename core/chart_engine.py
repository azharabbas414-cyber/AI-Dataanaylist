"""Natural-language to chart engine for InsightAI.

Charts are built from deterministic query-engine evidence. The LLM is never
used to calculate chart values.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px

from core.query_engine import _norm, _numeric_column, query_dataframe


CHART_WORDS = (
    "chart",
    "plot",
    "graph",
    "visualize",
    "visualise",
    "show",
    "display",
    "trend",
    "compare",
    "comparison",
    "distribution",
    "histogram",
    "bar",
    "line",
    "pie",
)


def is_chart_request(question: str) -> bool:
    """Return True when the question explicitly asks for a visual."""
    q = _norm(question)
    return any(word in q.split() for word in CHART_WORDS) or any(
        phrase in q
        for phrase in (
            "show me",
            "visualize",
            "visualise",
            "plot the",
            "graph the",
            "trend of",
            "compare ",
            "distribution of",
        )
    )


def _datetime_column(df: pd.DataFrame, question: str) -> str | None:
    datetime_cols = list(
        df.select_dtypes(include=["datetime", "datetimetz"]).columns
    )
    if datetime_cols:
        q = _norm(question)
        for col in datetime_cols:
            if _norm(col) in q:
                return col
        return datetime_cols[0]

    candidates: list[tuple[float, str]] = []
    for col in df.columns:
        name = _norm(col)
        if any(
            token in name
            for token in ("date", "time", "timestamp", "month", "year")
        ):
            parsed = pd.to_datetime(df[col], errors="coerce")
            valid_ratio = float(parsed.notna().mean()) if len(df) else 0.0
            if valid_ratio >= 0.70:
                candidates.append((valid_ratio, col))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def _metric_column(df: pd.DataFrame, question: str) -> str | None:
    return _numeric_column(df, question)


def _chart_title(
    question: str,
    intent: str | None,
    metric: str | None,
    group: str | None,
    time_grain: str | None = None,
) -> str:
    if metric and group:
        if intent == "group_sum":
            return f"Total {metric} by {group}"
        if intent == "group_mean":
            return f"Average {metric} by {group}"
        if intent == "group_count":
            return f"Count by {group}"
        if intent == "ranking":
            return f"{metric} by {group}"
        if intent == "calculated_metric":
            aggregation = "Total"
            q = _norm(question)
            if any(word in q.split() for word in ("average", "mean", "avg")):
                aggregation = "Average"
            elif "median" in q:
                aggregation = "Median"
            return f"{aggregation} {metric} by {group}"

    if metric and time_grain:
        aggregation = "Total"
        q = _norm(question)
        if any(word in q.split() for word in ("average", "mean", "avg")):
            aggregation = "Average"
        elif "median" in q:
            aggregation = "Median"
        return f"{aggregation} {metric} by {time_grain.title()}"

    return question.strip().rstrip("?").capitalize()


def _chart_from_query_results(
    result: dict[str, Any],
    question: str,
) -> dict[str, Any] | None:
    """Create a chart directly from already-calculated query records."""
    records = result.get("results") or []
    if not records:
        return None

    metric = result.get("metric")
    group = result.get("group_by")
    time_grain = result.get("time_grain")
    intent = result.get("intent")
    chart_df = pd.DataFrame(records)

    # Calculated time-series queries return a `period` field.
    if "period" in chart_df.columns:
        value_candidates = [
            c
            for c in chart_df.columns
            if c != "period" and pd.api.types.is_numeric_dtype(chart_df[c])
        ]
        if value_candidates:
            value_col = value_candidates[0]
            title = _chart_title(
                question,
                intent,
                metric,
                None,
                time_grain=time_grain or "period",
            )
            fig = px.line(
                chart_df,
                x="period",
                y=value_col,
                markers=True,
                title=title,
            )
            return {
                "handled": True,
                "chart_type": "line",
                "figure": fig,
                "title": title,
                "source": "deterministic query-engine calculation",
                "rows_used": len(chart_df),
            }

    if group:
        value_candidates = [
            c
            for c in chart_df.columns
            if c != group and pd.api.types.is_numeric_dtype(chart_df[c])
        ]
        if value_candidates:
            value_col = value_candidates[0]
            chart_df = chart_df.head(20).copy()

            q = _norm(question)
            chart_type = "bar"
            if "pie" in q or "share" in q or "proportion" in q:
                chart_type = "pie"

            title = _chart_title(
                question,
                intent,
                metric,
                group,
                time_grain=time_grain,
            )

            if chart_type == "pie":
                fig = px.pie(
                    chart_df,
                    names=group,
                    values=value_col,
                    title=title,
                    hole=0.35,
                )
            else:
                fig = px.bar(
                    chart_df,
                    x=group,
                    y=value_col,
                    title=title,
                )

            return {
                "handled": True,
                "chart_type": chart_type,
                "figure": fig,
                "title": title,
                "source": "deterministic query-engine calculation",
                "rows_used": len(chart_df),
            }

    return None


def build_chart_payload(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """Build an auditable chart payload from the active dataframe."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"handled": False, "reason": "The active dataset is empty."}

    if not is_chart_request(question):
        return {"handled": False, "reason": "This question does not request a chart."}

    q = _norm(question)
    result = query_dataframe(df, question)

    # IMPORTANT: calculated/grouped query results are authoritative. This is
    # checked before raw dataframe trend logic so a derived metric such as
    # Quantity × UnitPrice is never accidentally replaced by UnitPrice alone.
    query_chart = _chart_from_query_results(result, question)
    if query_chart:
        return query_chart

    metric = result.get("metric")

    # Distribution / histogram.
    if "distribution" in q or "histogram" in q:
        metric = metric or _metric_column(df, question)
        if metric:
            values = pd.to_numeric(df[metric], errors="coerce").dropna()
            if not values.empty:
                chart_df = pd.DataFrame({metric: values})
                fig = px.histogram(
                    chart_df,
                    x=metric,
                    nbins=min(40, max(10, int(values.nunique()))),
                    title=f"Distribution of {metric}",
                )
                return {
                    "handled": True,
                    "chart_type": "histogram",
                    "figure": fig,
                    "title": f"Distribution of {metric}",
                    "source": "deterministic dataframe calculation",
                    "rows_used": len(values),
                }

    # Raw dataframe time-series trend.
    if any(
        token in q
        for token in (
            "trend",
            "over time",
            "by month",
            "by year",
            "monthly",
            "daily",
            "weekly",
        )
    ):
        metric = metric or _metric_column(df, question)
        date_col = _datetime_column(df, question)
        if metric and date_col and metric in df.columns:
            work = df[[date_col, metric]].copy()
            work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
            work[metric] = pd.to_numeric(work[metric], errors="coerce")
            work = work.dropna(subset=[date_col, metric])

            if not work.empty:
                freq = "MS"
                if "daily" in q:
                    freq = "D"
                elif "weekly" in q:
                    freq = "W"
                elif "year" in q or "yearly" in q:
                    freq = "YS"

                trend = (
                    work.set_index(date_col)[metric]
                    .resample(freq)
                    .sum()
                    .reset_index()
                )
                fig = px.line(
                    trend,
                    x=date_col,
                    y=metric,
                    markers=True,
                    title=f"{metric} Trend Over Time",
                )
                return {
                    "handled": True,
                    "chart_type": "line",
                    "figure": fig,
                    "title": f"{metric} Trend Over Time",
                    "source": "deterministic dataframe calculation",
                    "rows_used": len(work),
                }

    return {
        "handled": False,
        "reason": "InsightAI could not map the requested visual to a safe deterministic chart.",
    }


def render_chart(
    df: pd.DataFrame,
    question: str,
    *,
    use_container_width: bool = True,
) -> dict[str, Any]:
    """Build and return the chart payload. Rendering remains in the UI layer."""
    return build_chart_payload(df, question)
