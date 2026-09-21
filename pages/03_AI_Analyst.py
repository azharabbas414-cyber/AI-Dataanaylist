import streamlit as st

from core.analytics import analyze_dataset
from ai.analyst import (
    build_prompt,
    fallback_analysis,
)
from ai.provider import get_ai_provider


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="InsightAI - AI Analyst",
    page_icon="🤖",
    layout="wide",
)


# =========================================================
# ACTIVE DATASET
# =========================================================

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):

    st.warning(
        "No active dataset is selected."
    )

    st.info(
        "Return to Home and select or upload a dataset."
    )

    if st.button("🏠 Go to Home"):

        st.switch_page(
            "streamlitapp.py"
        )

    st.stop()


df = st.session_state.active_dataframe

dataset_name = st.session_state.get(
    "active_dataset",
    "Dataset"
)


# =========================================================
# ANALYTICS ENGINE
# =========================================================

analysis = analyze_dataset(df)


# =========================================================
# HEADER
# =========================================================

st.title("🤖 AI Data Analyst")

st.caption(
    f"Ask questions about **{dataset_name}**"
)


# =========================================================
# STATUS
# =========================================================

provider = get_ai_provider()

if provider and provider.is_available():

    st.success(
        "🟢 AI provider connected"
    )

    ai_available = True

else:

    st.info(
        "🔵 AI provider is not configured. "
        "InsightAI will use its built-in analytics engine."
    )

    ai_available = False


# =========================================================
# QUICK QUESTIONS
# =========================================================

st.markdown("### 💡 Suggested Questions")

quick_questions = [
    "What are the most important findings in this dataset?",
    "Which variables have the strongest relationships?",
    "Are there any unusual or suspicious values?",
    "Explain the dataset quality.",
    "What should I investigate first?",
]


selected_question = st.selectbox(
    "Choose a suggested question",
    quick_questions,
)


# =========================================================
# CUSTOM QUESTION
# =========================================================

question = st.text_area(
    "Ask your own question",
    value=selected_question,
    height=100,
    placeholder=(
        "Example: What are the most important "
        "patterns in this dataset?"
    ),
)


# =========================================================
# ANALYZE BUTTON
# =========================================================

if st.button(
    "🔍 Analyze",
    type="primary",
    use_container_width=True,
):

    if not question.strip():

        st.warning(
            "Please enter a question."
        )

        st.stop()

    with st.spinner(
        "Analyzing your dataset..."
    ):

        try:

            if ai_available:

                prompt = build_prompt(
                    question,
                    dataset_name,
                    analysis,
                )

                answer = provider.analyze(
                    prompt
                )

            else:

                answer = fallback_analysis(
                    question,
                    dataset_name,
                    analysis,
                )

            st.markdown("## 🧠 InsightAI Analysis")

            st.markdown(answer)

        except Exception as error:

            st.error(
                f"AI analysis failed: {error}"
            )

            st.info(
                "Showing the built-in analytics results instead."
            )

            st.markdown(
                fallback_analysis(
                    question,
                    dataset_name,
                    analysis,
                )
            )


# =========================================================
# AUTOMATIC FINDINGS
# =========================================================

st.divider()

st.markdown(
    "### 📊 Analytics Engine Findings"
)

findings = analysis["findings"]

if findings:

    for finding in findings:

        st.info(
            f"• {finding}"
        )

else:

    st.info(
        "No automatic findings available."
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "InsightAI • AI Analyst"
)
