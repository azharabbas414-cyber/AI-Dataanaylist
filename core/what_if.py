"""InsightAI deterministic What-If / Decision Intelligence engine.

Metrics are dataset-driven. Users can select any numeric field or create a
calculated metric from numeric fields; no business metric is hard-coded.
"""
from __future__ import annotations

import ast
from typing import Any
import pandas as pd


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.select_dtypes(include="number").columns]


def metric_series(df: pd.DataFrame, metric: str, calculated_metrics: dict[str, str] | None = None) -> pd.Series:
    if metric == "Row Count":
        return pd.Series(1.0, index=df.index)
    if calculated_metrics and metric in calculated_metrics:
        return evaluate_formula(df, calculated_metrics[metric])
    if metric not in df.columns:
        raise ValueError(f"Metric '{metric}' is not available in the dataset.")
    return pd.to_numeric(df[metric], errors="coerce")


def available_metrics(df: pd.DataFrame, calculated_metrics: dict[str, str] | None = None) -> list[str]:
    return ["Row Count"] + numeric_columns(df) + list((calculated_metrics or {}).keys())


def evaluate_formula(df: pd.DataFrame, formula: str) -> pd.Series:
    """Safely evaluate a simple arithmetic formula using numeric columns.

    Supported operators: +, -, *, / and parentheses. No Python functions,
    attributes, calls, subscripting or arbitrary code are permitted.
    """
    tree = ast.parse(formula, mode="eval")

    def walk(node: ast.AST) -> pd.Series:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Name):
            if node.id not in df.columns:
                raise ValueError(f"Unknown field in formula: {node.id}")
            return pd.to_numeric(df[node.id], errors="coerce")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return pd.Series(float(node.value), index=df.index)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = walk(node.left), walk(node.right)
            with pd.option_context("mode.use_inf_as_na", True):
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                return left / right.replace(0, pd.NA)
        raise ValueError("Formula supports only numeric fields, numbers, +, -, *, / and parentheses.")

    return pd.to_numeric(walk(tree), errors="coerce")


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


def run_multi_scenario(df: pd.DataFrame, assumptions: list[dict[str, Any]], group_by: str | None = None,
                       filter_column: str | None = None, filter_value: Any = None,
                       calculated_metrics: dict[str, str] | None = None) -> dict[str, Any]:
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
        actual = metric_series(work, metric, calculated_metrics)
        valid = actual.notna() & actual.replace([float("inf"), float("-inf")], pd.NA).notna()
        transformed = actual.copy()
        transformed.loc[valid] = _apply_adjustment(actual.loc[valid], scenario_type, adjustment)
        baseline = baseline.add(actual.fillna(0), fill_value=0)
        scenario = scenario.add(transformed.fillna(0), fill_value=0)
        formula = _formula(metric, scenario_type, adjustment)
        if calculated_metrics and metric in calculated_metrics:
            formula = f"{metric} = {calculated_metrics[metric]}; scenario: {formula}"
        evidence.append({"metric": metric, "scenario_type": scenario_type, "adjustment": adjustment,
                         "formula": formula, "rows_used": int(valid.sum()),
                         "actual": float(actual.sum(skipna=True)), "scenario": float(transformed.sum(skipna=True))})

    if group_by and group_by != "None":
        if group_by not in work.columns:
            raise ValueError("Selected group field is not present.")
        groups = work[group_by].astype(str)
        actual_g = baseline.groupby(groups).sum()
        scenario_g = scenario.groupby(groups).sum()
        result = pd.DataFrame({"Group": actual_g.index, "Actual": actual_g.values,
                               "Scenario": scenario_g.reindex(actual_g.index).values})
    else:
        result = pd.DataFrame({"Group": ["Overall"], "Actual": [baseline.sum()], "Scenario": [scenario.sum()]})

    result["Impact"] = result["Scenario"] - result["Actual"]
    result["Impact %"] = result.apply(lambda r: (r["Impact"] / r["Actual"] * 100) if r["Actual"] else 0.0, axis=1)
    actual_total = float(result["Actual"].sum())
    scenario_total = float(result["Scenario"].sum())
    impact = scenario_total - actual_total
    impact_pct = impact / actual_total * 100 if actual_total else 0.0
    return {"assumptions": evidence, "group_by": group_by, "filter_column": filter_column,
            "filter_value": filter_value, "rows_used": int(len(work)), "actual": actual_total,
            "scenario": scenario_total, "impact": impact, "impact_pct": impact_pct,
            "result": result, "formula": " + ".join(x["formula"] for x in evidence)}


def _formula(metric: str, scenario_type: str, adjustment: float) -> str:
    if scenario_type == "Increase by %": return f"{metric} × (1 + {adjustment:g}/100)"
    if scenario_type == "Decrease by %": return f"{metric} × (1 - {adjustment:g}/100)"
    if scenario_type == "Add": return f"{metric} + {adjustment:g}"
    return f"{metric} - {adjustment:g}"


def run_scenario(df: pd.DataFrame, metric: str, scenario_type: str, adjustment: float,
                 group_by: str | None = None, filter_column: str | None = None,
                 filter_value: Any = None, calculated_metrics: dict[str, str] | None = None) -> dict[str, Any]:
    return run_multi_scenario(df, [{"metric": metric, "scenario_type": scenario_type, "adjustment": adjustment}],
                              group_by, filter_column, filter_value, calculated_metrics)
