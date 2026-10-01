"""Conversation context helpers for InsightAI AI Analyst 2.0."""
from __future__ import annotations

import re
from typing import Any


_FOLLOW_UPS = {
    "why": "Explain why the previous result occurred. Use the previous result as the subject and identify only evidence-supported drivers or hypotheses.",
    "why?": "Explain why the previous result occurred. Use the previous result as the subject and identify only evidence-supported drivers or hypotheses.",
    "which one": "Identify which item from the previous result is most relevant to investigate next, using the available evidence.",
    "which country": "Identify the relevant country from the previous result and explain the evidence.",
    "which product": "Identify the relevant product from the previous result and explain the evidence.",
    "show evidence": "Show the exact evidence behind the previous answer, including the deterministic calculation, fields, grouping, filters, and rows used when available.",
    "evidence": "Show the exact evidence behind the previous answer, including the deterministic calculation, fields, grouping, filters, and rows used when available.",
    "what next": "Based on the previous result, what should I investigate next? Give concrete evidence-based investigation steps.",
    "what should i investigate next": "Based on the previous result, what should I investigate next? Give concrete evidence-based investigation steps.",
    "drill down": "Drill down into the previous result using the most relevant available dimension and identify the important contributors.",
}


def is_follow_up(question: str) -> bool:
    q = re.sub(r"\s+", " ", (question or "").strip().lower())
    return q in _FOLLOW_UPS or q.startswith(("why ", "which ", "show me the evidence"))


def resolve_follow_up(
    question: str,
    conversation: list[dict[str, Any]] | None = None,
) -> str:
    """Turn short contextual follow-ups into explicit analytical questions."""
    q = re.sub(r"\s+", " ", (question or "").strip().lower())
    history = conversation or []

    if not history or not is_follow_up(question):
        return question

    previous_user = ""
    previous_answer = ""
    for item in reversed(history):
        if item.get("role") == "assistant" and not previous_answer:
            previous_answer = str(item.get("content", ""))
        if item.get("role") == "user" and not previous_user:
            previous_user = str(item.get("content", ""))
        if previous_user and previous_answer:
            break

    instruction = _FOLLOW_UPS.get(q)
    if not instruction:
        if q.startswith("why"):
            instruction = _FOLLOW_UPS["why"]
        elif q.startswith("which"):
            instruction = "Identify the relevant item from the previous result and explain the evidence."
        elif q.startswith("show"):
            instruction = _FOLLOW_UPS["show evidence"]
        else:
            instruction = _FOLLOW_UPS["what next"]

    return (
        f"{instruction}\n\n"
        f"Previous user question: {previous_user}\n"
        f"Previous InsightAI answer: {previous_answer[:6000]}"
    )


def quick_context(
    conversation: list[dict[str, Any]] | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    return (conversation or [])[-limit:]
