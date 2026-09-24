"""Network/PCAP intelligence for InsightAI.

This module exposes both the richer network metrics API and the table helpers
used by the Network Intelligence Streamlit page.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _first_existing(df: pd.DataFrame, names: list[str]) -> str | None:
    lookup = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def _col(df: pd.DataFrame, names: list[str]) -> str | None:
    return _first_existing(df, names)


def analyze_network_capture(
    df: pd.DataFrame,
    capture_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "available": False,
            "reason": "No packets available.",
            "packet_count": 0,
            "total_bytes": 0,
            "duration_seconds": 0.0,
            "packets_per_second": 0.0,
            "bytes_per_second": 0.0,
        }

    protocol_col = _first_existing(
        df, ["_ws.col.protocol", "protocol", "protocols", "ip.proto", "frame.protocols", "frame_protocols"]
    )
    src_col = _first_existing(df, ["ip.src", "ipv6.src", "ip_src", "src_ip", "ipv4 source", "ipv4_source", "eth.src", "source"])
    dst_col = _first_existing(df, ["ip.dst", "ipv6.dst", "ip_dst", "dst_ip", "ipv4 destination", "ipv4_destination", "eth.dst", "destination"])
    length_col = _first_existing(df, ["frame.len", "frame_len", "packet length", "packet_length", "length", "len"])
    time_col = _first_existing(
        df, ["frame.time_epoch", "frame.time", "frame_time", "timestamp", "time"]
    )

    result: dict[str, Any] = {
        "available": True,
        "packet_count": int(len(df)),
        "protocols": {},
        "top_sources": {},
        "top_destinations": {},
        "total_bytes": 0,
        "duration_seconds": 0.0,
        "packets_per_second": 0.0,
        "bytes_per_second": 0.0,
        "unique_conversations": 0,
        "columns": {
            "protocol": protocol_col,
            "source": src_col,
            "destination": dst_col,
            "length": length_col,
            "time": time_col,
        },
    }

    if capture_metadata:
        result["capture_metadata"] = capture_metadata

    if protocol_col:
        result["protocols"] = (
            df[protocol_col].astype("string").fillna("Unknown").value_counts().head(20).to_dict()
        )

    if src_col:
        result["top_sources"] = (
            df[src_col].astype("string").fillna("Unknown").value_counts().head(10).to_dict()
        )

    if dst_col:
        result["top_destinations"] = (
            df[dst_col].astype("string").fillna("Unknown").value_counts().head(10).to_dict()
        )

    if length_col:
        lengths = pd.to_numeric(df[length_col], errors="coerce")
        if lengths.notna().any():
            result["total_bytes"] = int(lengths.sum())

    if time_col:
        raw = df[time_col]
        # TShark frame.time_epoch is numeric. Human-readable frame.time/timestamp
        # values require datetime parsing.
        numeric_time = pd.to_numeric(raw, errors="coerce")
        if numeric_time.notna().sum() >= 2:
            duration = float(numeric_time.max() - numeric_time.min())
        else:
            parsed_time = pd.to_datetime(raw, errors="coerce")
            duration = (
                float((parsed_time.max() - parsed_time.min()).total_seconds())
                if parsed_time.notna().sum() >= 2
                else 0.0
            )

        if duration >= 0:
            result["duration_seconds"] = round(duration, 6)
            if duration > 0:
                result["packets_per_second"] = round(len(df) / duration, 3)
                result["bytes_per_second"] = round(result["total_bytes"] / duration, 3)

    if src_col and dst_col:
        pairs = pd.DataFrame(
            {
                "src": df[src_col].astype("string"),
                "dst": df[dst_col].astype("string"),
            }
        ).dropna()
        result["unique_conversations"] = int(pairs.drop_duplicates().shape[0])

    return result


def protocol_distribution(df: pd.DataFrame) -> pd.DataFrame:
    col = _first_existing(
        df, ["_ws.col.protocol", "protocol", "protocols", "ip.proto", "frame.protocols", "frame_protocols"]
    )
    if not col:
        return pd.DataFrame()
    return (
        df[col]
        .fillna("Unknown")
        .astype(str)
        .value_counts()
        .rename_axis("Protocol")
        .reset_index(name="Packets")
    )


def top_endpoints(df: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    src = _first_existing(df, ["ip.src", "ipv6.src", "ip_src", "src_ip", "ipv4 source", "ipv4_source", "eth.src", "source"])
    dst = _first_existing(df, ["ip.dst", "ipv6.dst", "ip_dst", "dst_ip", "ipv4 destination", "ipv4_destination", "eth.dst", "destination"])
    if not src and not dst:
        return pd.DataFrame()

    parts = []
    if src:
        parts.append(
            df[src].fillna("Unknown").astype(str).value_counts()
            .rename_axis("Endpoint").reset_index(name="Source Packets")
        )
    if dst:
        parts.append(
            df[dst].fillna("Unknown").astype(str).value_counts()
            .rename_axis("Endpoint").reset_index(name="Destination Packets")
        )

    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part, on="Endpoint", how="outer")
    return result.fillna(0).sort_values(result.columns[1], ascending=False).head(limit)


def top_conversations(df: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    src = _first_existing(df, ["ip.src", "ipv6.src", "ip_src", "src_ip"])
    dst = _first_existing(df, ["ip.dst", "ipv6.dst", "ip_dst", "dst_ip"])
    if not src or not dst:
        return pd.DataFrame()

    out = pd.DataFrame(
        {
            "Source": df[src].fillna("Unknown").astype(str),
            "Destination": df[dst].fillna("Unknown").astype(str),
        }
    )
    return (
        out.groupby(["Source", "Destination"], as_index=False)
        .size()
        .rename(columns={"size": "Packets"})
        .sort_values("Packets", ascending=False)
        .head(limit)
    )


def network_summary_text(metrics: dict[str, Any]) -> str:
    if not metrics.get("available"):
        return "Network intelligence is not available for this dataset."
    lines = [f"Packets: {metrics.get('packet_count', 0):,}"]
    if metrics.get("total_bytes") is not None:
        lines.append(f"Bytes: {metrics['total_bytes']:,}")
    if metrics.get("duration_seconds") is not None:
        lines.append(f"Duration: {metrics['duration_seconds']:.3f} seconds")
    if metrics.get("packets_per_second") is not None:
        lines.append(f"Packets/sec: {metrics['packets_per_second']:,.2f}")
    if metrics.get("bytes_per_second") is not None:
        lines.append(f"Bytes/sec: {metrics['bytes_per_second']:,.2f}")
    if metrics.get("unique_conversations") is not None:
        lines.append(f"Unique source/destination pairs: {metrics['unique_conversations']:,}")
    return "\n".join(lines)
