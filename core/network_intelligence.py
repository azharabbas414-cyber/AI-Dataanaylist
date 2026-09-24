"""Network/PCAP intelligence for InsightAI."""
from __future__ import annotations

from typing import Any
import pandas as pd


def _first_existing(df: pd.DataFrame, names: list[str]) -> str | None:
    lookup = {str(c).lower(): str(c) for c in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def analyze_network_capture(df: pd.DataFrame, capture_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create deterministic network metrics from common TShark columns."""
    if df is None or df.empty:
        return {"available": False, "reason": "No packets available."}

    protocol_col = _first_existing(df, ["_ws.col.Protocol", "protocol", "ip.proto", "frame.protocols"])
    src_col = _first_existing(df, ["ip.src", "ipv6.src", "eth.src"])
    dst_col = _first_existing(df, ["ip.dst", "ipv6.dst", "eth.dst"])
    length_col = _first_existing(df, ["frame.len", "length", "len"])
    time_col = _first_existing(df, ["frame.time_epoch", "frame.time", "timestamp", "time"])
    tcp_stream_col = _first_existing(df, ["tcp.stream"])
    udp_stream_col = _first_existing(df, ["udp.stream"])

    result: dict[str, Any] = {
        "available": True,
        "packet_count": int(len(df)),
        "protocols": {},
        "top_sources": {},
        "top_destinations": {},
        "total_bytes": None,
        "duration_seconds": None,
        "packets_per_second": None,
        "bytes_per_second": None,
        "unique_conversations": None,
        "columns": {"protocol": protocol_col, "source": src_col, "destination": dst_col, "length": length_col, "time": time_col},
    }

    if capture_metadata:
        result["capture_metadata"] = capture_metadata

    if protocol_col:
        result["protocols"] = df[protocol_col].astype("string").fillna("Unknown").value_counts().head(20).to_dict()

    if src_col:
        result["top_sources"] = df[src_col].astype("string").fillna("Unknown").value_counts().head(10).to_dict()

    if dst_col:
        result["top_destinations"] = df[dst_col].astype("string").fillna("Unknown").value_counts().head(10).to_dict()

    if length_col:
        lengths = pd.to_numeric(df[length_col], errors="coerce")
        result["total_bytes"] = int(lengths.sum()) if lengths.notna().any() else None

    if time_col:
        times = pd.to_numeric(df[time_col], errors="coerce")
        if times.notna().sum() >= 2:
            duration = float(times.max() - times.min())
            if duration >= 0:
                result["duration_seconds"] = round(duration, 6)
                if duration > 0:
                    result["packets_per_second"] = round(len(df) / duration, 3)
                    if result["total_bytes"] is not None:
                        result["bytes_per_second"] = round(result["total_bytes"] / duration, 3)

    if src_col and dst_col:
        pairs = pd.DataFrame({"src": df[src_col].astype("string"), "dst": df[dst_col].astype("string")}).dropna()
        result["unique_conversations"] = int(pairs.drop_duplicates().shape[0])

    if tcp_stream_col or udp_stream_col:
        stream_cols = [c for c in [tcp_stream_col, udp_stream_col] if c]
        result["unique_streams"] = int(pd.concat([df[c].astype("string") for c in stream_cols]).nunique(dropna=True))

    return result


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
