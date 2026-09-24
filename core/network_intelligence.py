"""Network-aware analytics for packet DataFrames."""
from __future__ import annotations
import pandas as pd

def _col(df, names):
    lower = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n in lower:
            return lower[n]
    return None

def analyze_network_capture(df):
    time_col = _col(df, ["frame_time", "frame.time", "timestamp", "time"])
    len_col = _col(df, ["frame_len", "frame.len", "length", "len"])
    packets = len(df)
    total_bytes = int(pd.to_numeric(df[len_col], errors="coerce").fillna(0).sum()) if len_col else 0
    duration = 0.0
    if time_col:
        t = pd.to_datetime(df[time_col], errors="coerce")
        if t.notna().any():
            duration = max(0.0, (t.max() - t.min()).total_seconds())
    return {
        "packet_count": packets,
        "total_bytes": total_bytes,
        "duration_seconds": duration,
        "packets_per_second": packets / duration if duration else 0.0,
        "bytes_per_second": total_bytes / duration if duration else 0.0,
    }

def protocol_distribution(df):
    col = _col(df, ["protocol", "_ws.col.protocol", "frame_protocols", "ip_proto"])
    if not col:
        return pd.DataFrame()
    return df[col].fillna("Unknown").astype(str).value_counts().rename_axis("Protocol").reset_index(name="Packets")

def top_endpoints(df, limit=15):
    src = _col(df, ["ip_src", "ip.src", "src_ip", "source"])
    dst = _col(df, ["ip_dst", "ip.dst", "dst_ip", "destination"])
    if not src and not dst:
        return pd.DataFrame()
    parts = []
    if src:
        parts.append(df[src].fillna("Unknown").astype(str).value_counts().rename_axis("Endpoint").reset_index(name="Source Packets"))
    if dst:
        parts.append(df[dst].fillna("Unknown").astype(str).value_counts().rename_axis("Endpoint").reset_index(name="Destination Packets"))
    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part, on="Endpoint", how="outer")
    return result.fillna(0).head(limit)

def top_conversations(df, limit=15):
    src = _col(df, ["ip_src", "ip.src", "src_ip"])
    dst = _col(df, ["ip_dst", "ip.dst", "dst_ip"])
    if not src or not dst:
        return pd.DataFrame()
    out = df.copy()
    out["Source"] = out[src].fillna("Unknown").astype(str)
    out["Destination"] = out[dst].fillna("Unknown").astype(str)
    return out.groupby(["Source", "Destination"], as_index=False).size().rename(columns={"size": "Packets"}).sort_values("Packets", ascending=False).head(limit)
