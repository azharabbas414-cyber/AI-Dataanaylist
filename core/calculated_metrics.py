"""Deterministic calculated-metric engine for InsightAI."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from core.performance import aggregate as performance_aggregate


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _find_exact_or_alias(df: pd.DataFrame, aliases: list[str], numeric_only: bool = False) -> str | None:
    columns = list(df.columns)
    if numeric_only:
        columns = list(df.select_dtypes(include="number").columns)
    normalized = {_norm(c): c for c in columns}
    for alias in aliases:
        if _norm(alias) in normalized:
            return normalized[_norm(alias)]
    candidates: list[tuple[int, str]] = []
    for column in columns:
        nc = _norm(column)
        for alias in aliases:
            na = _norm(alias)
            if na and na in nc:
                candidates.append((len(nc), column))
                break
    if candidates:
        candidates.sort()
        return candidates[0][1]
    return None


def _find_datetime_column(df: pd.DataFrame, question: str) -> str | None:
    datetime_columns = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
    aliases = ["invoice date", "transaction date", "order date", "billing date", "date", "timestamp", "datetime", "time"]
    found = _find_exact_or_alias(df, aliases)
    if found in datetime_columns:
        return found
    q = _norm(question)
    if not any(t in q for t in ("month", "monthly", "year", "yearly", "date", "trend", "quarter", "week", "daily")):
        return None
    for column in df.columns:
        if column in datetime_columns:
            return column
        if not pd.api.types.is_string_dtype(df[column]) and df[column].dtype != "object":
            continue
        sample = df[column].dropna().head(300)
        if sample.empty:
            continue
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() >= 0.85:
            return column
    return None


def _find_time_grain(question: str) -> str | None:
    q = _norm(question)
    if any(x in q for x in ("by month", "monthly", "per month", "month by")):
        return "month"
    if any(x in q for x in ("by quarter", "quarterly", "per quarter")):
        return "quarter"
    if any(x in q for x in ("by year", "yearly", "annually", "per year")):
        return "year"
    if any(x in q for x in ("by week", "weekly", "per week")):
        return "week"
    if any(x in q for x in ("by day", "daily", "per day")):
        return "day"
    return None


def _find_group_column(df: pd.DataFrame, question: str, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    q = _norm(question)
    categorical = [c for c in df.select_dtypes(include=["object", "category", "bool"]).columns if c not in exclude]
    aliases = {
        "country": ["country", "countries"],
        "region": ["region", "area", "territory", "market", "zone"],
        "product": ["product", "products", "item", "items", "sku", "product name", "description"],
        "category": ["category", "categories", "segment", "segments", "type", "product category"],
        "customer": ["customer", "customers", "customer id", "client", "clients"],
        "plan": ["plan", "package", "tariff"],
        "service": ["service", "service type"],
    }
    for terms in aliases.values():
        if any(_norm(term) in q for term in terms):
            found = _find_exact_or_alias(df, terms)
            if found in categorical and found not in exclude:
                return found
    for column in categorical:
        if _norm(column) in q:
            return column
    return None


def _ranking_request(question: str) -> tuple[str | None, int | None]:
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
        m = re.search(pattern, q)
        if m:
            return direction, max(1, min(int(m.group(1)), 100))
    return None, None


def _metric_definition(df: pd.DataFrame, question: str) -> dict[str, Any] | None:
    q = _norm(question)
    numeric = set(df.select_dtypes(include="number").columns)
    if not numeric:
        return None

    sales_terms = ("sales value", "sale value", "sales amount", "transaction value", "line total", "total sales")
    existing_sales = _find_exact_or_alias(df, list(sales_terms), numeric_only=True)
    if any(_norm(alias) in q for alias in sales_terms) and existing_sales:
        return {"name": existing_sales, "label": existing_sales, "formula": existing_sales,
                "columns": [existing_sales], "kind": "existing"}

    # Quantity × UnitPrice is the standard transaction sales-value formula.
    if any(token in q for token in sales_terms):
        quantity = _find_exact_or_alias(df, ["quantity", "qty", "order quantity", "units"], numeric_only=True)
        unit_price = _find_exact_or_alias(df, ["unitprice", "unit price", "price", "selling price"], numeric_only=True)
        if quantity and unit_price and quantity != unit_price:
            return {"name": "SalesValue", "label": "Sales Value", "formula": f"{quantity} × {unit_price}",
                    "columns": [quantity, unit_price], "kind": "formula", "operation": "multiply"}

    if any(token in q for token in ("revenue", "billing", "bill value")):
        usage = _find_exact_or_alias(df, ["usage", "usage units", "data usage", "data gb", "minutes", "call minutes"], numeric_only=True)
        rate = _find_exact_or_alias(df, ["rate", "price per unit", "unit rate", "tariff"], numeric_only=True)
        existing = _find_exact_or_alias(df, ["revenue", "total revenue", "sales", "total bill"], numeric_only=True)
        if existing:
            return {"name": existing, "label": existing, "formula": existing, "columns": [existing], "kind": "existing"}
        if usage and rate and usage != rate:
            return {"name": "CalculatedRevenue", "label": "Calculated Revenue", "formula": f"{usage} × {rate}",
                    "columns": [usage, rate], "kind": "formula", "operation": "multiply"}

    if "arpu" in q or "average revenue per user" in q:
        revenue = _find_exact_or_alias(df, ["revenue", "total revenue", "sales", "billing", "total bill"], numeric_only=True)
        subscribers = _find_exact_or_alias(df, ["active subscribers", "subscribers", "subscriber count", "customers", "customer count"], numeric_only=True)
        if revenue and subscribers and revenue != subscribers:
            return {"name": "ARPU", "label": "ARPU", "formula": f"{revenue} ÷ {subscribers}",
                    "columns": [revenue, subscribers], "kind": "formula", "operation": "divide"}
    return None


def calculate_metric_series(df: pd.DataFrame, definition: dict[str, Any]) -> pd.Series:
    if definition.get("kind") == "existing":
        return pd.to_numeric(df[definition["columns"][0]], errors="coerce")
    a, b = definition["columns"]
    left = pd.to_numeric(df[a], errors="coerce")
    right = pd.to_numeric(df[b], errors="coerce")
    if definition.get("operation") == "multiply":
        return left * right
    if definition.get("operation") == "divide":
        return left.div(right.replace(0, pd.NA))
    raise ValueError(f"Unsupported calculated metric operation: {definition.get('operation')}")


def build_calculated_query(df: pd.DataFrame, question: str) -> dict[str, Any] | None:
    definition = _metric_definition(df, question)
    if not definition:
        return None
    grain = _find_time_grain(question)
    date_column = _find_datetime_column(df, question) if grain else None
    group_column = _find_group_column(df, question, exclude={date_column} if date_column else set())
    direction, limit = _ranking_request(question)

    q = _norm(question)
    aggregation = "sum"
    if re.search(r"\b(average|mean|avg)\b", q):
        aggregation = "mean"
    elif re.search(r"\bmedian\b", q):
        aggregation = "median"
    elif re.search(r"\bcount\b", q):
        aggregation = "count"

    if not grain and not group_column:
        return None
    return {
        "definition": definition,
        "time_column": date_column,
        "time_grain": grain,
        "group_column": group_column,
        "aggregation": aggregation,
        "rank_direction": direction,
        "rank_limit": limit,
    }


def execute_calculated_query(df: pd.DataFrame, query: dict[str, Any]) -> dict[str, Any]:
    definition = query["definition"]
    values = calculate_metric_series(df, definition)
    work = df.copy()
    work[definition["name"]] = values

    time_column = query.get("time_column")
    grain = query.get("time_grain")
    group_column = query.get("group_column")
    aggregation = query.get("aggregation", "sum")
    rank_direction = query.get("rank_direction")
    rank_limit = query.get("rank_limit")

    if time_column and grain:
        dates = pd.to_datetime(work[time_column], errors="coerce")
        if grain == "month":
            work["__time_group__"] = dates.dt.to_period("M").dt.to_timestamp("M")
        elif grain == "quarter":
            work["__time_group__"] = dates.dt.to_period("Q").dt.to_timestamp("Q")
        elif grain == "year":
            work["__time_group__"] = dates.dt.to_period("Y").dt.to_timestamp("Y")
        elif grain == "week":
            work["__time_group__"] = dates.dt.to_period("W").dt.to_timestamp("W")
        else:
            work["__time_group__"] = dates.dt.floor("D")
        keys = ["__time_group__"] + ([group_column] if group_column else [])
    else:
        keys = [group_column] if group_column else []

    valid = work.dropna(subset=[definition["name"]])
    if not keys:
        return {"handled": False, "intent": "calculated_metric", "reason": "No grouping dimension was detected."}

    grouped = valid.groupby(keys, dropna=False)
    if definition.get("operation") == "divide":
        numerator, denominator = definition["columns"]
        ratio_frame = work.copy()
        ratio_frame["__numerator__"] = pd.to_numeric(ratio_frame[numerator], errors="coerce")
        ratio_frame["__denominator__"] = pd.to_numeric(ratio_frame[denominator], errors="coerce")
        ratio_frame = ratio_frame.dropna(subset=["__numerator__", "__denominator__"])
        ratio_grouped = ratio_frame.groupby(keys, dropna=False)
        series = ratio_grouped["__numerator__"].sum().div(ratio_grouped["__denominator__"].sum().replace(0, pd.NA))
    else:
        # Use the shared performance engine for large datasets while keeping
        # identical result semantics for smaller datasets.
        result_df, engine_used = performance_aggregate(
            work, keys, definition["name"], aggregation
        )
        series = None

    if definition.get("operation") == "divide":
        result_df = series.reset_index(name="value")
        engine_used = "pandas"


    # Ranking applies to the final grouped result, not the raw rows.
    if rank_direction:
        result_df = result_df.sort_values("value", ascending=(rank_direction == "bottom"), kind="stable")
        result_df = result_df.head(rank_limit or 10)
    else:
        result_df = result_df.sort_values(keys, kind="stable").reset_index(drop=True)

    records: list[dict[str, Any]] = []
    for row in result_df.to_dict(orient="records"):
        cleaned = {}
        for key, value in row.items():
            if pd.isna(value):
                cleaned["period" if key == "__time_group__" else key] = None
            elif key == "__time_group__":
                cleaned["period"] = pd.Timestamp(value).strftime("%Y-%m")
            elif hasattr(value, "item"):
                cleaned[key] = value.item()
            else:
                cleaned[key] = value
        records.append(cleaned)

    label = definition["label"]
    if definition.get("operation") == "divide":
        calculation_text = f"{label} calculated as {definition['formula']} using aggregated numerator and denominator."
    else:
        calculation_text = f"{aggregation.title()} of {label} calculated using {definition['formula']}."

    if rank_direction:
        direction_text = "top" if rank_direction == "top" else "bottom"
        group_text = group_column or "time period"
        calculation_text += f" Ranked {direction_text} {rank_limit} by {group_text}."

    return {
        "handled": True,
        "intent": "calculated_metric_ranking" if rank_direction else "calculated_metric",
        "metric": label,
        "formula": definition["formula"],
        "source_columns": definition["columns"],
        "aggregation": aggregation.upper(),
        "time_column": time_column,
        "time_grain": grain,
        "group_by": group_column,
        "rank_direction": rank_direction,
        "rank_limit": rank_limit,
        "engine": engine_used,
        "results": records,
        "row_count_used": int(len(valid)),
        "direct_answer": calculation_text,
    }


def run_calculated_metric_query(df: pd.DataFrame, question: str) -> dict[str, Any]:
    query = build_calculated_query(df, question)
    if not query:
        return {"handled": False, "intent": "calculated_metric", "reason": "No supported calculated metric was detected."}
    try:
        return execute_calculated_query(df, query)
    except Exception as exc:
        return {"handled": False, "intent": "calculated_metric", "reason": f"Calculated metric could not be executed: {exc}"}
