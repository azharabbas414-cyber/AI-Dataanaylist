
import html
from datetime import datetime

import pandas as pd


def build_report_data(
    df,
    dataset_name,
    analysis,
):
    """
    Prepare structured information for the report.
    """

    health = analysis["health"]
    classification = analysis["classification"]

    numeric_summary = analysis["numeric_summary"]
    categorical_summary = analysis["categorical_summary"]
    outliers = analysis["outliers"]
    correlations = analysis["correlations"]
    findings = analysis["findings"]

    return {
        "dataset_name": dataset_name,
        "generated_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "health": health,
        "classification": classification,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "outliers": outliers,
        "correlations": correlations,
        "findings": findings,
        "rows": len(df),
        "columns": len(df.columns),
    }


def generate_executive_summary(report_data):
    """
    Generate a concise executive summary.
    """

    health = report_data["health"]

    rows = health["rows"]
    columns = health["columns"]
    completeness = health["completeness"]
    quality_score = health["quality_score"]
    anomaly_count = len(
        report_data["outliers"]
    )

    summary = []

    summary.append(
        f"The dataset contains {rows:,} records "
        f"across {columns:,} columns."
    )

    summary.append(
        f"Overall data completeness is "
        f"{completeness:.1f}% with a calculated "
        f"quality score of {quality_score:.0f}/100."
    )

    if anomaly_count > 0:
        summary.append(
            f"The analytics engine identified "
            f"{anomaly_count:,} columns containing "
            f"potential statistical outliers."
        )
    else:
        summary.append(
            "No statistical outlier groups were identified."
        )

    return " ".join(summary)


def dataframe_to_html(
    dataframe,
    max_rows=20,
):
    """
    Convert a DataFrame into an HTML table.
    """

    if dataframe is None or dataframe.empty:
        return "<p>No data available.</p>"

    display_df = dataframe.head(max_rows).copy()

    return display_df.to_html(
        index=False,
        classes="data-table",
        border=0,
        escape=True,
    )


def generate_html_report(report_data):
    """
    Generate a complete HTML report.
    """

    dataset_name = html.escape(
        str(report_data["dataset_name"])
    )

    generated_at = html.escape(
        str(report_data["generated_at"])
    )

    health = report_data["health"]

    classification = report_data[
        "classification"
    ]

    findings = report_data["findings"]

    executive_summary = generate_executive_summary(
        report_data
    )

    numeric_summary = dataframe_to_html(
        report_data["numeric_summary"],
        max_rows=20,
    )

    categorical_summary = dataframe_to_html(
        report_data["categorical_summary"],
        max_rows=20,
    )

    outliers = dataframe_to_html(
        report_data["outliers"],
        max_rows=20,
    )

    correlations = dataframe_to_html(
        report_data["correlations"],
        max_rows=20,
    )

    findings_html = ""

    if findings:

        for finding in findings:

            findings_html += (
                f"<li>{html.escape(str(finding))}</li>"
            )

    else:

        findings_html = (
            "<li>No automatic findings were generated.</li>"
        )

    numeric_columns = ", ".join(
        str(column)
        for column in classification["numeric"]
    )

    categorical_columns = ", ".join(
        str(column)
        for column in classification["categorical"]
    )

    datetime_columns = ", ".join(
        str(column)
        for column in classification["datetime"]
    )

    report_html = f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>InsightAI Report - {dataset_name}</title>

<style>

body {{
    font-family: Arial, Helvetica, sans-serif;
    margin: 0;
    padding: 0;
    background: #f5f7fa;
    color: #1e293b;
}}

.container {{
    max-width: 1100px;
    margin: 40px auto;
    background: white;
    padding: 45px;
    box-shadow: 0 5px 25px rgba(0,0,0,0.08);
}}

.header {{
    border-bottom: 3px solid #334155;
    padding-bottom: 25px;
    margin-bottom: 30px;
}}

.logo {{
    font-size: 32px;
    font-weight: 800;
}}

.subtitle {{
    color: #64748b;
    font-size: 15px;
}}

h1 {{
    font-size: 30px;
}}

h2 {{
    margin-top: 35px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 8px;
}}

.summary {{
    background: #f1f5f9;
    padding: 20px;
    border-radius: 10px;
    line-height: 1.7;
}}

.kpi-container {{
    display: flex;
    gap: 15px;
    margin: 25px 0;
}}

.kpi {{
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 18px;
}}

.kpi-title {{
    color: #64748b;
    font-size: 13px;
}}

.kpi-value {{
    font-size: 25px;
    font-weight: 700;
    margin-top: 5px;
}}

.data-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    font-size: 13px;
}}

.data-table th {{
    background: #e2e8f0;
    text-align: left;
    padding: 9px;
}}

.data-table td {{
    border-bottom: 1px solid #e2e8f0;
    padding: 8px;
}}

ul {{
    line-height: 1.8;
}}

.footer {{
    margin-top: 50px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 12px;
}}

</style>

</head>

<body>

<div class="container">

<div class="header">

<div class="logo">
InsightAI
</div>

<div class="subtitle">
AI-Powered Data Analytics & Decision Intelligence
</div>

<h1>
Data Analytics Report
</h1>

<p>
<strong>Dataset:</strong> {dataset_name}
</p>

<p>
<strong>Generated:</strong> {generated_at}
</p>

</div>


<h2>Executive Summary</h2>

<div class="summary">

{html.escape(executive_summary)}

</div>


<div class="kpi-container">

<div class="kpi">

<div class="kpi-title">
Rows
</div>

<div class="kpi-value">
{health["rows"]:,}
</div>

</div>


<div class="kpi">

<div class="kpi-title">
Columns
</div>

<div class="kpi-value">
{health["columns"]:,}
</div>

</div>


<div class="kpi">

<div class="kpi-title">
Completeness
</div>

<div class="kpi-value">
{health["completeness"]:.1f}%
</div>

</div>


<div class="kpi">

<div class="kpi-title">
Quality Score
</div>

<div class="kpi-value">
{health["quality_score"]:.0f}/100
</div>

</div>

</div>


<h2>Dataset Structure</h2>

<p>
<strong>Numeric Fields:</strong>
{html.escape(numeric_columns or "None")}
</p>

<p>
<strong>Categorical Fields:</strong>
{html.escape(categorical_columns or "None")}
</p>

<p>
<strong>Date/Time Fields:</strong>
{html.escape(datetime_columns or "None")}
</p>


<h2>Data Quality</h2>

<ul>

<li>
Missing values:
{health["missing_values"]:,}
</li>

<li>
Duplicate rows:
{health["duplicate_rows"]:,}
</li>

<li>
Completeness:
{health["completeness"]:.2f}%
</li>

<li>
Duplicate percentage:
{health["duplicate_percentage"]:.2f}%
</li>

</ul>


<h2>Key Findings</h2>

<ul>

{findings_html}

</ul>


<h2>Numeric Statistics</h2>

{numeric_summary}


<h2>Categorical Analysis</h2>

{categorical_summary}


<h2>Potential Outliers</h2>

{outliers}


<h2>Strongest Relationships</h2>

{correlations}


<div class="footer">

InsightAI • AI-Powered Data Analytics Platform

</div>

</div>

</body>

</html>
"""

    return report_html
