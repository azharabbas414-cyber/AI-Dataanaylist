"""Unified, evidence-grounded AI Analyst engine for InsightAI."""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from core.analytics import analyze_dataset
from core.dataset_detector import detect_dataset_type
from core.network_intelligence import (
    analyze_network_capture,
    protocol_distribution,
    top_endpoints,
    top_conversations,
)
from core.query_engine import query_dataframe


def _records(frame: pd.DataFrame | None, limit: int = 15) -> list[dict[str, Any]]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return frame.head(limit).to_dict(orient="records")


def _network_context(df: pd.DataFrame) -> dict[str, Any]:
    metrics = analyze_network_capture(df)
    protocols = protocol_distribution(df)
    endpoints = top_endpoints(df, 15)
    conversations = top_conversations(df, 15)

    def number(value, default=0):
        try:
            return default if value is None else float(value)
        except (TypeError, ValueError):
            return default

    return {
        "summary": {
            "packets": int(metrics.get("packet_count", len(df)) or 0),
            "total_bytes": int(metrics.get("total_bytes", 0) or 0),
            "duration_seconds": number(metrics.get("duration_seconds")),
            "packets_per_second": number(metrics.get("packets_per_second")),
            "bytes_per_second": number(metrics.get("bytes_per_second")),
            "unique_conversations": int(metrics.get("unique_conversations", 0) or 0),
        },
        "protocols": _records(protocols, 15),
        "top_endpoints": _records(endpoints, 15),
        "top_conversations": _records(conversations, 15),
        "recognized_columns": metrics.get("columns", {}),
    }


def build_analysis_context(dataset_name, analysis):
    health = analysis["health"]
    classification = analysis["classification"]
    context = {
        "dataset": dataset_name,
        "dataset_health": health,
        "numeric_columns": classification["numeric"],
        "categorical_columns": classification["categorical"],
        "datetime_columns": classification["datetime"],
        "automatic_findings": analysis["findings"],
        "outliers": _records(analysis.get("outliers"), 15),
        "correlations": _records(analysis.get("correlations"), 15),
    }
    return json.dumps(context, indent=2, default=str)


def build_prompt(question, dataset_name, analysis):
    context = build_analysis_context(dataset_name, analysis)
    return f"""
You are InsightAI, an expert data analyst.

Dataset: {dataset_name}

Calculated evidence:
{context}

User question:
{question}

Rules:
1. Answer only from supplied calculated evidence.
2. Never invent statistics or observations.
3. Distinguish observed facts from interpretations.
4. If evidence is insufficient, say what exact calculation is needed.
5. Keep the answer concise and professional.
""".strip()


def build_dataset_context(df: pd.DataFrame, dataset_name: str = "Dataset", source_type: str | None = None) -> dict[str, Any]:
    dataset_type = detect_dataset_type(df, source_name=dataset_name, source_type=source_type)
    context: dict[str, Any] = {
        "dataset": dataset_name,
        "dataset_type": dataset_type,
        "rows": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "numeric_columns": [str(c) for c in df.select_dtypes(include="number").columns],
        "sample_rows": _records(df, 8),
    }

    if dataset_type == "network_capture":
        context["network_intelligence"] = _network_context(df)
        return context

    analysis = analyze_dataset(df)
    context["analytics"] = {
        "health": analysis.get("health", {}),
        "classification": analysis.get("classification", {}),
        "findings": analysis.get("findings", [])[:20],
        "outliers": _records(analysis.get("outliers"), 15),
        "correlations": _records(analysis.get("correlations"), 15),
        "numeric_summary": _records(analysis.get("numeric_summary"), 15),
        "categorical_summary": _records(analysis.get("categorical_summary"), 15),
    }
    return context


def build_command_prompt(question: str, context: dict[str, Any], conversation=None) -> str:
    history = conversation or []
    history_text = "\n".join(
        f"{item.get('role', 'user').upper()}: {item.get('content', '')}"
        for item in history[-8:]
    )
    context_json = json.dumps(context, indent=2, default=str)
    return f"""
You are InsightAI, the AI Data Analyst inside a professional data-intelligence platform.

USER QUESTION:
{question}

RECENT CONVERSATION:
{history_text or "No previous conversation."}

DATASET EVIDENCE:
{context_json}

STRICT RULES:
- Exact Query Evidence is deterministic and calculated directly from the active dataframe.
- If Exact Query Evidence is present, use it as the authoritative answer for the requested calculation.
- Never replace an exact calculated value with a guess from a sample or statistical summary.
- Never invent a product, region, date, customer, value, count, or ranking.
- Distinguish individual-row extremes from grouped totals.
- For ambiguous questions such as "which product has maximum profit", explain both the highest individual transaction and the highest cumulative product total when both are supplied.
- For why questions, give evidence-supported hypotheses and validation steps.
- For what-next questions, provide practical investigation steps.
- Keep the answer concise and professional.
""".strip()


