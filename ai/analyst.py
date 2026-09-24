"""Unified AI Analyst engine for InsightAI.

This is the single intelligence layer behind the existing
pages/03_AI_Analyst.py page.

Responsibilities:
- build evidence-grounded dataset context
- support normal tabular/time-series analysis
- support first-class PCAP/network intelligence
- build safe prompts for the configured AI provider
- provide deterministic local fallback answers when AI is unavailable
"""
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


def _records(frame: pd.DataFrame | None, limit: int = 15) -> list[dict[str, Any]]:
    """Convert a dataframe into JSON-safe records."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return frame.head(limit).to_dict(orient="records")


def _network_context(df: pd.DataFrame) -> dict[str, Any]:
    """Build deterministic evidence for a PCAP/network dataset."""
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
            "unique_conversations": int(
                metrics.get("unique_conversations", 0) or 0
            ),
        },
        "protocols": _records(protocols, 15),
        "top_endpoints": _records(endpoints, 15),
        "top_conversations": _records(conversations, 15),
        "recognized_columns": metrics.get("columns", {}),
    }


def build_analysis_context(dataset_name, analysis):
    """Original API preserved for compatibility with the existing app."""
    health = analysis["health"]
    classification = analysis["classification"]
    findings = analysis["findings"]
    outliers = analysis["outliers"]
    correlations = analysis["correlations"]

    context = {
        "dataset": dataset_name,
        "dataset_health": health,
        "numeric_columns": classification["numeric"],
        "categorical_columns": classification["categorical"],
        "datetime_columns": classification["datetime"],
        "automatic_findings": findings,
        "outliers": _records(outliers, 15),
        "correlations": _records(correlations, 15),
    }

    return json.dumps(context, indent=2, default=str)


def build_prompt(question, dataset_name, analysis):
    """Original prompt API preserved for compatibility."""
    context = build_analysis_context(dataset_name, analysis)

    return f"""
You are InsightAI, an expert data analyst.

Dataset:
{dataset_name}

Calculated evidence:
{context}

User question:
{question}

Rules:
1. Answer from the supplied evidence.
2. Never invent statistics or observations.
3. Distinguish observed facts from interpretations.
4. Use simple professional language.
5. Mention relevant columns when useful.
6. If evidence is insufficient, say what additional analysis is needed.
7. Keep the answer concise but useful.
8. Use headings or bullets when appropriate.
""".strip()


def build_dataset_context(
    df: pd.DataFrame,
    dataset_name: str = "Dataset",
    source_type: str | None = None,
) -> dict[str, Any]:
    """Build one grounded context object for the unified AI experience."""
    dataset_type = detect_dataset_type(
        df,
        source_name=dataset_name,
        source_type=source_type,
    )

    context: dict[str, Any] = {
        "dataset": dataset_name,
        "dataset_type": dataset_type,
        "rows": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "numeric_columns": [
            str(c) for c in df.select_dtypes(include="number").columns
        ],
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
        "categorical_summary": _records(
            analysis.get("categorical_summary"), 15
        ),
    }

    return context


def build_command_prompt(
    question: str,
    context: dict[str, Any],
    conversation: list[dict[str, str]] | None = None,
) -> str:
    """Build an evidence-grounded prompt for the AI provider."""
    history = conversation or []
    history_text = "\n".join(
        f"{item.get('role', 'user').upper()}: {item.get('content', '')}"
        for item in history[-8:]
    )

    context_json = json.dumps(context, indent=2, default=str)

    return f"""
You are InsightAI, the AI Data Analyst inside a professional
data-intelligence platform.

The platform is designed around three questions:
1. What happened?
2. Why might it have happened?
3. What should I investigate next?

USER QUESTION:
{question}

RECENT CONVERSATION:
{history_text or "No previous conversation."}

DATASET EVIDENCE:
{context_json}

STRICT EVIDENCE RULES:
- Use the supplied calculated evidence as the primary source.
- Never invent measurements, counts, IP addresses, protocols, trends,
  correlations, causes, or statistics.
- Treat calculations in the evidence as observations.
- Clearly separate observed facts from possible explanations.
- Do not state a root cause as confirmed unless the evidence supports it.
- For "why" questions, give evidence-supported hypotheses and concrete
  validation checks.
- For "what next" questions, provide practical investigation steps.
- For PCAP/network questions, use the supplied packet, protocol, endpoint,
  conversation, byte and timing evidence.
