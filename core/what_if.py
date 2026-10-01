"""InsightAI deterministic What-If / Decision Intelligence engine."""
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


def _apply_adjustment(series: pd.Series, scenario_type: str, adjustment: float) -> pd.Series:
    if scenario_type == "Increase by %":
        return series * (1 + adjustment / 100.0)
    if scenario_type == "Decrease by %":
        return series * (1 - adjustment / 100.0)
    if scenario_type == "Add":
        return series + adjustment
    if scenario_type == "Subtract":
        return series - adjustment
    raise ValueError(f"Unsupported scenario type: {scenario_type}")


def run_multi_scenario(
    df: pd.DataFrame,
    assumptions: list[dict[str, Any]],
    group_by: str | None = None,
    filter_column: str | None = None,
    filter_value: Any = None,
) -> dict[str, Any]:
    """Run multiple independent assumptions and combine their impacts.

    The simulation is deterministic and never mutates the input dataframe.
    Each assumption transforms a metric series, then all scenario deltas are
    added together. This is intentionally transparent rather than causal.
    """
    if df.empty:
        raise ValueError("The active dataset is empty.")
    if not assumptions:
        raise ValueError("At least one assumption is required.")

    work = df.copy()
    if filter_column and filter_column != "None":
        if filter_column not in work.columns:
            raise ValueError("Selected filter column is not present.")
        work = work[work[filter_column].astype(str) == str(filter_value)].copy()

    if work.empty:
        raise ValueError("The selected filter leaves no rows.")

    baseline = pd.Series(0.0, index=work.index)
    scenario = pd.Series(0.0, index=work.index)
    evidence: list[dict[str, Any]] = []

    for item in assumptions:
        metric = str(item["metric"])
        scenario_type = str(item["scenario_type"])
        adjustment = float(item["adjustment"])
        actual = metric_series(work, metric)
        valid = actual.notna()
        transformed = actual.copy()
        transformed.loc[valid] = _apply_adjustment(actual.loc[valid], scenario_type, adjustment)
        baseline = baseline.add(actual.fillna(0), fill_value=0)
        scenario = scenario.add(transformed.fillna(0), fill_value=0)
        evidence.append({
            "metric": metric,
            "scenario_type": scenario_type,
            "adjustment": adjustment,
            "formula": _formula(metric, scenario_type, adjustment),
            "rows_used": int(valid.sum()),
            "actual": float(actual.sum(skipna=True)),
            "scenario": float(transformed.sum(skipna=True)),
        })

    # For grouped analysis, use the same row-level combined scenario.
    if group_by and group_by != "None":
        groups = work[group_by].astype(str)
        actual_g = baseline.groupby(groups).sum()
        scenario_g = scenario.groupby(groups).sum()
        result = pd.DataFrame({"Group": actual_g.index, "Actual": actual_g.values, "Scenario": scenario_g.reindex(actual_g.index).values})
    else:
        result = pd.DataFrame({"Group": ["Overall"], "Actual": [baseline.sum()], "Scenario": [scenario.sum()]})

    result["Impact"] = result["Scenario"] - result["Actual"]
    result["Impact %"] = result.apply(lambda r: (r["Impact"] / r["Actual"] * 100) if r["Actual"] else 0.0, axis=1)

    actual_total = float(result["Actual"].sum())
    scenario_total = float(result["Scenario"].sum())
    impact = scenario_total - actual_total
    impact_pct = impact / actual_total * 100 if actual_total else 0.0

    return {
        "assumptions": evidence,
        "group_by": group_by,
        "filter_column": filter_column,
        "filter_value": filter_value,
        "rows_used": int(len(work)),
        "actual": actual_total,
        "scenario": scenario_total,
        "impact": impact,
        "impact_pct": impact_pct,
        "result": result,
        "formula": " + ".join(x["formula"] for x in evidence),
    }


def _formula(metric: str, scenario_type: str, adjustment: float) -> str:
    if scenario_type == "Increase by %":
        return f"{metric} × (1 + {adjustment:g}/100)"
    if scenario_type == "Decrease by %":
        return f"{metric} × (1 - {adjustment:g}/100)"
    if scenario_type == "Add":
        return f"{metric} + {adjustment:g}"
    return f"{metric} - {adjustment:g}"


def run_scenario(df: pd.DataFrame, metric: str, scenario_type: str, adjustment: float, group_by: str | None = None, filter_column: str | None = None, filter_value: Any = None) -> dict[str, Any]:
    """Backward-compatible single-assumption wrapper."""
    return run_multi_scenario(df, [{"metric": metric, "scenario_type": scenario_type, "adjustment": adjustment}], group_by, filter_column, filter_value)
