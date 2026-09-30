"""Deterministic calculated-metric engine for InsightAI.

This module turns common business-language metrics into explicit formulas over
an active dataframe. Calculations remain deterministic and auditable; an LLM
may explain the result later but never performs the arithmetic itself.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


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

    # Prefer a column containing the full alias, then the shortest match.
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
    aliases = [
        "invoice date", "transaction date", "order date", "billing date",
        "joining date", "date", "timestamp", "datetime", "time", "month",
    ]
    found = _find_exact_or_alias(df, aliases)
    if found in datetime_columns:
        return found

    # Object columns that can be parsed as dates are considered only when the
    # question explicitly asks for a time grouping.
    q = _norm(question)
    if not any(token in q for token in ("month", "monthly", "year", "yearly", "date", "trend", "quarter", "week", "daily")):
        return None

    for column in df.columns:
        if column in datetime_columns:
            return column
        if not (df[column].dtype == "object" or pd.api.types.is_string_dtype(df[column])):
            continue
        sample = df[column].dropna().head(200)
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
        "country": ["country"],
        "region": ["region", "area", "territory", "market", "zone"],
        "product": ["product", "item", "sku", "product name"],
        "category": ["category", "segment", "type", "product category"],
        "customer": ["customer", "customer id", "client"],
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


def _metric_definition(df: pd.DataFrame, question: str) -> dict[str, Any] | None:
    """Infer a deterministic derived metric from the question."""
    q = _norm(question)

    numeric = set(df.select_dtypes(include="number").columns)
    if not numeric:
        return None

    # Existing explicit metric columns always take precedence over a derived
    # formula. This avoids redefining a dataset's own Revenue/Sale Price field.
    explicit_aliases = {
        "revenue": ["revenue", "total revenue", "sales revenue"],
        "sales_value": ["sales value", "sale value", "sales amount", "transaction value", "line total"],
        "profit": ["profit", "net profit", "gross profit", "earnings"],
        "margin": ["margin", "margin percent", "profit margin"],
    }

    if any(_norm(alias) in q for alias in explicit_aliases["revenue"]):
        existing = _find_exact_or_alias(df, explicit_aliases["revenue"], numeric_only=True)
        if existing:
            return {"name": existing, "label": existing, "formula": f"{existing}", "columns": [existing], "kind": "existing"}

    if any(_norm(alias) in q for alias in explicit_aliases["sales_value"]):
        existing = _find_exact_or_alias(df, explicit_aliases["sales_value"], numeric_only=True)
        if existing:
            return {"name": existing, "label": existing, "formula": f"{existing}", "columns": [existing], "kind": "existing"}

    # Quantity × UnitPrice is the standard transaction sales-value formula.
    if any(token in q for token in ("sales value", "sale value", "sales amount", "transaction value", "line total", "total sales")):
        quantity = _find_exact_or_alias(df, ["quantity", "qty", "order quantity", "units"], numeric_only=True)
        unit_price = _find_exact_or_alias(df, ["unitprice", "unit price", "price", "selling price"], numeric_only=True)
        if quantity and unit_price and quantity != unit_price:
            return {
                "name": "SalesValue",
                "label": "Sales Value",
                "formula": f"{quantity} × {unit_price}",
                "columns": [quantity, unit_price],
                "kind": "formula",
                "operation": "multiply",
            }

    # Revenue from usage × rate is useful for telecom datasets.
    if any(token in q for token in ("revenue", "billing", "bill value", "charge", "sales")):
        usage = _find_exact_or_alias(df, ["usage", "usage units", "data usage", "data gb", "minutes", "call minutes"], numeric_only=True)
        rate = _find_exact_or_alias(df, ["rate", "price per unit", "unit rate", "tariff"], numeric_only=True)
        if usage and rate and usage != rate and any(token in q for token in ("revenue", "billing", "bill value")):
            return {
                "name": "CalculatedRevenue",
                "label": "Calculated Revenue",
                "formula": f"{usage} × {rate}",
                "columns": [usage, rate],
                "kind": "formula",
                "operation": "multiply",
            }

    # Telecom ARPU / average revenue per user.
    if "arpu" in q or "average revenue per user" in q:
        revenue = _find_exact_or_alias(df, ["revenue", "total revenue", "sales", "billing", "total bill"], numeric_only=True)
        subscribers = _find_exact_or_alias(df, ["active subscribers", "subscribers", "subscriber count", "customers", "customer count"], numeric_only=True)
        if revenue and subscribers and revenue != subscribers:
            return {
                "name": "ARPU",
                "label": "ARPU",
                "formula": f"{revenue} ÷ {subscribers}",
                "columns": [revenue, subscribers],
                "kind": "formula",
                "operation": "divide",
            }

    return None


def calculate_metric_series(df: pd.DataFrame, definition: dict[str, Any]) -> pd.Series:
    """Create the metric series deterministically."""
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
    """Return an executable calculated-metric query description, if recognized."""
    definition = _metric_definition(df, question)
    if not definition:
        return None

    grain = _find_time_grain(question)
    date_column = _find_datetime_column(df, question) if grain else None
    group_column = _find_group_column(df, question, exclude={date_column} if date_column else set())

    q = _norm(question)
    aggregation = "sum"
    if re.search(r"\b(average|mean|avg)\b", q):
        aggregation = "mean"
    elif re.search(r"\bmedian\b", q):
        aggregation = "median"
    elif re.search(r"\bcount\b", q):
        aggregation = "count"

    # Derived metric queries are only handled when the question actually asks
    # for a grouped/aggregated result. Scalar calculated metrics can be added
    # later without changing this interface.
    if not grain and not group_column:
        return None

    return {
        "definition": definition,
        "time_column": date_column,
        "time_grain": grain,
        "group_column": group_column,
        "aggregation": aggregation,
    }


def execute_calculated_query(df: pd.DataFrame, query: dict[str, Any]) -> dict[str, Any]:
    """Execute a calculated metric query and return auditable evidence."""
    definition = query["definition"]
    values = calculate_metric_series(df, definition)
    work = df.copy()
    work[definition["name"]] = values

    time_column = query.get("time_column")
    grain = query.get("time_grain")
    group_column = query.get("group_column")
    aggregation = query.get("aggregation", "sum")

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
        keys = ["__time_group__"]
        if group_column:
            keys.append(group_column)
    else:
        keys = [group_column] if group_column else []

    valid = work.dropna(subset=[definition["name"]])
    if keys:
        grouped = valid.groupby(keys, dropna=False)

        # Ratios such as ARPU should be calculated from aggregated numerator
        # and denominator, not by summing row-level ratios.
        if definition.get("operation") == "divide":
            numerator, denominator = definition["columns"]
            numerator_values = pd.to_numeric(work[numerator], errors="coerce")
            denominator_values = pd.to_numeric(work[denominator], errors="coerce")
            ratio_frame = work.copy()
            ratio_frame["__numerator__"] = numerator_values
            ratio_frame["__denominator__"] = denominator_values
            ratio_frame = ratio_frame.dropna(subset=["__numerator__", "__denominator__"])
            ratio_grouped = ratio_frame.groupby(keys, dropna=False)
            numerator_sum = ratio_grouped["__numerator__"].sum()
            denominator_sum = ratio_grouped["__denominator__"].sum()
            series = numerator_sum.div(denominator_sum.replace(0, pd.NA))
        else:
            grouped_metric = grouped[definition["name"]]
            if aggregation == "mean":
                series = grouped_metric.mean()
            elif aggregation == "median":
                series = grouped_metric.median()
            elif aggregation == "count":
                series = grouped_metric.count()
            else:
                series = grouped_metric.sum()

        result_df = series.reset_index(name="value")
        result_df = result_df.sort_values(keys).reset_index(drop=True)

        records: list[dict[str, Any]] = []
        for row in result_df.to_dict(orient="records"):
            cleaned = {}
            for key, value in row.items():
                if pd.isna(value):
                    cleaned[key if key != "__time_group__" else "period"] = None
                elif key == "__time_group__":
                    cleaned["period"] = pd.Timestamp(value).strftime("%Y-%m")
                elif isinstance(value, (pd.Timestamp,)):
                    cleaned[key] = value.isoformat()
                else:
                    cleaned[key] = value.item() if hasattr(value, "item") else value
            records.append(cleaned)
    else:
        if aggregation == "mean":
            value = valid[definition["name"]].mean()
        elif aggregation == "median":
            value = valid[definition["name"]].median()
        elif aggregation == "count":
            value = valid[definition["name"]].count()
        else:
            value = valid[definition["name"]].sum()
        records = [{"value": value.item() if hasattr(value, "item") else value}]

    label = definition["label"]
    grouping_text = ""
    if time_column and grain:
        grouping_text = f" by {grain} using {time_column}"
    if group_column:
        grouping_text += f" and {group_column}"

    if definition.get("operation") == "divide":
        calculation_text = f"{label} calculated as {definition['formula']} using aggregated numerator and denominator."
    else:
        calculation_text = f"{aggregation.title()} of {label} calculated{grouping_text} using {definition['formula']}."

    return {
        "handled": True,
        "intent": "calculated_metric",
        "metric": label,
        "formula": definition["formula"],
        "source_columns": definition["columns"],
        "aggregation": aggregation.upper(),
        "time_column": time_column,
        "time_grain": grain,
        "group_by": group_column,
        "results": records,
        "row_count_used": int(len(valid)),
        "direct_answer": calculation_text,
    }


def run_calculated_metric_query(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """Public helper used by the query engine."""
    query = build_calculated_query(df, question)
    if not query:
        return {"handled": False, "intent": "calculated_metric", "reason": "No supported calculated metric was detected."}
    try:
        return execute_calculated_query(df, query)
    except Exception as exc:
        return {
            "handled": False,
            "intent": "calculated_metric",
            "reason": f"Calculated metric could not be executed: {exc}",
        }

