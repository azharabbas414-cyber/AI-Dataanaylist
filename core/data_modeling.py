"""Data modeling utilities for InsightAI.

Provides lightweight BI-style table registration, relationship inference,
validation and deterministic joins without introducing a database dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class Relationship:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    cardinality: str = "Many-to-One"
    join_type: str = "Left"

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_key(series: pd.Series) -> pd.Series:
    """Normalize join keys conservatively while preserving values."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return series.astype("string").str.strip().str.lower()


def key_profile(series: pd.Series) -> dict:
    s = normalize_key(series).dropna()
    return {
        "rows": int(len(series)),
        "non_null": int(s.notna().sum()),
        "unique": int(s.nunique(dropna=True)),
        "unique_ratio": float(s.nunique(dropna=True) / max(len(s), 1)),
    }


def infer_relationships(
    tables: Dict[str, pd.DataFrame],
    min_overlap: float = 0.25,
    max_candidates: int = 30,
) -> List[dict]:
    """Infer likely relationships using matching column names and key overlap."""
    names = list(tables.keys())
    candidates: List[dict] = []

    for i, left_name in enumerate(names):
        left = tables[left_name]
        for right_name in names[i + 1 :]:
            right = tables[right_name]
            common = set(left.columns).intersection(right.columns)
            for col in common:
                if left[col].isna().all() or right[col].isna().all():
                    continue
                lp = key_profile(left[col])
                rp = key_profile(right[col])
                if lp["unique"] == 0 or rp["unique"] == 0:
                    continue
                lvals = set(normalize_key(left[col]).dropna().head(10000).tolist())
                rvals = set(normalize_key(right[col]).dropna().head(10000).tolist())
                if not lvals or not rvals:
                    continue
                overlap = len(lvals & rvals) / max(1, min(len(lvals), len(rvals)))
                if overlap < min_overlap:
                    continue

                if lp["unique_ratio"] >= 0.95 and rp["unique_ratio"] < 0.95:
                    cardinality = "Many-to-One"
                elif rp["unique_ratio"] >= 0.95 and lp["unique_ratio"] < 0.95:
                    cardinality = "One-to-Many"
                elif lp["unique_ratio"] >= 0.95 and rp["unique_ratio"] >= 0.95:
                    cardinality = "One-to-One"
                else:
                    cardinality = "Many-to-Many"

                score = overlap
                if left_name.lower() in str(col).lower() or right_name.lower() in str(col).lower():
                    score += 0.05
                candidates.append(
                    {
                        "left_table": left_name,
                        "left_column": col,
                        "right_table": right_name,
                        "right_column": col,
                        "cardinality": cardinality,
                        "overlap": round(overlap, 3),
                        "score": round(score, 3),
                    }
                )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:max_candidates]


def validate_relationship(
    left: pd.DataFrame,
    left_column: str,
    right: pd.DataFrame,
    right_column: str,
) -> dict:
    if left_column not in left.columns or right_column not in right.columns:
        return {"valid": False, "message": "Join column not found."}

    lkey = normalize_key(left[left_column])
    rkey = normalize_key(right[right_column])
    lvals = set(lkey.dropna().tolist())
    rvals = set(rkey.dropna().tolist())
    matched = len(lvals & rvals)

    return {
        "valid": matched > 0,
        "left_rows": len(left),
        "right_rows": len(right),
        "left_unique": int(lkey.nunique(dropna=True)),
        "right_unique": int(rkey.nunique(dropna=True)),
        "matched_keys": matched,
        "left_unmatched_keys": len(lvals - rvals),
        "right_unmatched_keys": len(rvals - lvals),
        "message": "Relationship has matching keys." if matched else "No matching keys found.",
    }


def join_tables(
    left: pd.DataFrame,
    left_column: str,
    right: pd.DataFrame,
    right_column: str,
    how: str = "left",
    right_prefix: Optional[str] = None,
) -> Tuple[pd.DataFrame, dict]:
    """Perform a deterministic join using normalized temporary keys."""
    validation = validate_relationship(left, left_column, right, right_column)
    if not validation["valid"]:
        raise ValueError(validation["message"])

    l = left.copy()
    r = right.copy()
    l["__insightai_join_key__"] = normalize_key(l[left_column])
    r["__insightai_join_key__"] = normalize_key(r[right_column])

    # Avoid accidental column collisions while retaining both key columns.
    rename = {}
    for col in r.columns:
        if col == "__insightai_join_key__":
            continue
        if col in l.columns and col != right_column:
            prefix = right_prefix or "right"
            rename[col] = f"{prefix}_{col}"
    r = r.rename(columns=rename)

    result = l.merge(r, on="__insightai_join_key__", how=how, suffixes=("", "_right"))
    result = result.drop(columns=["__insightai_join_key__"])

    stats = {
        **validation,
        "input_left_rows": len(left),
        "input_right_rows": len(right),
        "output_rows": len(result),
        "join_type": how,
        "row_multiplier": round(len(result) / max(1, len(left)), 3),
    }
    return result, stats


def relationship_frame(relationships: List[dict]) -> pd.DataFrame:
    if not relationships:
        return pd.DataFrame(
            columns=["left_table", "left_column", "right_table", "right_column", "cardinality", "overlap"]
        )
    return pd.DataFrame(relationships)
