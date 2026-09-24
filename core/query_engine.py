"""Deterministic dataframe query engine for InsightAI.

The AI should explain computed evidence, not guess row-level answers.
This module handles common natural-language analytical questions directly
against the active dataframe and returns exact, auditable results.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _find_column(df: pd.DataFrame, terms: list[str]) -> str | None:
    columns = list(df.columns)
    normalized = {_norm(c): c for c in columns}

    for term in terms:
        nt = _norm(term)
        if nt in normalized:
            return normalized[nt]

    # Exact token/substring match, preferring shorter column names.
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
    # Common business metric aliases.
    aliases = {
        "profit": ["profit", "net profit", "gross profit", "earnings"],
        "sales": ["sales", "revenue", "turnover", "amount"],
        "revenue": ["revenue", "sales", "turnover"],
        "quantity": ["quantity", "qty", "units", "volume"],
        "price": ["price", "unit price", "selling price"],
        "cost": ["cost", "expense", "expenses"],
        "traffic": ["traffic", "bytes", "bandwidth"],
    }

    # Prefer a metric explicitly mentioned in the question.
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

    # Prefer dimensions explicitly mentioned in the question.
    aliases = {
        "product": ["product", "item", "sku", "product name"],
        "category": ["category", "segment", "type"],
        "region": ["region", "area", "territory", "market", "country", "city"],
        "customer": ["customer", "customer id", "client"],
        "date": ["date", "order date", "transaction date", "month", "year"],
    }
    for terms in aliases.values():
        if any(_norm(t) in q for t in terms):
            found = _find_column(df, terms)
            if found in categorical:
                return found

    # Direct column-name mention.
    for c in categorical:
        if _norm(c) in q:
            return c

    # If user asks "which X" and X is a categorical column, infer it.
    m = re.search(r"which\s+([a-z0-9 _-]+?)\s+(?:has|with|generated|made|is)", q)
    if m:
        phrase = m.group(1).strip()
        found = _find_column(df, [phrase])
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


def query_dataframe(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """Execute a safe deterministic query for common analytical questions."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"handled": False, "reason": "The active dataset is empty."}

    q = _norm(question)
    metric = _numeric_column(df, question)
    group = _group_column(df, question, metric)

    result: dict[str, Any] = {
        "handled": False,
        "intent": "unknown",
        "question": question,
        "metric": metric,
        "group_by": group,
    }

    # Quality / count questions.
    if any(x in q for x in ["how many rows", "row count", "number of rows", "how many records"]):
        result.update(
            handled=True,
            intent="row_count",
            value=int(len(df)),
            direct_answer=f"The dataset contains {_fmt_number(len(df))} rows.",
        )
        return result

    if "missing" in q and metric is None:
        missing = df.isna().sum().sort_values(ascending=False)
        missing = missing[missing > 0]
        result.update(
            handled=True,
            intent="missing_values",
            results=[{"column": str(k), "missing": int(v)} for k, v in missing.items()],
            direct_answer=(
                "No missing values were detected."
                if missing.empty
                else "Missing values are present; see the calculated column-level counts."
            ),
        )
        return result

    # Distinct / unique questions.
    if any(x in q for x in ["how many products", "distinct products", "unique products", "number of products"]):
        group = group or _find_column(df, ["product", "item", "sku"])
        if group:
            n = int(df[group].nunique(dropna=True))
            result.update(
                handled=True,
                intent="distinct_count",
                group_by=group,
                value=n,
                direct_answer=f"There are {_fmt_number(n)} distinct values in {group}.",
            )
            return result

    # Maximum / minimum questions.
    wants_max = any(x in q for x in ["maximum", "max", "highest", "largest", "most"])
    wants_min = any(x in q for x in ["minimum", "min", "lowest", "smallest", "least"])

    if (wants_max or wants_min) and metric:
        clean = df[[metric]].dropna()
        if clean.empty:
            return {**result, "handled": True, "intent": "extreme", "direct_answer": f"No usable values are available for {metric}."}

        extreme_value = clean[metric].max() if wants_max else clean[metric].min()
        mask = df[metric].eq(extreme_value)
        rows = df.loc[mask].head(20)

        # If a grouping dimension exists, calculate both the single-record
        # extreme and cumulative metric by group. This removes ambiguity for
        # questions such as "which product has maximum profit".
        grouped = None
        if group and group in df.columns:
            grouped = (
                df.groupby(group, dropna=False)[metric]
                .sum()
                .sort_values(ascending=not wants_max)
                .head(10)
            )

        row_records = rows.head(10).to_dict(orient="records")
        group_records = []
        if grouped is not None:
            for idx, value in grouped.items():
                group_records.append({group: idx, f"total_{metric}": value})

        if group and group in rows.columns and not rows.empty:
            values = ", ".join(str(v) for v in rows[group].dropna().unique()[:10])
            direct = (
                f"The highest individual {metric} is {_fmt_number(extreme_value)}. "
                f"It occurs for {group}: {values}."
            ) if wants_max else (
                f"The lowest individual {metric} is {_fmt_number(extreme_value)}. "
                f"It occurs for {group}: {values}."
            )
        else:
            direct = f"The {'maximum' if wants_max else 'minimum'} {metric} is {_fmt_number(extreme_value)}."

        if group_records:
            top_group = group_records[0]
            top_name = top_group.get(group)
            top_value = top_group.get(f"total_{metric}")
            direct += (
                f" The {group} with the {'highest' if wants_max else 'lowest'} total {metric} "
                f"is {top_name}, at {_fmt_number(top_value)}."
            )

        result.update(
            handled=True,
            intent="extreme",
            extreme_value=float(extreme_value),
            matching_rows=row_records,
            grouped_totals=group_records,
            direct_answer=direct,
        )
        return result

    # Top N / bottom N by a metric.
    top_match = re.search(r"(?:top|highest)\s+(\d+)", q)
    bottom_match = re.search(r"(?:bottom|lowest)\s+(\d+)", q)
    if (top_match or bottom_match) and metric and group:
        n = int((top_match or bottom_match).group(1))
        n = max(1, min(n, 50))
        ascending = bool(bottom_match)
        grouped = (
            df.groupby(group, dropna=False)[metric]
            .sum()
            .sort_values(ascending=ascending)
            .head(n)
        )
        records = [{group: idx, f"total_{metric}": val} for idx, val in grouped.items()]
        result.update(
            handled=True,
            intent="ranking",
            results=records,
            direct_answer=f"Here are the {('bottom' if ascending else 'top')} {n} {group} values ranked by total {metric}.",
        )
        return result

    # Total / average / median / count by group.
    if metric and group:
        if any(x in q for x in ["total", "sum", "overall"]):
            grouped = df.groupby(group, dropna=False)[metric].sum().sort_values(ascending=False)
            records = [{group: idx, f"total_{metric}": val} for idx, val in grouped.head(20).items()]
            result.update(
                handled=True,
                intent="group_sum",
                results=records,
                direct_answer=f"Total {metric} has been calculated for each {group}.",
            )
            return result

        if any(x in q for x in ["average", "mean"]):
            grouped = df.groupby(group, dropna=False)[metric].mean().sort_values(ascending=False)
            records = [{group: idx, f"average_{metric}": val} for idx, val in grouped.head(20).items()]
            result.update(
                handled=True,
                intent="group_mean",
                results=records,
                direct_answer=f"Average {metric} has been calculated for each {group}.",
            )
            return result

        if "count" in q:
            grouped = df.groupby(group, dropna=False)[metric].count().sort_values(ascending=False)
            records = [{group: idx, f"count_{metric}": val} for idx, val in grouped.head(20).items()]
            result.update(
                handled=True,
                intent="group_count",
                results=records,
                direct_answer=f"The number of {metric} records has been calculated for each {group}.",
            )
            return result

    # Simple scalar metric questions.
    if metric:
        if any(x in q for x in ["average", "mean"]):
            value = df[metric].mean()
            result.update(handled=True, intent="mean", value=float(value), direct_answer=f"The average {metric} is {_fmt_number(value)}.")
            return result
        if "median" in q:
            value = df[metric].median()
            result.update(handled=True, intent="median", value=float(value), direct_answer=f"The median {metric} is {_fmt_number(value)}.")
            return result
        if any(x in q for x in ["total", "sum"]):
            value = df[metric].sum()
            result.update(handled=True, intent="sum", value=float(value), direct_answer=f"The total {metric} is {_fmt_number(value)}.")
            return result

    return result
