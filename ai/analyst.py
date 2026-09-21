
import json


def build_analysis_context(
    dataset_name,
    analysis
):
    """
    Convert analytics engine results into
    structured context for the AI.
    """

    health = analysis["health"]

    classification = analysis[
        "classification"
    ]

    findings = analysis[
        "findings"
    ]

    outliers = analysis[
        "outliers"
    ]

    correlations = analysis[
        "correlations"
    ]

    context = {
        "dataset": dataset_name,

        "dataset_health": health,

        "numeric_columns":
            classification["numeric"],

        "categorical_columns":
            classification["categorical"],

        "datetime_columns":
            classification["datetime"],

        "automatic_findings":
            findings,

        "outliers":
            outliers.head(15).to_dict(
                orient="records"
            )
            if not outliers.empty
            else [],

        "correlations":
            correlations.head(15).to_dict(
                orient="records"
            )
            if not correlations.empty
            else [],
    }

    return json.dumps(
        context,
        indent=2,
        default=str
    )


def build_prompt(
    question,
    dataset_name,
    analysis
):

    context = build_analysis_context(
        dataset_name,
        analysis
    )

    prompt = f"""
You are InsightAI, an expert data analyst.

You are analyzing the dataset:
{dataset_name}

The following information was calculated
by the InsightAI analytics engine:

{context}

User question:
{question}

Instructions:

1. Answer using the supplied analytical evidence.
2. Do not invent statistics that are not present.
3. Clearly distinguish observations from interpretations.
4. Use simple professional language.
5. When useful, mention the relevant column names.
6. If the available information is insufficient,
   explicitly say what additional analysis is needed.
7. Keep the answer concise but useful.
8. Structure the answer with headings or bullet points
   when appropriate.
"""

    return prompt


def fallback_analysis(
    question,
    dataset_name,
    analysis
):
    """
    Local fallback when no AI API key is configured.
    """

    findings = analysis["findings"]

    answer = []

    answer.append(
        f"### Analysis of {dataset_name}"
    )

    answer.append(
        f"Your question: **{question}**"
    )

    if findings:

        answer.append(
            "### Key Findings"
        )

        for finding in findings:

            answer.append(
                f"- {finding}"
            )

    else:

        answer.append(
            "No automatic findings were generated."
        )

    answer.append(
        "### AI Status"
    )

    answer.append(
        "The AI provider is not configured yet. "
        "The response above uses InsightAI's local "
        "analytics engine."
    )

    return "\n\n".join(answer)
