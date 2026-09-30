
"""Performance engine for InsightAI.

Automatically chooses Pandas for small datasets and DuckDB for larger analytical
workloads. DuckDB is used lazily so InsightAI can still run when it is not
installed; the engine falls back to Pandas with no change to user-facing APIs.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

import pandas as pd

try:
    import duckdb  # type: ignore
except Exception:  # pragma: no cover
    duckdb = None

DEFAULT_ROW_THRESHOLD = 100_000
DEFAULT_MEMORY_THRESHOLD_MB = 256


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def estimate_memory_mb(df: pd.DataFrame) -> float:
    try:
        return float(df.memory_usage(index=True, deep=True).sum()) / (1024 ** 2)
    except Exception:
        return 0.0


def choose_engine(
    df: pd.DataFrame,
    row_threshold: int = DEFAULT_ROW_THRESHOLD,
    memory_threshold_mb: float = DEFAULT_MEMORY_THRESHOLD_MB,
) -> str:
    """Return ``duckdb`` for large analytical datasets, otherwise ``pandas``."""
    if not isinstance(df, pd.DataFrame):
        return "pandas"
    if duckdb is None:
        return "pandas"
    if len(df) >= row_threshold or estimate_memory_mb(df) >= memory_threshold_mb:
        return "duckdb"
    return "pandas"


def engine_info(df: pd.DataFrame) -> dict[str, Any]:
    engine = choose_engine(df)
    return {
        "engine": engine,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "memory_mb": round(estimate_memory_mb(df), 2),
        "duckdb_available": duckdb is not None,
        "row_threshold": DEFAULT_ROW_THRESHOLD,
        "memory_threshold_mb": DEFAULT_MEMORY_THRESHOLD_MB,
    }


def _pandas_aggregate(
    df: pd.DataFrame,
    group_by: list[str],
    value_col: str,
    aggregation: str,
) -> pd.DataFrame:
    grouped = df.groupby(group_by, dropna=False)[value_col]
    agg = aggregation.lower()
    if agg == "sum":
        series = grouped.sum()
    elif agg in {"mean", "avg", "average"}:
        series = grouped.mean()
    elif agg == "median":
        series = grouped.median()
    elif agg == "min":
        series = grouped.min()
    elif agg == "max":
        series = grouped.max()
    elif agg == "count":
        series = grouped.count()
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    return series.reset_index(name="value")


def aggregate(
    df: pd.DataFrame,
    group_by: str | Iterable[str],
    value_col: str,
    aggregation: str = "sum",
    *,
    sort_desc: bool | None = None,
    limit: int | None = None,
) -> tuple[pd.DataFrame, str]:
    """Aggregate a dataframe and return ``(result, engine_used)``.

    The result always contains grouping columns followed by ``value``.
    """
    groups = [group_by] if isinstance(group_by, str) else list(group_by)
    if not groups:
        raise ValueError("At least one group-by column is required")
    missing = [c for c in [*groups, value_col] if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}")

    engine = choose_engine(df)
    if engine == "pandas":
        result = _pandas_aggregate(df, groups, value_col, aggregation)
    else:
        con = duckdb.connect(database=":memory:")
        try:
            con.register("insightai_df", df)
            select_groups = ", ".join(_quote_identifier(c) for c in groups)
            value = _quote_identifier(value_col)
            agg = aggregation.lower()
            agg_map = {
                "sum": f"SUM({value})",
                "mean": f"AVG({value})",
                "avg": f"AVG({value})",
                "average": f"AVG({value})",
                "median": f"MEDIAN({value})",
                "min": f"MIN({value})",
                "max": f"MAX({value})",
                "count": f"COUNT({value})",
            }
            if agg not in agg_map:
                raise ValueError(f"Unsupported aggregation: {aggregation}")
            sql = (
                f"SELECT {select_groups}, {agg_map[agg]} AS value "
                f"FROM insightai_df GROUP BY {select_groups}"
            )
            result = con.execute(sql).df()
        finally:
            con.close()

    if sort_desc is not None:
        result = result.sort_values("value", ascending=not sort_desc, kind="stable")
    if limit is not None:
        result = result.head(max(0, int(limit)))
    return result.reset_index(drop=True), engine


def total(df: pd.DataFrame, value_col: str) -> tuple[float, str]:
    if choose_engine(df) == "duckdb":
        con = duckdb.connect(database=":memory:")
        try:
            con.register("insightai_df", df)
            value = con.execute(
                f"SELECT SUM({_quote_identifier(value_col)}) FROM insightai_df"
            ).fetchone()[0]
        finally:
            con.close()
        return float(value or 0), "duckdb"
    return float(pd.to_numeric(df[value_col], errors="coerce").sum()), "pandas"
