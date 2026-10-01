"""InsightAI deterministic What-If scenario engine."""
from __future__ import annotations

from typing import Any
import pandas as pd


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.select_dtypes(include="number").columns]


def metric_series(df: pd.DataFrame, metric: str) -> pd.Series:
    if metric == "Row Count":
        return pd.Series(1.0, index=df.index)
    return pd.to_numeric(df[metric], errors="coerce")


def available_metrics(df: pd.DataFrame) -> list[str]:
    return ["Row Count"] + numeric_columns(df)


def run_scenario(
    df: pd.DataFrame,
    metric: str,
    scenario_type: str,
    adjustment: float,
    group_by: str | None = None,
    filter_column: str | None = None,
    filter_value: Any = None,
) -> dict[str, Any]:
    """Run a non-destructive scenario.

    Adjustment is interpreted as a percentage for Increase/Decrease and as an
    absolute delta for Add/Subtract. The original dataframe is never modified.
    """
    if df.empty:
        raise ValueError("The active dataset is empty.")

    work = df.copy()
    if filter_column and filter_column != "None":
        if filter_column not in work.columns:
            raise ValueError("Selected filter column is not present.")
        if filter_value is not None:
            work = work[work[filter_column].astype(str) == str(filter_value)].copy()

    actual = metric_series(work, metric).dropna()

    if scenario_type == "Increase by %":
        scenario_values = actual * (1 + adjustment / 100.0)
        adjustment_label = f"+{adjustment:g}%"
    elif scenario_type == "Decrease by %":
        scenario_values = actual * (1 - adjustment / 100.0)
        adjustment_label = f"-{adjustment:g}%"
    elif scenario_type == "Add":
        scenario_values = actual + adjustment
        adjustment_label = f"+{adjustment:g}"
    elif scenario_type == "Subtract":
        scenario_values = actual - adjustment
        adjustment_label = f"-{adjustment:g}"
    else:
        raise ValueError("Unsupported scenario type.")

    if group_by and group_by != "None":
        grouped_actual = actual.groupby(work.loc[actual.index, group_by].astype(str)).sum()
        grouped_scenario = scenario_values.groupby(work.loc[scenario_values.index, group_by].astype(str)).sum()
        result = pd.DataFrame({
            "Group": grouped_actual.index,
            "Actual": grouped_actual.values,
            "Scenario": grouped_scenario.reindex(grouped_actual.index).values,
        })
    else:
        result = pd.DataFrame({
            "Group": ["Overall"],
            "Actual": [actual.sum()],
            "Scenario": [scenario_values.sum()],
        })

    result["Impact"] = result["Scenario"] - result["Actual"]
    result["Impact %"] = result.apply(
        lambda r: (r["Impact"] / r["Actual"] * 100) if r["Actual"] not in (0, None) else 0,
        axis=1,
    )

    actual_total = float(result["Actual"].sum())
    scenario_total = float(result["Scenario"].sum())
    impact = scenario_total - actual_total
    impact_pct = (impact / actual_total * 100) if actual_total else 0.0

    return {
        "metric": metric,
        "scenario_type": scenario_type,
        "adjustment": adjustment,
        "adjustment_label": adjustment_label,
        "group_by": group_by,
        "filter_column": filter_column,
        "filter_value": filter_value,
        "rows_used": int(len(actual)),
        "actual": actual_total,
        "scenario": scenario_total,
        "impact": impact,
        "impact_pct": impact_pct,
        "result": result,
        "formula": (
            f"{metric} × (1 + {adjustment:g}/100)"
            if scenario_type == "Increase by %"
            else f"{metric} × (1 - {adjustment:g}/100)"
            if scenario_type == "Decrease by %"
            else f"{metric} + {adjustment:g}"
            if scenario_type == "Add"
            else f"{metric} - {adjustment:g}"
        ),
    }
