"""Deterministic dataframe query engine for InsightAI.

The engine executes analytical questions directly against the active dataframe.
LLMs may explain the evidence, but they do not perform the arithmetic.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from core.calculated_metrics import run_calculated_metric_query
from core.performance import aggregate as performance_aggregate, total as performance_total


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _find_column(df: pd.DataFrame, terms: list[str]) -> str | None:
    columns = list(df.columns)
    normalized = {_norm(c): c for c in columns}
    for term in terms:
        nt = _norm(term)
        if nt in normalized:
            return normalized[nt]

    candidates: list[tuple[int, str]] = []
    for c in columns:
        nc = _norm(c)
        for term in terms:
            nt = _norm(term)
            if nt and (nt in nc or nc in nt):
                candidates.append((len(nc), c))
                break
    if candidates:
        candidates.sort()
        return candidates[0][1]
    return None


def _numeric_column(df: pd.DataFrame, question: str) -> str | None:
    numeric = list(df.select_dtypes(include="number").columns)
    if not numeric:
        return None

    q = _norm(question)
    aliases = {
        "profit": ["profit", "net profit", "gross profit", "earnings"],
        "sales": ["sales", "revenue", "turnover", "amount"],
        "revenue": ["revenue", "sales", "turnover"],
        "quantity": ["quantity", "qty", "units", "volume"],
        "price": ["price", "unit price", "selling price"],
        "cost": ["cost", "expense", "expenses"],
        "traffic": ["traffic", "bytes", "bandwidth"],
    }

    for metric_terms in aliases.values():
        if any(_norm(t) in q for t in metric_terms):
            found = _find_column(df, metric_terms)
            if found in numeric:
                return found

    for c in numeric:
        if _norm(c) in q:
            return c
    return None


def _group_column(df: pd.DataFrame, question: str, metric: str | None) -> str | None:
    categorical = list(df.select_dtypes(include=["object", "category", "bool"]).columns)
    q = _norm(question)

    aliases = {
        "product": ["product", "item", "sku", "product name"],
        "category": ["category", "segment", "type"],
        "region": ["region", "area", "territory", "market", "country", "city"],
        "customer": ["customer", "customers", "customer id", "client", "clients"],
        "date": ["date", "order date", "transaction date", "month", "year"],
    }
    for terms in aliases.values():
        if any(_norm(t) in q for t in terms):
            found = _find_column(df, terms)
            if found in categorical:
                return found

    for c in categorical:
        if _norm(c) in q:
            return c

    m = re.search(r"which\s+([a-z0-9 _-]+?)\s+(?:has|with|generated|made|is)", q)
    if m:
        found = _find_column(df, [m.group(1).strip()])
        if found in categorical:
            return found
    return None


def _fmt_number(value: Any) -> str:
    try:
        v = float(value)
        if v.is_integer():
            return f"{int(v):,}"
        return f"{v:,.2f}"
    except Exception:
        return str(value)


def _ranking_request(question: str) -> tuple[str | None, int | None]:
    """Detect top/bottom/highest/lowest N requests robustly."""
    q = _norm(question)

    patterns = [
        ("top", r"\btop\s+(\d+)\b"),
        ("top", r"\bhighest\s+(?:top\s+)?(\d+)\b"),
        ("top", r"\b(?:best|largest)\s+(\d+)\b"),
        ("bottom", r"\bbottom\s+(\d+)\b"),
        ("bottom", r"\blowest\s+(?:bottom\s+)?(\d+)\b"),
        ("bottom", r"\b(?:worst|smallest)\s+(\d+)\b"),
    ]
    for direction, pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return direction, max(1, min(int(match.group(1)), 100))
    return None, None


def _format_records_table(records: list[dict[str, Any]]) -> str:
    if not records:
        return "No matching results were found."
    keys = list(records[0].keys())
    lines = ["| Rank | " + " | ".join(keys) + " |", "|---:|" + "---|" * len(keys)]
    for rank, row in enumerate(records, 1):
        values = []
        for key in keys:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(_fmt_number(value))
            else:
                values.append(str(value))
        lines.append(f"| {rank} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def query_dataframe(df: pd.DataFrame, question: str) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"handled": False, "reason": "The active dataset is empty."}

    q = _norm(question)

    # Calculated metrics are evaluated first. Top/bottom semantics are applied
    # inside the calculated-metric engine so formulas such as Quantity*UnitPrice
    # are never confused with the UnitPrice column itself.
    calculated = run_calculated_metric_query(df, question)
    if calculated.get("handled"):
        return calculated

    metric = _numeric_column(df, question)
    group = _group_column(df, question, metric)

    result: dict[str, Any] = {
        "handled": False,
        "intent": "unknown",
        "question": question,
        "metric": metric,
        "group_by": group,
    }

    if any(x in q for x in ["how many rows", "row count", "number of rows", "how many records"]):
        result.update(handled=True, intent="row_count", value=int(len(df)),
                      direct_answer=f"The dataset contains {_fmt_number(len(df))} rows.")
        return result

    if "missing" in q and metric is None:
        missing = df.isna().sum().sort_values(ascending=False)
        missing = missing[missing > 0]
        result.update(
            handled=True,
            intent="missing_values",
            results=[{"column": str(k), "missing": int(v)} for k, v in missing.items()],
            direct_answer=("No missing values were detected." if missing.empty
                           else "Missing values are present; see the calculated column-level counts."),
        )
        return result

    if any(x in q for x in ["how many products", "distinct products", "unique products", "number of products"]):
        group = group or _find_column(df, ["product", "item", "sku"])
        if group:
            n = int(df[group].nunique(dropna=True))
            result.update(handled=True, intent="distinct_count", group_by=group, value=n,
                          direct_answer=f"There are {_fmt_number(n)} distinct values in {group}.")
            return result

    wants_max = any(x in q for x in ["maximum", "max", "highest", "largest", "most"])
    wants_min = any(x in q for x in ["minimum", "min", "lowest", "smallest", "least"])

    # Explicit ranking is checked before generic extreme logic.
    direction, n = _ranking_request(question)
    if direction and metric and group:
        ascending = direction == "bottom"
        agg_df, engine_used = performance_aggregate(df, group, metric, "sum", sort_desc=not ascending, limit=n)
        records = agg_df.to_dict(orient="records")
        records = [{group: row[group], f"total_{metric}": row["value"]} for row in records]
        result.update(
            handled=True,
            intent="ranking",
            results=records,
            rank_direction=direction,
            rank_limit=n,
            engine=engine_used,
            direct_answer=f"Here are the {direction} {n} {group} values ranked by total {metric}.",
        )
        return result

    if (wants_max or wants_min) and metric:
        clean = df[[metric]].dropna()
        if clean.empty:
            result.update(handled=True, intent="extreme", direct_answer=f"No usable values are available for {metric}.")
            return result

        extreme_value = clean[metric].max() if wants_max else clean[metric].min()
        mask = df[metric].eq(extreme_value)
        rows = df.loc[mask].head(20)

        grouped = None
        if group and group in df.columns:
            grouped_df, engine_used = performance_aggregate(df, group, metric, "sum", sort_desc=wants_max, limit=10)

        row_records = rows.head(10).to_dict(orient="records")
        group_records = []
        if grouped_df is not None:
            for row in grouped_df.to_dict(orient="records"):
                group_records.append({group: row[group], f"total_{metric}": row["value"]})

        direct = f"The {'maximum' if wants_max else 'minimum'} {metric} is {_fmt_number(extreme_value)}."
        if group_records:
            top_group = group_records[0]
            direct += f" The {group} with the {'highest' if wants_max else 'lowest'} total {metric} is {top_group.get(group)}, at {_fmt_number(top_group.get(f'total_{metric}'))}."

        result.update(handled=True, intent="extreme", extreme_value=float(extreme_value),
                      matching_rows=row_records, grouped_totals=group_records, engine=(engine_used if group else "pandas"), direct_answer=direct)
        return result

    if metric and group:
        if any(x in q for x in ["total", "sum", "overall"]):
            grouped_df, engine_used = performance_aggregate(df, group, metric, "sum", sort_desc=True, limit=20)
            records = [{group: row[group], f"total_{metric}": row["value"]} for row in grouped_df.to_dict(orient="records")]
            result.update(handled=True, intent="group_sum", results=records,
                          engine=engine_used, direct_answer=f"Total {metric} by {group} calculated successfully.")
            return result

        if any(x in q for x in ["average", "avg", "mean"]):
            grouped_df, engine_used = performance_aggregate(df, group, metric, "mean", sort_desc=True, limit=20)
            records = [{group: row[group], f"average_{metric}": row["value"]} for row in grouped_df.to_dict(orient="records")]
            result.update(handled=True, intent="group_mean", results=records,
                          engine=engine_used, direct_answer=f"Average {metric} by {group} calculated successfully.")
            return result

        if "median" in q:
            grouped_df, engine_used = performance_aggregate(df, group, metric, "median", sort_desc=True, limit=20)
            records = [{group: row[group], f"median_{metric}": row["value"]} for row in grouped_df.to_dict(orient="records")]
            result.update(handled=True, intent="group_median", results=records,
                          engine=engine_used, direct_answer=f"Median {metric} by {group} calculated successfully.")
            return result

    if metric:
        if any(x in q for x in ["total", "sum"]):
            value, engine_used = performance_total(df, metric)
            result.update(handled=True, intent="sum", value=float(value), engine=engine_used,
                          direct_answer=f"The total {metric} is {_fmt_number(value)}.")
            return result
        if any(x in q for x in ["average", "avg", "mean"]):
            value = df[metric].mean()
            result.update(handled=True, intent="mean", value=float(value),
                          direct_answer=f"The average {metric} is {_fmt_number(value)}.")
            return result

    return result