def _normal_fallback(question: str, dataset_name: str, analysis: dict[str, Any]) -> str:
    health = analysis.get("health", {})
    findings = analysis.get("findings", [])
    q = (question or "").lower()
    lines = [f"### InsightAI Analysis — {dataset_name}", f"**Question:** {question}", ""]

    if any(word in q for word in ("quality", "clean", "missing", "duplicate")):
        lines += [
            "### Data Quality",
            f"- Rows: **{health.get('rows', 0):,}**",
            f"- Columns: **{health.get('columns', 0):,}**",
            f"- Completeness: **{health.get('completeness', 0):.2f}%**",
            f"- Missing values: **{health.get('missing_values', 0):,}**",
            f"- Duplicate rows: **{health.get('duplicate_rows', 0):,}**",
            f"- Quality score: **{health.get('quality_score', 0):.1f}/100**",
            "",
        ]

    if findings:
        lines.append("### Key Findings")
        lines.extend(f"- {finding}" for finding in findings[:10])
    else:
        lines += ["### Key Findings", "- No automatic findings were generated."]

    lines += [
        "",
        "### What to investigate next",
        "- Use Data Explorer to inspect the relevant columns.",
        "- Use Anomaly Detection for unusual values.",
        "- Use Dashboard for visual relationships and trends.",
    ]
    return "\n".join(lines)


def _network_fallback(question: str, context: dict[str, Any]) -> str:
    q = (question or "").lower()
    net = context.get("network_intelligence", {})
    summary = net.get("summary", {})
    protocols = net.get("protocols", [])
    endpoints = net.get("top_endpoints", [])
    conversations = net.get("top_conversations", [])

    if "protocol" in q and protocols:
        return "### Protocol Intelligence\n\n" + "\n".join(
            f"- **{r.get('Protocol', 'Unknown')}**: {int(r.get('Packets', 0) or 0):,} packets"
            for r in protocols[:10]
        )
    if any(x in q for x in ("conversation", "communicating", "talking")) and conversations:
        return "### Top Conversations\n\n" + "\n".join(
            f"- **{r.get('Source')} → {r.get('Destination')}**: {int(r.get('Packets', 0) or 0):,} packets"
            for r in conversations[:10]
        )
    if any(x in q for x in ("endpoint", "source ip", "destination ip", "top ip")) and endpoints:
        return "### Top Endpoints\n\n" + "\n".join(
            f"- **{r.get('Endpoint')}** — source packets: {int(r.get('Source Packets', 0) or 0):,}, destination packets: {int(r.get('Destination Packets', 0) or 0):,}"
            for r in endpoints[:10]
        )
    return (
        "### Network Capture Summary\n\n"
        f"- Packets: **{int(summary.get('packets', 0) or 0):,}**\n"
        f"- Total bytes: **{int(summary.get('total_bytes', 0) or 0):,}**\n"
        f"- Duration: **{float(summary.get('duration_seconds', 0) or 0):,.3f} seconds**\n"
        f"- Packets/sec: **{float(summary.get('packets_per_second', 0) or 0):,.2f}**\n"
        f"- Bytes/sec: **{float(summary.get('bytes_per_second', 0) or 0):,.2f}**\n"
    )


def fallback_answer(question, dataset_name, analysis):
    return _normal_fallback(question, dataset_name, analysis)


def answer_question(question: str, df: pd.DataFrame, dataset_name: str = "Dataset", source_type: str | None = None, provider=None, conversation=None) -> str:
    """Answer using deterministic dataframe evidence first, then AI explanation."""
    context = build_dataset_context(df, dataset_name=dataset_name, source_type=source_type)

    # Network captures use their specialized deterministic evidence path.
    if context["dataset_type"] == "network_capture":
        if provider is not None and provider.is_available():
            prompt = build_command_prompt(question, context, conversation)
            return provider.analyze(prompt)
        return _network_fallback(question, context)

    # Critical upgrade: calculate exact row/group results before asking the LLM.
    query_result = query_dataframe(df, question)
    context["exact_query_evidence"] = query_result

    if query_result.get("handled"):
        exact = query_result.get("direct_answer", "Exact calculation completed.")
        if provider is not None and provider.is_available():
            prompt = build_command_prompt(question, context, conversation)
            ai_answer = provider.analyze(prompt)
            return f"### Exact calculated result\n{exact}\n\n### InsightAI explanation\n{ai_answer}"
        return f"### Exact calculated result\n{exact}\n\n**Calculated directly from the active dataset — not inferred from a summary.**"

    if provider is not None and provider.is_available():
        prompt = build_command_prompt(question, context, conversation)
        return provider.analyze(prompt)

    analysis = analyze_dataset(df)
    return _normal_fallback(question, dataset_name, analysis)