- If the available evidence cannot answer the question, say so clearly.
- Do not claim to have inspected packets or columns that are not supplied.
- Use professional, concise language.
- Prefer headings and bullets for readability.
""".strip()


def _normal_fallback(question: str, dataset_name: str, analysis: dict[str, Any]) -> str:
    """Useful deterministic response when no external AI is configured."""
    health = analysis.get("health", {})
    findings = analysis.get("findings", [])
    correlations = analysis.get("correlations", pd.DataFrame())
    outliers = analysis.get("outliers", pd.DataFrame())

    q = (question or "").lower()

    lines = [
        f"### InsightAI Analysis — {dataset_name}",
        f"**Question:** {question}",
        "",
    ]

    if "quality" in q or "clean" in q or "missing" in q or "duplicate" in q:
        lines.extend(
            [
                "### Data Quality",
                f"- Rows: **{health.get('rows', 0):,}**",
                f"- Columns: **{health.get('columns', 0):,}**",
                f"- Completeness: **{health.get('completeness', 0):.2f}%**",
                f"- Missing values: **{health.get('missing_values', 0):,}**",
                f"- Duplicate rows: **{health.get('duplicate_rows', 0):,}**",
                f"- Quality score: **{health.get('quality_score', 0):.1f}/100**",
                "",
            ]
        )

    if "correlation" in q or "relationship" in q or "related" in q:
        if isinstance(correlations, pd.DataFrame) and not correlations.empty:
            lines.append("### Strongest Relationships")
            for row in correlations.head(8).to_dict(orient="records"):
                lines.append(
                    f"- **{row.get('column_1')} ↔ {row.get('column_2')}**: "
                    f"correlation **{row.get('correlation')}**"
                )
        else:
            lines.append("No numeric correlation pairs are available.")

        lines.append("")

    if "outlier" in q or "unusual" in q or "suspicious" in q:
        if isinstance(outliers, pd.DataFrame) and not outliers.empty:
            useful = outliers[outliers["outliers"] > 0]
            if not useful.empty:
                lines.append("### Potential Outliers")
                for row in useful.head(8).to_dict(orient="records"):
                    lines.append(
                        f"- **{row.get('column')}**: "
                        f"{int(row.get('outliers', 0)):,} potential outliers "
                        f"({row.get('outlier_percentage', 0)}%)"
                    )
            else:
                lines.append("No IQR-based outliers were detected.")
        else:
            lines.append("No outlier results are available.")
        lines.append("")

    if findings:
        lines.append("### Key Findings")
        lines.extend(f"- {finding}" for finding in findings[:10])
    else:
        lines.append("### Key Findings")
        lines.append("- No automatic findings were generated.")

    lines.extend(
        [
            "",
            "### What to investigate next",
            "- Open Data Explorer to inspect the relevant columns.",
            "- Use Anomaly Detection for a dedicated anomaly analysis.",
            "- Use Dashboard for visual relationships and trends.",
            "- Ask a more specific question if you want to investigate one column.",
            "",
            "_AI provider is not configured, so this response uses InsightAI's local analytics engine._",
        ]
    )

    return "\n".join(lines)


def _network_fallback(question: str, context: dict[str, Any]) -> str:
    """Useful deterministic PCAP/network response when AI is unavailable."""
    q = (question or "").lower()
    net = context.get("network_intelligence", {})
    summary = net.get("summary", {})
    protocols = net.get("protocols", [])
    endpoints = net.get("top_endpoints", [])
    conversations = net.get("top_conversations", [])

    if "protocol" in q:
        if protocols:
            lines = ["### Protocol Intelligence"]
            for row in protocols[:10]:
                lines.append(
                    f"- **{row.get('Protocol', 'Unknown')}**: "
                    f"{int(row.get('Packets', 0) or 0):,} packets"
                )
            return "\n".join(lines)
        return "### Protocol Intelligence\n\nNo protocol distribution is available."

    if any(word in q for word in ("conversation", "communicating", "talking")):
        if conversations:
            lines = ["### Top Conversations"]
            for row in conversations[:10]:
                lines.append(
                    f"- **{row.get('Source')} → {row.get('Destination')}**: "
                    f"{int(row.get('Packets', 0) or 0):,} packets"
                )
            return "\n".join(lines)
        return "### Top Conversations\n\nNo source/destination conversations are available."

    if any(
        word in q
        for word in ("endpoint", "source ip", "destination ip", "top ip")
    ):
        if endpoints:
            lines = ["### Top Endpoints"]
            for row in endpoints[:10]:
                src = int(row.get("Source Packets", 0) or 0)
                dst = int(row.get("Destination Packets", 0) or 0)
                lines.append(
                    f"- **{row.get('Endpoint')}** — "
                    f"source packets: {src:,}, destination packets: {dst:,}"
                )
            return "\n".join(lines)
        return "### Top Endpoints\n\nNo endpoint information is available."

    return (
        "### Network Capture Summary\n\n"
        f"- Packets: **{int(summary.get('packets', 0) or 0):,}**\n"
        f"- Total bytes: **{int(summary.get('total_bytes', 0) or 0):,}**\n"
        f"- Duration: **{float(summary.get('duration_seconds', 0) or 0):,.3f} seconds**\n"
        f"- Packets/sec: **{float(summary.get('packets_per_second', 0) or 0):,.2f}**\n"
        f"- Bytes/sec: **{float(summary.get('bytes_per_second', 0) or 0):,.2f}**\n"
        f"- Unique conversations: **{int(summary.get('unique_conversations', 0) or 0):,}**\n\n"
        "### What to investigate next\n"
        "Ask about protocols, endpoints, conversations, traffic volume, "
        "or unusual traffic to continue the investigation."
    )


def fallback_answer(question, dataset_name, analysis):
    """Original fallback API preserved for compatibility."""
    return _normal_fallback(question, dataset_name, analysis)


def answer_question(
    question: str,
    df: pd.DataFrame,
    dataset_name: str = "Dataset",
    source_type: str | None = None,
    provider=None,
    conversation: list[dict[str, str]] | None = None,
) -> str:
    """Unified entry point used by pages/03_AI_Analyst.py."""
    context = build_dataset_context(
        df,
        dataset_name=dataset_name,
        source_type=source_type,
    )

    if provider is not None and provider.is_available():
        prompt = build_command_prompt(
            question,
            context,
            conversation=conversation,
        )
        return provider.analyze(prompt)

    if context["dataset_type"] == "network_capture":
        return _network_fallback(question, context)

    analysis = analyze_dataset(df)
    return _normal_fallback(question, dataset_name, analysis)
