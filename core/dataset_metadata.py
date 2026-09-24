"""
InsightAI Dataset Metadata facade.

Keeps metadata creation in one place so future AI, dashboard, cleaning,
RAG and reporting modules can consume the same dataset description.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.dataset_detector import build_dataset_metadata


def create_metadata(
    df: pd.DataFrame,
    source_name: str | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    return build_dataset_metadata(df, source_name, source_type)


def metadata_summary(metadata: dict[str, Any]) -> str:
    """Return a compact text representation suitable for AI prompts."""
    return (
        f"Dataset: {metadata.get('name', 'Unknown')}\n"
        f"Type: {metadata.get('dataset_type_label', 'Unknown')}\n"
        f"Rows: {metadata.get('rows', 0):,}\n"
        f"Columns: {metadata.get('columns', 0):,}\n"
        f"Missing cells: {metadata.get('missing_cells', 0):,} "
        f"({metadata.get('missing_percent', 0):.2f}%)\n"
        f"Duplicate rows: {metadata.get('duplicate_rows', 0):,}\n"
        f"Numeric columns: {', '.join(metadata.get('numeric_columns', [])) or 'None'}\n"
        f"Categorical columns: {', '.join(metadata.get('categorical_columns', [])) or 'None'}\n"
        f"Datetime columns: {', '.join(metadata.get('datetime_columns', [])) or 'None'}"
    )
