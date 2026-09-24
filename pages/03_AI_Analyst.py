"""InsightAI AI Analyst / AI Command Center.

This is the existing 03_AI_Analyst.py page upgraded into the central AI
experience. No second AI page is required.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from ai.analyst import (
    answer_question,
    build_dataset_context,
)
from ai.provider import get_ai_provider
from core.analytics import analyze_dataset
from core.dataset_detector import detect_dataset_type


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="InsightAI - AI Analyst",
    page_icon="🤖",
    layout="wide",
)


# =========================================================
# SESSION STATE
# =========================================================

if "ai_conversation" not in st.session_state:
    st.session_state.ai_conversation = []

if "ai_last_answer" not in st.session_state:
    st.session_state.ai_last_answer = ""

if "ai_last_question" not in st.session_state:
    st.session_state.ai_last_question = ""


# =========================================================
# ACTIVE DATASET
# =========================================================

df = st.session_state.get("active_dataframe")

if df is None or not isinstance(df, pd.DataFrame):
    st.warning("No active dataset is selected.")
    st.info("Return to Home and select or upload a dataset.")

    if st.button("🏠 Go to Home", use_container_width=True):
        st.switch_page("streamlitapp.py")

    st.stop()

dataset_name = st.session_state.get(
    "active_dataset",
    "Active Dataset",
)

dataset_type = detect_dataset_type(
    df,
    source_name=dataset_name,
)


# =========================================================
# PROVIDER
# =========================================================

provider = get_ai_provider()
ai_available = bool(provider and provider.is_available())


# =========================================================
# HEADER
# =========================================================

st.title("🤖 AI Analyst")

st.caption(
    "InsightAI Command Center — ask questions, investigate findings, "
    "and understand what to investigate next."
)

header_left, header_mid, header_right = st.columns(3)

with header_left:
    st.metric("Active Dataset", str(dataset_name)[:30])

with header_mid:
    st.metric("Dataset Type", dataset_type.replace("_", " ").title())

with header_right:
    if ai_available:
        st.metric("AI Status", "Connected")
    else:
        st.metric("AI Status", "Local Analytics")


if ai_available:
    st.success(
        f"🟢 AI provider connected — {getattr(provider, 'provider_name', 'AI Provider')}"
    )
else:
    st.info(
        "🔵 AI provider is not configured. "
        "InsightAI will still answer using its local analytics and network engines."
    )


# =========================================================
# QUICK ACTIONS
# =========================================================

st.markdown("### ⚡ Quick Investigation")

quick_actions = [
    (
        "📌 Key Findings",
        "What are the most important findings in this dataset?",
    ),
    (
        "🧹 Data Quality",
        "Explain the data quality, missing values, duplicates, and what I should clean first.",
    ),
    (
        "🚨 Unusual Values",
        "Are there any unusual or suspicious values that I should investigate?",
    ),
    (
        "🔗 Relationships",
        "Which variables have the strongest relationships and what should I investigate?",
    ),
    (
        "🔎 What Next?",
        "What should I investigate next based on the available evidence?",
    ),
]

if dataset_type == "network_capture":
    quick_actions = [
        (
            "🌐 Network Summary",
            "Summarize this network capture and highlight the most important traffic observations.",
        ),
        (
            "📡 Protocols",
            "Which protocols dominate this capture?",
        ),
        (
            "🔗 Conversations",
            "What are the top source-to-destination conversations?",
        ),
        (
            "🎯 Endpoints",
            "Which endpoints generate the most traffic or packets?",
        ),
        (
            "🔎 What Next?",
            "What should I investigate next in this network capture?",
        ),
    ]

cols = st.columns(len(quick_actions))

for index, (label, prompt) in enumerate(quick_actions):
    with cols[index]:
        if st.button(
            label,
            key=f"quick_action_{index}",
            use_container_width=True,
        ):
            st.session_state.ai_pending_question = prompt


# =========================================================
# QUESTION INPUT
# =========================================================

pending_question = st.session_state.pop(
    "ai_pending_question",
    "",
)

st.markdown("### 💬 Ask InsightAI")
st.caption(
    "Ask a question about the active dataset. InsightAI will use the "
    "calculated evidence and your previous questions to investigate it."
)

# Use a normal visible text box instead of st.chat_input.
# st.chat_input is pinned to the bottom of the browser window, which can
# make it look like there is no question box in the main workspace.
question = st.text_area(
    "Your question",
    value=pending_question,
    placeholder=(
        "Example: What are the most important findings in this dataset?"
    ),
    height=100,
    key="ai_question_input",
)

ask_col, clear_col = st.columns([5, 1])
with ask_col:
    ask_question = st.button(
        "🚀 Ask InsightAI",
        type="primary",
        use_container_width=True,
    )
with clear_col:
    if st.button(
        "Clear",
        use_container_width=True,
        help="Clear the question box.",
    ):
        st.session_state.ai_question_input = ""
        st.rerun()

if ask_question and question:
    question = question.strip()

    if question:
        # Keep a compact conversation history for contextual follow-ups.
        history = st.session_state.ai_conversation[-10:]

        with st.spinner("InsightAI is analyzing the evidence..."):
            try:
                answer = answer_question(
                    question=question,
                    df=df,
                    dataset_name=dataset_name,
                    source_type=(
                        "network_capture"
                        if dataset_type == "network_capture"
                        else None
                    ),
                    provider=provider,
                    conversation=history,
                )

                st.session_state.ai_conversation.append(
                    {
                        "role": "user",
                        "content": question,
                    }
                )
                st.session_state.ai_conversation.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

                st.session_state.ai_last_question = question
                st.session_state.ai_last_answer = answer

            except Exception as error:
                st.error(f"AI analysis failed: {error}")

                st.info(
                    "InsightAI is showing the local analytics result instead."
                )

                # Retry without the external provider.
                try:
                    fallback = answer_question(
                        question=question,
                        df=df,
                        dataset_name=dataset_name,
                        source_type=(
                            "network_capture"
                            if dataset_type == "network_capture"
                            else None
                        ),
                        provider=None,
                        conversation=history,
                    )

                    st.session_state.ai_conversation.append(
                        {
                            "role": "user",
                            "content": question,
                        }
                    )
                    st.session_state.ai_conversation.append(
                        {
                            "role": "assistant",
                            "content": fallback,
                        }
                    )

                    st.session_state.ai_last_question = question
                    st.session_state.ai_last_answer = fallback

                except Exception as fallback_error:
                    st.error(
                        f"Local analysis also failed: {fallback_error}"
                    )


# =========================================================
# CONVERSATION
# =========================================================

if st.session_state.ai_conversation:
    st.markdown("### 🧠 Investigation")

    for message in st.session_state.ai_conversation:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        with st.chat_message(
            "user" if role == "user" else "assistant"
        ):
            st.markdown(content)

    if st.button(
        "🗑️ Clear Conversation",
        use_container_width=False,
    ):
        st.session_state.ai_conversation = []
        st.session_state.ai_last_answer = ""
        st.session_state.ai_last_question = ""
        st.rerun()


# =========================================================
# EVIDENCE / CONTEXT
# =========================================================

st.divider()

st.markdown("### 🔍 Evidence Available to InsightAI")

try:
    context = build_dataset_context(
        df,
        dataset_name=dataset_name,
        source_type=(
            "network_capture"
            if dataset_type == "network_capture"
            else None
        ),
    )

    evidence_col1, evidence_col2, evidence_col3 = st.columns(3)

    with evidence_col1:
        st.metric(
            "Rows / Packets",
            f"{int(context.get('rows', 0)):,}",
        )

    with evidence_col2:
        st.metric(
            "Columns",
            f"{int(context.get('column_count', 0)):,}",
        )

    with evidence_col3:
        if dataset_type == "network_capture":
            summary = context.get("network_intelligence", {}).get(
                "summary",
                {},
            )
            st.metric(
                "Conversations",
                f"{int(summary.get('unique_conversations', 0) or 0):,}",
            )
        else:
            analytics = context.get("analytics", {})
            health = analytics.get("health", {})
            st.metric(
                "Quality Score",
                f"{float(health.get('quality_score', 0) or 0):.1f}/100",
            )

    with st.expander("View AI evidence context"):
        # Keep this transparent without exposing credentials.
        if dataset_type == "network_capture":
            network = context.get("network_intelligence", {})
            st.write("**Network Summary**")
            st.json(network.get("summary", {}))

            protocols = network.get("protocols", [])
            if protocols:
                st.write("**Top Protocols**")
                st.dataframe(
                    pd.DataFrame(protocols),
                    use_container_width=True,
                    hide_index=True,
                )

            conversations = network.get("top_conversations", [])
            if conversations:
                st.write("**Top Conversations**")
                st.dataframe(
                    pd.DataFrame(conversations),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            analytics = context.get("analytics", {})
            health = analytics.get("health", {})
            st.write("**Dataset Health**")
            st.json(health)

            findings = analytics.get("findings", [])
            if findings:
                st.write("**Calculated Findings**")
                for finding in findings:
                    st.write(f"• {finding}")

            correlations = analytics.get("correlations", [])
            if correlations:
                st.write("**Top Correlations**")
                st.dataframe(
                    pd.DataFrame(correlations),
                    use_container_width=True,
                    hide_index=True,
                )

except Exception as error:
    st.warning(f"Evidence preview is unavailable: {error}")


# =========================================================
# LOCAL ANALYTICS SNAPSHOT
# =========================================================

if dataset_type != "network_capture":
    st.divider()
    st.markdown("### 📊 Analytics Snapshot")

    try:
        analysis = analyze_dataset(df)
        health = analysis.get("health", {})

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Completeness",
                f"{health.get('completeness', 0):.2f}%",
            )

        with c2:
            st.metric(
                "Missing Values",
                f"{health.get('missing_values', 0):,}",
            )

        with c3:
            st.metric(
                "Duplicate Rows",
                f"{health.get('duplicate_rows', 0):,}",
            )

        with c4:
            st.metric(
                "Quality Score",
                f"{health.get('quality_score', 0):.1f}/100",
            )

        findings = analysis.get("findings", [])

        if findings:
            with st.expander("Automatic Findings", expanded=False):
                for finding in findings:
                    st.info(finding)

    except Exception as error:
        st.warning(f"Analytics snapshot is unavailable: {error}")


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "InsightAI • AI Analyst / Command Center • "
    "Evidence-grounded analysis"
)
