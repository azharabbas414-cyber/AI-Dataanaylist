"""
InsightAI Dataset Detector
Classifies an already-loaded DataFrame and its source into a useful
high-level dataset type. This is intentionally lightweight and deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_TYPES = {
    "tabular": "Tabular Dataset",
    "time_series": "Time Series",
    "network_capture": "Network Capture",
    "log": "Log / Event Dataset",
    "unknown": "Unknown Dataset",
}


def _normalise_columns(columns) -> list[str]:
    return [str(c).strip().lower().replace(" ", "_") for c in columns]


def detect_dataset_type(
    df: pd.DataFrame,
    source_name: str | None = None,
    source_type: str | None = None,
) -> str:
    """Return one of: tabular, time_series, network_capture, log, unknown."""

    if df is None or not isinstance(df, pd.DataFrame):
        return "unknown"

    source = (source_name or "").lower()
    source_kind = (source_type or "").lower()

    if source_kind in {"pcap", "pcapng", "cap", "network_capture"}:
        return "network_capture"

    if Path(source).suffix.lower() in {".pcap", ".pcapng", ".cap"}:
        return "network_capture"

    cols = _normalise_columns(df.columns)
    colset = set(cols)

    network_markers = {
        "frame_number",
        "frame_time",
        "frame_len",
        "ip_src",
        "ip_dst",
        "tcp_srcport",
        "tcp_dstport",
        "udp_srcport",
        "udp_dstport",
        "ip_proto",
        "protocol",
        "_ws_col_protocol",
        "tcp_stream",
        "udp_stream",
    }

    if len(colset.intersection(network_markers)) >= 2:
        return "network_capture"

    log_markers = {
        "log",
        "message",
        "severity",
        "level",
        "event",
        "event_type",
        "timestamp",
        "datetime",
        "log_time",
    }
    if len(colset.intersection(log_markers)) >= 3 and (
        "message" in colset or "event" in colset or "log" in colset
    ):
        return "log"

    date_like = _find_datetime_columns(df)
    if date_like:
        return "time_series"

    return "tabular"


def _find_datetime_columns(df: pd.DataFrame) -> list[str]:
    found: list[str] = []

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            found.append(str(col))
            continue

        name = str(col).lower()
        date_hint = any(
            token in name
            for token in (
                "date",
                "time",
                "timestamp",
                "datetime",
                "month",
                "year",
            )
        )

        if date_hint and pd.api.types.is_object_dtype(series):
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() >= 0.70:
                found.append(str(col))

    return found


def get_dataset_capabilities(dataset_type: str) -> dict[str, bool]:
    """Describe which InsightAI features are naturally applicable."""
    common = {
        "profiling": True,
        "cleaning": True,
        "explorer": True,
        "dashboard": True,
        "ai_analysis": True,
        "anomaly_detection": True,
        "reporting": True,
    }

    if dataset_type == "time_series":
        common.update({"forecasting": True, "trend_analysis": True})
    else:
        common.update({"forecasting": False, "trend_analysis": False})

    if dataset_type == "network_capture":
        common.update(
            {
                "pcap_analysis": True,
                "network_protocol_analysis": True,
                "flow_analysis": True,
                "forecasting": False,
            }
        )
    else:
        common.update(
            {
                "pcap_analysis": False,
                "network_protocol_analysis": False,
                "flow_analysis": False,
            }
        )

    return common


def build_dataset_metadata(
    df: pd.DataFrame,
    source_name: str | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    """Create a serialisable metadata dictionary for the active dataset."""

    dataset_type = detect_dataset_type(df, source_name, source_type)

    numeric_columns = [
        str(c) for c in df.select_dtypes(include="number").columns
    ]
    categorical_columns = [
        str(c)
        for c in df.select_dtypes(include=["object", "category", "bool"]).columns
    ]
    datetime_columns = [
        str(c)
        for c in df.columns
        if pd.api.types.is_datetime64_any_dtype(df[c])
    ]

    missing_cells = int(df.isna().sum().sum())
    total_cells = max(int(df.shape[0] * df.shape[1]), 1)

    return {
        "name": source_name or "Active Dataset",
        "source_type": source_type or "",
        "dataset_type": dataset_type,
        "dataset_type_label": SUPPORTED_TYPES.get(dataset_type, dataset_type),
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "datetime_columns": datetime_columns,
        "missing_cells": missing_cells,
        "missing_percent": round((missing_cells / total_cells) * 100, 2),
        "duplicate_rows": int(df.duplicated().sum()),
        "capabilities": get_dataset_capabilities(dataset_type),
    }
