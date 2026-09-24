import streamlit as st
import pandas as pd
import plotly.express as px

from core.network_intelligence import (
    analyze_network_capture,
    protocol_distribution,
    top_endpoints,
    top_conversations,
)

try:
    from core.dataset_detector import detect_dataset_type
except Exception:
    detect_dataset_type = None

st.set_page_config(
    page_title="InsightAI - Network Intelligence",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 Network Intelligence")
st.caption("Network-aware analytics for PCAP, PCAPNG and packet datasets.")

df = st.session_state.get("active_dataframe")
dataset_name = st.session_state.get("active_dataset", "Dataset")
source_type = st.session_state.get("active_source_type", "")

if df is None:
    st.warning("No active dataset is selected.")
    st.info("Select or upload a PCAP/PCAPNG dataset from the Home page.")
    st.stop()

detected = (
    detect_dataset_type(df, dataset_name, source_type)
    if detect_dataset_type
    else "unknown"
)

if detected != "network_capture":
    st.info(
        f"Current dataset is detected as **{detected.replace('_', ' ').title()}**. "
        "Network Intelligence is designed for packet/network datasets."
    )
    st.stop()

try:
    summary = analyze_network_capture(df)
except Exception as exc:
    st.error(f"Network analysis could not be completed: {exc}")
    st.stop()

st.markdown("### Capture Overview")
cols = st.columns(5)
metrics = [
    ("Packets", summary.get("packet_count", 0), ","),
    ("Total Bytes", summary.get("total_bytes", 0), ","),
    ("Duration (sec)", summary.get("duration_seconds", 0), ".2f"),
    ("Packets / sec", summary.get("packets_per_second", 0), ".2f"),
    ("Bytes / sec", summary.get("bytes_per_second", 0), ".2f"),
]
for col, (label, value, fmt) in zip(cols, metrics):
    with col:
        st.metric(label, format(value, fmt) if isinstance(value, (int, float)) else str(value))

st.divider()
st.markdown("### Protocol Intelligence")
left, right = st.columns(2)

with left:
    st.subheader("Protocol Distribution")
    try:
        protocols = protocol_distribution(df)
    except Exception:
        protocols = pd.DataFrame()

    if protocols is not None and not protocols.empty:
        st.dataframe(protocols, use_container_width=True, hide_index=True)
        label_col = next(
            (c for c in protocols.columns if str(c).lower() in {"protocol", "name", "label"}),
            protocols.columns[0],
        )
        value_col = next(
            (c for c in protocols.columns if str(c).lower() in {"count", "packets", "value"}),
            protocols.columns[-1],
        )
        fig = px.pie(
            protocols,
            names=label_col,
            values=value_col,
            hole=0.45,
            title="Packets by Protocol",
        )
        fig.update_layout(margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Protocol information is not available in this dataset.")

with right:
    st.subheader("Network Summary")
    st.dataframe(
        pd.DataFrame(
            [
                ("Dataset", dataset_name),
                ("Detected Type", "Network Capture"),
                ("Rows / Packets", f"{len(df):,}"),
                ("Columns", f"{len(df.columns):,}"),
                ("Source Type", source_type or "Auto-detected"),
            ],
            columns=["Metric", "Value"],
        ),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.markdown("### Traffic Intelligence")
left, right = st.columns(2)

with left:
    st.subheader("Top Source / Destination Endpoints")
    try:
        endpoints = top_endpoints(df, limit=15)
    except Exception:
        endpoints = pd.DataFrame()
    if endpoints is not None and not endpoints.empty:
        st.dataframe(endpoints, use_container_width=True, hide_index=True)
    else:
        st.info("Source/destination fields were not available.")

with right:
    st.subheader("Top Conversations")
    try:
        conversations = top_conversations(df, limit=15)
    except Exception:
        conversations = pd.DataFrame()
    if conversations is not None and not conversations.empty:
        st.dataframe(conversations, use_container_width=True, hide_index=True)
    else:
        st.info("Conversation fields were not available.")

st.divider()
st.markdown("### Packet Data Explorer")
preview_cols = st.multiselect(
    "Columns to display",
    list(df.columns),
    default=list(df.columns[:8]),
)
st.dataframe(
    df[preview_cols].head(200) if preview_cols else df.head(200),
    use_container_width=True,
    height=450,
)
st.caption("InsightAI Network Intelligence • PCAP-aware analytics")
