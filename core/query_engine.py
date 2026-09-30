"""Deterministic, semantic dataframe query engine for InsightAI.

The query engine resolves the user's analytical intent first and performs the
calculation directly on the dataframe. The LLM is used only to explain the
calculated evidence.

Design goals:
- Prefer exact/near-exact column names over loose aliases.
- Distinguish a row-level maximum from a grouped maximum.
- Understand common dimensions such as product, category, region and customer.
- Understand time phrases such as monthly, weekly and daily.
- Return a transparent calculation plan/evidence object for the AI Analyst.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


TIME_WORDS = {
    "hourly": "H",
    "hour": "H",
    "daily": "D",
    "day": "D",
    "weekly": "W",
    "week": "W",
    "monthly": "ME",
    "month": "ME",
    "quarterly": "QE",
    "quarter": "QE",
    "yearly": "YE",
    "annual": "YE",
    "annually": "YE",
    "year": "YE",
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in _norm(value).split() if token}


def _is_numeric_series(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.select_dtypes(include="number").columns]


def _categorical_columns(df: pd.DataFrame) -> list[str]:
    return [
        str(c)
        for c in df.select_dtypes(include=["object", "category", "bool"]).columns
    ]


def _datetime_columns(df: pd.DataFrame) -> list[str]:
    result: list[str] = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            result.append(str(column))
            continue
        name = _norm(column)
        if not any(word in name.split() for word in ("date", "time", "timestamp", "datetime", "month", "year")):
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().mean() >= 0.60:
            result.append(str(column))
    return result


def _column_match_score(column: str, phrase: str) -> float:
    """Score how well a real column matches a user phrase.

    Exact normalized names are heavily preferred. This is what prevents
    'Sale Price' from accidentally resolving to 'Unit Price'.
    """
    c = _norm(column)
    p = _norm(phrase)
    if not p or not c:
        return -1.0
    if c == p:
        return 1000.0
    if c.startswith(p + " ") or c.endswith(" " + p):
        return 850.0 + len(p)
    if p in c:
        return 700.0 + len(p) / max(len(c), 1)
    ct = _tokens(c)
    pt = _tokens(p)
    if pt and pt.issubset(ct):
        return 600.0 + len(pt) * 10 - (len(ct) - len(pt))
    overlap = len(ct & pt)
    if overlap:
        return 300.0 + overlap * 20 - abs(len(ct) - len(pt))
    return -1.0


def _find_best_column(
    df: pd.DataFrame,
    phrases: list[str],
    allowed: list[str] | None = None,
    exclude: set[str] | None = None,
) -> str | None:
    candidates = allowed if allowed is not None else [str(c) for c in df.columns]
    exclude = exclude or set()
    best: tuple[float, str] | None = None
    for phrase in phrases:
        for column in candidates:
            if column in exclude:
                continue
            score = _column_match_score(column, phrase)
            if score < 0:
                continue
            # Prefer numeric columns when the caller is resolving a metric.
            item = (score, column)
            if best is None or item[0] > best[0]:
                best = item
    return best[1] if best else None


def _question_metric_phrase(question: str) -> str | None:
    q = _norm(question)

    # Explicit metric phrases have priority over generic aliases.
    patterns = [
        r"(?:total|sum|average|mean|median|maximum|max|minimum|min|highest|lowest|top\s+\d+|bottom\s+\d+)\s+(?:of\s+)?(.+?)(?:\s+by\s+|\s+per\s+|\s+for\s+|$)",
        r"(?:by|per)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            phrase = match.group(1).strip()
            phrase = re.sub(r"\b(?:product|category|region|customer|month|year|week|day)\b$", "", phrase).strip()
            if phrase:
                return phrase

    # Common explicit phrases used in business/telecom data.
    aliases = [
        "sale price", "selling price", "unit price", "total price",
        "total bill", "monthly bill", "billing amount", "charge", "charges",
        "revenue", "sales", "profit", "margin", "cost", "expense",
        "quantity", "order quantity", "data usage", "usage", "traffic",
        "throughput", "latency", "duration", "call duration", "sms",
    ]
    for alias in aliases:
        if alias in q:
            return alias
    return None


def _numeric_column(df: pd.DataFrame, question: str) -> str | None:
    numeric = _numeric_columns(df)
    if not numeric:
        return None

    q = _norm(question)

    # First pass: exact/strong real-column mentions. This is the critical
    # protection against 'sale price' being matched to 'unit price'.
    mentioned = []
    for column in numeric:
        nc = _norm(column)
        if nc and (nc in q or _tokens(nc).issubset(_tokens(q))):
            mentioned.append((1000 + len(nc), column))
    if mentioned:
        return max(mentioned)[1]

    phrase = _question_metric_phrase(question)
    if phrase:
        found = _find_best_column(df, [phrase], allowed=numeric)
        if found:
            return found

    # Alias matching is deliberately conservative and scored against actual
    # columns rather than returning the first substring match.
    alias_groups = [
        ["profit", "net profit", "gross profit", "earnings"],
        ["sale price", "selling price", "total sale price", "sales price"],
        ["revenue", "turnover"],
        ["sales"],
        ["unit price"],
        ["cost", "expense", "expenses"],
        ["quantity", "qty", "units", "volume"],
        ["traffic", "bandwidth", "bytes"],
        ["throughput"],
        ["latency"],
        ["duration", "minutes"],
        ["rating", "score"],
    ]
    best: tuple[float, str] | None = None
    for aliases in alias_groups:
        if not any(alias in q for alias in aliases):
            continue
        found = _find_best_column(df, aliases, allowed=numeric)
        if found:
            score = max(_column_match_score(found, alias) for alias in aliases)
            # Explicitly mentioned aliases beat generic ones.
            candidate = (score + 100, found)
            if best is None or candidate[0] > best[0]:
                best = candidate
    return best[1] if best else None


def _dimension_phrase(question: str) -> list[str]:
    q = _norm(question)
    phrases: list[str] = []

    # Preserve multi-word dimensions first.
    for pattern in [r"\bby\s+(.+?)(?:\s+using\s+|\s+with\s+|$)", r"\bper\s+(.+)$", r"\bwhich\s+(.+?)\s+(?:has|have|with|generated|made|shows|is)\b"]:
        match = re.search(pattern, q)
        if match:
            value = match.group(1).strip()
            if value:
                phrases.append(value)

    # Explicit domain dimensions.
    for phrase in [
        "product category", "sub category", "subcategory", "product",
        "customer", "customer id", "region", "location", "zone", "city",
        "country", "department", "segment", "plan", "service type",
        "status", "payment method", "cell id", "site id", "operator",
    ]:
        if phrase in q:
            phrases.append(phrase)
    return list(dict.fromkeys(phrases))


def _group_column(df: pd.DataFrame, question: str, metric: str | None = None) -> str | None:
    categorical = _categorical_columns(df)
    if not categorical:
        return None

    phrases = _dimension_phrase(question)
    if phrases:
        # Prefer the longest/highest quality phrase. This makes 'product
        # category' resolve to Product Category instead of Product.
        scored: list[tuple[float, str]] = []
        for phrase in phrases:
            for column in categorical:
                score = _column_match_score(column, phrase)
                if score >= 0:
                    scored.append((score + len(_tokens(phrase)) * 5, column))
        if scored:
            return max(scored)[1]

    return None


def _find_time_column(df: pd.DataFrame, question: str) -> str | None:
    dates = _datetime_columns(df)
    if not dates:
        return None
    q = _norm(question)
    explicit = [c for c in dates if _norm(c) in q]
    if explicit:
        return max(explicit, key=len)
    return dates[0]


def _time_grain(question: str) -> tuple[str | None, str | None]:
    q = _norm(question)
    for word, code in TIME_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return code, word
    return None, None


def _aggregation(question: str) -> str | None:
    q = _norm(question)
    if any(x in q for x in ("average", "mean", "avg")):
        return "mean"
    if "median" in q:
        return "median"
    if any(x in q for x in ("count", "number of", "how many")):
        return "count"
    if any(x in q for x in ("minimum", "minimum", "lowest", "smallest", "min")):
        return "min"
    if any(x in q for x in ("maximum", "highest", "largest", "max")):
        return "max"
    if any(x in q for x in ("total", "sum", "overall", "revenue")):
        return "sum"
    return None


def _fmt_number(value: Any) -> str:
    try:
        v = float(value)
        if v.is_integer():
            return f"{int(v):,}"
        return f"{v:,.2f}"
    except Exception:
        return str(value)


def _safe_records(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return frame.head(limit).where(pd.notna(frame.head(limit)), None).to_dict(orient="records")


def _grouped_metric(df: pd.DataFrame, group: str, metric: str, aggregation: str) -> pd.Series:
    series = pd.to_numeric(df[metric], errors="coerce")
    work = pd.DataFrame({group: df[group].fillna("Missing").astype(str), metric: series}).dropna(subset=[metric])
    if work.empty:
        return pd.Series(dtype=float)
    return work.groupby(group, dropna=False)[metric].agg(aggregation)


def _time_grouped_metric(df: pd.DataFrame, date_column: str, metric: str, aggregation: str, grain: str) -> pd.DataFrame:
    work = df[[date_column, metric]].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce")
    if aggregation == "count":
        work[metric] = 1
    else:
        work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=[date_column])
    if aggregation != "count":
        work = work.dropna(subset=[metric])
    if work.empty:
        return pd.DataFrame(columns=[date_column, metric])
    indexed = work.set_index(date_column)
    grouped = indexed[metric].resample(grain).agg(aggregation).dropna().reset_index()
    return grouped.sort_values(date_column).reset_index(drop=True)


def _base_result(question: str, metric: str | None, group: str | None) -> dict[str, Any]:
    return {
        "handled": False,
        "intent": "unknown",
        "question": question,
        "metric": metric,
        "group_by": group,
        "aggregation": None,
        "time_column": None,
        "time_grain": None,
        "calculation": None,
        "evidence": {},
    }


def query_dataframe(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """Resolve and execute common analytical questions deterministically."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"handled": False, "reason": "The active dataset is empty."}

    question = str(question or "").strip()
    q = _norm(question)
    metric = _numeric_column(df, question)
    group = _group_column(df, question, metric)
    aggregation = _aggregation(question)
    time_column = _find_time_column(df, question)
    time_code, time_label = _time_grain(question)

    result = _base_result(question, metric, group)
    result.update(
        aggregation=aggregation,
        time_column=time_column if time_code else None,
        time_grain=time_label,
    )

    # Basic dataset questions.
    if any(x in q for x in ("how many rows", "row count", "number of rows", "how many records", "record count")):
        result.update(
            handled=True,
            intent="row_count",
            value=int(len(df)),
            calculation="COUNT(rows)",
            direct_answer=f"The dataset contains {_fmt_number(len(df))} rows.",
            evidence={"rows": int(len(df))},
        )
        return result

    if "missing" in q and metric is None:
        missing = df.isna().sum().sort_values(ascending=False)
        missing = missing[missing > 0]
        result.update(
            handled=True,
            intent="missing_values",
            calculation="COUNT_NULLS(column)",
            results=[{"column": str(k), "missing": int(v)} for k, v in missing.items()],
            direct_answer=(
                "No missing values were detected."
                if missing.empty
                else "Missing values are present; see the calculated column-level counts."
            ),
            evidence={"missing_by_column": {str(k): int(v) for k, v in missing.items()}},
        )
        return result

    # Time-series questions: monthly/daily/weekly/etc. grouped results.
    if metric and time_code and time_column:
        agg = aggregation or "sum"
        if agg == "max" and any(x in q for x in ("highest", "maximum", "max")):
            # 'highest monthly sale price' means the maximum observation per period.
            pass
        try:
            grouped = _time_grouped_metric(df, time_column, metric, agg, time_code)
        except Exception:
            grouped = pd.DataFrame()
        if not grouped.empty:
            display = grouped.copy()
            display[time_column] = display[time_column].astype(str)
            records = _safe_records(display, 120)
            result.update(
                handled=True,
                intent="time_group",
                aggregation=agg,
                calculation=f"{agg.upper()}({metric}) GROUP BY {time_label or time_code}",
                results=records,
                direct_answer=(
                    f"Calculated {agg} of {metric} by {time_label or 'time period'} using {time_column}. "
                    f"There are {len(records)} calculated periods."
                ),
                evidence={
                    "time_column": time_column,
                    "time_grain": time_label or time_code,
                    "aggregation": agg,
                    "metric": metric,
                    "periods": records,
                },
            )
            return result

    # Grouped questions. Explicit 'by X', 'per X' and 'which X has...' are
    # interpreted as group-level analysis rather than a single-row extreme.
    wants_max = any(x in q for x in ("maximum", "max", "highest", "largest", "most"))
    wants_min = any(x in q for x in ("minimum", "min", "lowest", "smallest", "least"))
    explicit_group_extreme = group is not None and (wants_max or wants_min)

    top_match = re.search(r"(?:top|highest)\s+(\d+)", q)
    bottom_match = re.search(r"(?:bottom|lowest)\s+(\d+)", q)

    if metric and group and (top_match or bottom_match):
        n = max(1, min(int((top_match or bottom_match).group(1)), 50))
        ascending = bool(bottom_match)
        grouped = _grouped_metric(df, group, metric, "sum").sort_values(ascending=ascending).head(n)
        records = [{group: idx, f"total_{metric}": float(value)} for idx, value in grouped.items()]
        result.update(
            handled=True,
            intent="ranking",
            aggregation="sum",
            calculation=f"SUM({metric}) GROUP BY {group} ORDER BY {'ASC' if ascending else 'DESC'} LIMIT {n}",
            results=records,
            direct_answer=f"Here are the {('bottom' if ascending else 'top')} {n} {group} values ranked by total {metric}.",
            evidence={"group_by": group, "metric": metric, "aggregation": "sum", "ranking": records},
        )
        return result

    if metric and group and (explicit_group_extreme or aggregation in {"sum", "mean", "median", "min", "max", "count"}):
        # For questions such as "which product has maximum profit" or
        # "highest total sale price by product", users normally mean the
        # cumulative metric for each group. Only an explicit "individual"
        # or "single transaction" wording should force a row-level extreme.
        if wants_max or wants_min:
            explicit_row_extreme = any(phrase in q for phrase in (
                "individual", "single transaction", "one transaction", "single row", "one row"
            ))
            agg = aggregation if aggregation in {"sum", "mean", "median", "min", "max", "count"} and not ("total" in q and aggregation == "max") else None
            if not explicit_row_extreme:
                agg = "sum"
            if agg is None:
                agg = "max" if wants_max else "min"
        else:
            agg = aggregation or "sum"
        grouped = _grouped_metric(df, group, metric, agg)
        if not grouped.empty:
            ascending = agg in {"min"} or wants_min
            if agg == "count":
                ascending = False
            grouped = grouped.sort_values(ascending=ascending)
            records = [{group: idx, f"{agg}_{metric}": float(value)} for idx, value in grouped.head(50).items()]
            first = records[0]
            result.update(
                handled=True,
                intent="group_aggregate",
                aggregation=agg,
                calculation=f"{agg.upper()}({metric}) GROUP BY {group}",
                results=records,
                direct_answer=(
                    f"The {group} with the {'highest' if not ascending else 'lowest'} {agg} {metric} "
                    f"is **{first[group]}** at **{_fmt_number(first[f'{agg}_{metric}'])}**."
                ),
                evidence={
                    "group_by": group,
                    "metric": metric,
                    "aggregation": agg,
                    "groups": records,
                },
            )
            return result

    # Row-level maximum/minimum. If a group is mentioned but the question is
    # not asking for a total/average/etc., provide both interpretations so the
    # ambiguity is explicit rather than silently choosing one.
    if metric and (wants_max or wants_min):
        clean = pd.to_numeric(df[metric], errors="coerce")
        valid = clean.dropna()
        if valid.empty:
            result.update(handled=True, intent="extreme", direct_answer=f"No usable values are available for {metric}.")
            return result
        extreme_value = float(valid.max() if wants_max else valid.min())
        rows = df.loc[clean.eq(extreme_value)].head(20)
        row_records = _safe_records(rows, 20)
        direction = "maximum" if wants_max else "minimum"
        direct = f"The {direction} individual {metric} is **{_fmt_number(extreme_value)}**."

        evidence: dict[str, Any] = {
            "metric": metric,
            "extreme_type": "maximum" if wants_max else "minimum",
            "value": extreme_value,
            "matching_rows": row_records,
        }

        if group:
            grouped = _grouped_metric(df, group, metric, "sum").sort_values(ascending=not wants_max).head(10)
            group_records = [{group: idx, f"total_{metric}": float(value)} for idx, value in grouped.items()]
            if group_records:
                best = group_records[0]
                direct += (
                    f" The **highest cumulative {metric} by {group}** is **{best[group]}**, "
                    f"with **{_fmt_number(best[f'total_{metric}'])}**."
                )
                evidence["group_totals"] = group_records

        result.update(
            handled=True,
            intent="extreme",
            aggregation="max" if wants_max else "min",
            calculation=f"{direction.upper()}({metric})",
            extreme_value=extreme_value,
            matching_rows=row_records,
            direct_answer=direct,
            evidence=evidence,
        )
        return result

    # Scalar metric questions.
    if metric:
        agg = aggregation
        if agg in {"sum", "mean", "median", "min", "max"}:
            series = pd.to_numeric(df[metric], errors="coerce").dropna()
            if series.empty:
                result.update(handled=True, intent="scalar", direct_answer=f"No usable values are available for {metric}.")
                return result
            if agg == "sum": value = series.sum()
            elif agg == "mean": value = series.mean()
            elif agg == "median": value = series.median()
            elif agg == "min": value = series.min()
            else: value = series.max()
            label = {"sum": "total", "mean": "average", "median": "median", "min": "minimum", "max": "maximum"}[agg]
            result.update(
                handled=True,
                intent="scalar",
                aggregation=agg,
                calculation=f"{agg.upper()}({metric})",
                value=float(value),
                direct_answer=f"The {label} {metric} is **{_fmt_number(value)}**.",
                evidence={"metric": metric, "aggregation": agg, "value": float(value)},
            )
            return result

    return result
