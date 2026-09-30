
import io
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from docx import Document


def _sales_metric(df):
    if "Quantity" in df.columns and "UnitPrice" in df.columns:
        q = pd.to_numeric(df["Quantity"], errors="coerce")
        p = pd.to_numeric(df["UnitPrice"], errors="coerce")
        return q * p, "Sales Value", "Quantity × UnitPrice"

    candidates = [
        c for c in df.select_dtypes(include=np.number).columns
        if not any(x in str(c).lower() for x in ["id", "code", "zip", "postal"])
    ]
    if candidates:
        c = candidates[0]
        return pd.to_numeric(df[c], errors="coerce"), str(c), str(c)
    return None, None, None


def _detect_date(df):
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        name = str(c).lower()
        if any(x in name for x in ["date", "time", "timestamp"]):
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() >= 0.60:
                return c
    return None


def build_report_data(df):
    rows, cols = len(df), len(df.columns)
    cells = rows * cols
    missing = int(df.isna().sum().sum())
    return {
        "rows": rows,
        "columns": cols,
        "missing_cells": missing,
        "duplicate_rows": int(df.duplicated().sum()),
        "completeness": ((cells - missing) / cells * 100) if cells else 100.0,
        "numeric_columns": list(df.select_dtypes(include=np.number).columns),
        "categorical_columns": list(df.select_dtypes(include=["object", "category", "bool"]).columns),
        "datetime_columns": list(df.select_dtypes(include=["datetime", "datetimetz"]).columns),
    }


def _kpis(df):
    values, metric, formula = _sales_metric(df)
    out = []

    if values is not None:
        clean = values.dropna()
        if not clean.empty:
            out.extend([
                {"label": f"Total {metric}", "value": f"{clean.sum():,.2f}", "raw": float(clean.sum())},
                {"label": f"Average {metric}", "value": f"{clean.mean():,.2f}", "raw": float(clean.mean())},
                {"label": f"Maximum {metric}", "value": f"{clean.max():,.2f}", "raw": float(clean.max())},
            ])

    if "Quantity" in df.columns:
        q = pd.to_numeric(df["Quantity"], errors="coerce").sum()
        out.append({"label": "Total Quantity", "value": f"{q:,.0f}", "raw": float(q)})

    if "CustomerID" in df.columns:
        n = df["CustomerID"].nunique(dropna=True)
        out.append({"label": "Customers", "value": f"{n:,}", "raw": float(n)})

    out.append({"label": "Transactions / Rows", "value": f"{len(df):,}", "raw": float(len(df))})
    return out, metric, formula


def _preferred_dimension(df):
    candidates = [
        c for c in df.select_dtypes(include=["object", "category", "bool"]).columns
        if 2 <= df[c].nunique(dropna=True) <= min(1000, max(2, len(df)))
    ]
    priority = [
        "country", "region", "category", "product", "description",
        "customer", "customerid", "segment", "city", "state"
    ]
    for p in priority:
        for c in candidates:
            if str(c).lower() == p:
                return c
    return candidates[0] if candidates else None


def _top_bottom(df, n=10):
    values, metric, _ = _sales_metric(df)
    if values is None:
        return pd.DataFrame()

    dim = _preferred_dimension(df)
    if dim is None:
        return pd.DataFrame()

    temp = pd.DataFrame({"Dimension": df[dim].astype("string"), "Metric": values})
    temp = temp.dropna(subset=["Dimension", "Metric"])
    temp = temp.groupby("Dimension", as_index=False)["Metric"].sum()
    temp = temp.sort_values("Metric", ascending=False).head(n)
    temp.insert(0, "Rank", range(1, len(temp) + 1))
    return temp.rename(columns={"Dimension": dim, "Metric": metric})


def _trend(df):
    values, metric, _ = _sales_metric(df)
    date_col = _detect_date(df)
    if values is None or date_col is None:
        return pd.DataFrame()

    temp = pd.DataFrame({
        "Date": pd.to_datetime(df[date_col], errors="coerce"),
        "Value": values,
    }).dropna()

    if temp.empty:
        return pd.DataFrame()

    temp["Period"] = temp["Date"].dt.to_period("M").astype(str)
    out = temp.groupby("Period", as_index=False)["Value"].sum()
    return out.rename(columns={"Value": metric})


def _trend_insight(trend, metric):
    if trend.empty or len(trend) < 2:
        return None

    values = pd.to_numeric(trend.iloc[:, 1], errors="coerce")
    latest = float(values.iloc[-1])
    previous = float(values.iloc[-2])
    change = ((latest - previous) / abs(previous) * 100) if previous else np.nan

    peak_idx = values.idxmax()
    low_idx = values.idxmin()

    return {
        "latest_period": str(trend.iloc[-1, 0]),
        "latest_value": latest,
        "previous_period": str(trend.iloc[-2, 0]),
        "previous_value": previous,
        "change_pct": change,
        "peak_period": str(trend.loc[peak_idx].iloc[0]),
        "peak_value": float(values.loc[peak_idx]),
        "low_period": str(trend.loc[low_idx].iloc[0]),
        "low_value": float(values.loc[low_idx]),
        "metric": metric,
    }


def _contribution(df):
    top = _top_bottom(df, 10)
    values, metric, _ = _sales_metric(df)
    if top.empty or values is None:
        return top

    total = values.dropna().sum()
    if total:
        top = top.copy()
        top["Contribution %"] = top[metric] / total * 100
    return top


def _findings(df):
    findings = []
    data = build_report_data(df)
    values, metric, formula = _sales_metric(df)

    if values is not None:
        clean = values.dropna()
        if not clean.empty:
            findings.append(
                f"Total {metric} is {clean.sum():,.2f}, calculated using {formula}."
            )

    top = _contribution(df)
    if not top.empty:
        dim = top.columns[1]
        first = top.iloc[0]
        contribution = first["Contribution %"] if "Contribution %" in top.columns else np.nan
        if pd.notna(contribution):
            findings.append(
                f"{first[dim]} is the largest contributor, representing {contribution:.1f}% "
                f"of total {metric}."
            )
        else:
            findings.append(f"{first[dim]} is the largest contributor by {metric}.")

    trend = _trend(df)
    ti = _trend_insight(trend, metric)
    if ti:
        if np.isfinite(ti["change_pct"]):
            direction = "increased" if ti["change_pct"] >= 0 else "decreased"
            findings.append(
                f"{metric} {direction} by {abs(ti['change_pct']):.1f}% in "
                f"{ti['latest_period']} versus {ti['previous_period']}."
            )
        findings.append(
            f"The peak period was {ti['peak_period']} at {ti['peak_value']:,.2f}, "
            f"while the lowest was {ti['low_period']} at {ti['low_value']:,.2f}."
        )

    if data["duplicate_rows"]:
        findings.append(f"{data['duplicate_rows']:,} duplicate rows were identified.")
    if data["missing_cells"]:
        findings.append(f"{data['missing_cells']:,} missing cells require review.")

    return findings or ["No major automatic findings were identified."]


def _management_actions(df):
    actions = []
    top = _contribution(df)
    trend = _trend(df)
    values, metric, _ = _sales_metric(df)

    if not top.empty:
        dim = top.columns[1]
        first = top.iloc[0]
        actions.append(
            f"Investigate the products/customers/markets contributing most to {first[dim]} "
            f"and validate whether the concentration is sustainable."
        )

    ti = _trend_insight(trend, metric)
    if ti and np.isfinite(ti["change_pct"]) and abs(ti["change_pct"]) >= 10:
        actions.append(
            f"Investigate the {abs(ti['change_pct']):.1f}% period-over-period change in "
            f"{metric}, focusing on the drivers of the latest period."
        )

    if values is not None:
        clean = values.dropna()
        if not clean.empty and clean.sum() != 0:
            concentration = clean.max() / clean.sum() * 100
            if concentration >= 5:
                actions.append(
                    "Review high-value transactions for concentration or exceptional-order effects."
                )

    data = build_report_data(df)
    if data["missing_cells"] or data["duplicate_rows"]:
        actions.append("Review data quality issues before using the analysis for operational decisions.")

    return actions or ["Review the leading contributors and latest trend before taking action."]


def _executive_summary(df):
    data = build_report_data(df)
    kpis, metric, formula = _kpis(df)
    summary = []

    summary.append(
        f"The dataset contains {data['rows']:,} records across {data['columns']:,} fields."
    )

    if metric:
        total = next((x["value"] for x in kpis if x["label"].startswith("Total ")), None)
        summary.append(
            f"Total {metric} is {total}, using {formula} where applicable."
        )

    top = _contribution(df)
    if not top.empty:
        dim = top.columns[1]
        first = top.iloc[0]
        if "Contribution %" in top.columns:
            summary.append(
                f"{first[dim]} is the leading contributor at {first['Contribution %']:.1f}% "
                f"of total {metric}."
            )
        else:
            summary.append(f"{first[dim]} is the leading contributor by {metric}.")

    trend = _trend(df)
    ti = _trend_insight(trend, metric)
    if ti and np.isfinite(ti["change_pct"]):
        summary.append(
            f"The latest period changed by {ti['change_pct']:+.1f}% versus the previous period."
        )

    if data["missing_cells"] == 0 and data["duplicate_rows"] == 0:
        summary.append("No missing cells or duplicate rows were detected in the selected dataset.")
    else:
        summary.append(
            f"Data-quality review identified {data['missing_cells']:,} missing cells and "
            f"{data['duplicate_rows']:,} duplicate rows."
        )

    return summary


def generate_management_report(df, dataset_name, selected, preview=False):
    data = build_report_data(df)
    kpis, metric, formula = _kpis(df)
    top = _contribution(df) if selected.get("top_bottom") else pd.DataFrame()
    trend = _trend(df) if selected.get("trend") else pd.DataFrame()

    return {
        "dataset_name": dataset_name,
        "summary": _executive_summary(df) if selected.get("summary") else [],
        "kpis": kpis if selected.get("kpis") else [],
        "findings": _findings(df) if selected.get("findings") else [],
        "actions": _management_actions(df) if selected.get("actions") else [],
        "top_bottom": top,
        "trend": trend,
        "quality": data if selected.get("quality") else {},
        "metric": metric,
        "formula": formula,
        "rows": len(df),
    }


def _chart_png(df, kind):
    if kind == "trend":
        d = _trend(df)
        if d.empty:
            return None
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.plot(d.iloc[:, 0], d.iloc[:, 1], marker="o")
        ax.set_title("Monthly Trend")
        ax.set_xlabel("Period")
        ax.set_ylabel(str(d.columns[1]))
        ax.tick_params(axis="x", rotation=45)
    else:
        d = _top_bottom(df)
        if d.empty:
            return None
        fig, ax = plt.subplots(figsize=(8, 4.2))
        dd = d.iloc[::-1]
        ax.barh(dd.iloc[:, 1].astype(str), dd.iloc[:, 2])
        ax.set_title(f"Top {len(d)} {d.columns[1]} by {d.columns[2]}")
        ax.set_xlabel(str(d.columns[2]))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _table(dataframe, widths=None):
    data = [list(dataframe.columns)] + dataframe.astype(str).values.tolist()
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def generate_pdf_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {
        k: True for k in [
            "summary", "kpis", "findings", "actions", "top_bottom",
            "trend", "charts", "quality", "appendix", "anomalies", "forecast"
        ]
    }
    r = generate_management_report(df, dataset_name, selected)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "title", parent=styles["Title"], fontSize=24, alignment=TA_CENTER, spaceAfter=16
    )
    h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=15, spaceBefore=14, spaceAfter=8)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=5)

    story = [
        Paragraph("InsightAI Management Intelligence Report", title),
        Paragraph(f"<b>Dataset:</b> {dataset_name}", body),
        Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", body),
        Spacer(1, 10),
    ]

    if selected.get("summary"):
        story += [Paragraph("Executive Summary", h)]
        story += [Paragraph("• " + x, body) for x in r["summary"]]

    if selected.get("kpis"):
        story.append(Paragraph("Important KPIs / Values", h))
        kdf = pd.DataFrame([
            {"Metric": x["label"], "Value": x["value"]} for x in r["kpis"]
        ])
        story.append(_table(kdf, [3.4 * inch, 2.3 * inch]))

    if selected.get("top_bottom") and not r["top_bottom"].empty:
        story += [Paragraph("Top Contributors", h), _table(r["top_bottom"])]

    if selected.get("trend") and not r["trend"].empty:
        story.append(Paragraph("Trend Analysis", h))
        if selected.get("charts"):
            img = _chart_png(df, "trend")
            if img:
                story.append(Image(img, width=6.7 * inch, height=3.0 * inch))
        story.append(_table(r["trend"].tail(24)))

    if selected.get("findings"):
        story += [Paragraph("Key Findings", h)]
        story += [Paragraph("• " + x, body) for x in r["findings"]]

    if selected.get("actions"):
        story += [Paragraph("Recommended Investigation / Management Attention", h)]
        story += [Paragraph("• " + x, body) for x in r["actions"]]

    if selected.get("charts") and not selected.get("trend"):
        img = _chart_png(df, "top")
        if img:
            story += [
                Paragraph("Management Chart", h),
                Image(img, width=6.7 * inch, height=3.2 * inch),
            ]

    if selected.get("quality"):
        q = r["quality"]
        story += [
            Paragraph("Data Quality", h),
            Paragraph(
                f"Completeness: {q['completeness']:.1f}% | "
                f"Missing cells: {q['missing_cells']:,} | "
                f"Duplicates: {q['duplicate_rows']:,}",
                body,
            ),
        ]

    if selected.get("appendix"):
        story.append(PageBreak())
        story += [Paragraph("Filtered Data Appendix", h), _table(df.head(100))]

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_docx_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {
        k: True for k in [
            "summary", "kpis", "findings", "actions", "top_bottom",
            "trend", "charts", "quality", "appendix", "anomalies", "forecast"
        ]
    }
    r = generate_management_report(df, dataset_name, selected)

    doc = Document()
    doc.add_heading("InsightAI Management Intelligence Report", 0)
    doc.add_paragraph(f"Dataset: {dataset_name}")
    doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if selected.get("summary"):
        doc.add_heading("Executive Summary", level=1)
        for x in r["summary"]:
            doc.add_paragraph(x, style="List Bullet")

    if selected.get("kpis"):
        doc.add_heading("Important KPIs / Values", level=1)
        for x in r["kpis"]:
            doc.add_paragraph(f"{x['label']}: {x['value']}")

    if selected.get("top_bottom") and not r["top_bottom"].empty:
        doc.add_heading("Top Contributors", level=1)
        t = doc.add_table(rows=1, cols=len(r["top_bottom"].columns))
        for i, c in enumerate(r["top_bottom"].columns):
            t.rows[0].cells[i].text = str(c)
        for _, row in r["top_bottom"].iterrows():
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = str(v)

    if selected.get("trend") and not r["trend"].empty:
        doc.add_heading("Trend Analysis", level=1)
        for _, row in r["trend"].tail(24).iterrows():
            doc.add_paragraph(" | ".join(map(str, row.tolist())))

    if selected.get("findings"):
        doc.add_heading("Key Findings", level=1)
        for x in r["findings"]:
            doc.add_paragraph(x, style="List Bullet")

    if selected.get("actions"):
        doc.add_heading("Recommended Investigation / Management Attention", level=1)
        for x in r["actions"]:
            doc.add_paragraph(x, style="List Bullet")

    if selected.get("quality"):
        q = r["quality"]
        doc.add_heading("Data Quality", level=1)
        doc.add_paragraph(
            f"Completeness: {q['completeness']:.1f}% | "
            f"Missing: {q['missing_cells']:,} | "
            f"Duplicates: {q['duplicate_rows']:,}"
        )

    if selected.get("appendix"):
        doc.add_heading("Filtered Data Appendix", level=1)
        t = doc.add_table(rows=1, cols=len(df.columns))
        for i, c in enumerate(df.columns):
            t.rows[0].cells[i].text = str(c)
        for _, row in df.head(100).iterrows():
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = str(v)

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out.getvalue()


def generate_excel_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {
        k: True for k in [
            "summary", "kpis", "findings", "actions", "top_bottom",
            "trend", "charts", "quality", "appendix", "anomalies", "forecast"
        ]
    }
    r = generate_management_report(df, dataset_name, selected)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        if selected.get("kpis"):
            pd.DataFrame([
                {"Metric": x["label"], "Value": x["value"]} for x in r["kpis"]
            ]).to_excel(writer, index=False, sheet_name="KPIs")

        if selected.get("top_bottom") and not r["top_bottom"].empty:
            r["top_bottom"].to_excel(writer, index=False, sheet_name="Top Contributors")

        if selected.get("trend") and not r["trend"].empty:
            r["trend"].to_excel(writer, index=False, sheet_name="Trend")

        if selected.get("findings"):
            pd.DataFrame({"Finding": r["findings"]}).to_excel(
                writer, index=False, sheet_name="Findings"
            )

        if selected.get("actions"):
            pd.DataFrame({"Management Attention": r["actions"]}).to_excel(
                writer, index=False, sheet_name="Actions"
            )

        if selected.get("quality"):
            pd.DataFrame([r["quality"]]).to_excel(
                writer, index=False, sheet_name="Data Quality"
            )

        if selected.get("appendix"):
            df.head(10000).to_excel(writer, index=False, sheet_name="Data Appendix")

        if selected.get("summary"):
            pd.DataFrame({"Executive Summary": r["summary"]}).to_excel(
                writer, index=False, sheet_name="Executive Summary"
            )

    out.seek(0)
    return out.getvalue()


# Backward-compatible helpers
def generate_executive_summary(df, report_data=None):
    return _executive_summary(df)


def generate_report_findings(df):
    return _findings(df)


def numeric_statistics(df):
    return (
        df.select_dtypes(include=np.number)
        .describe()
        .T.reset_index()
        .rename(columns={"index": "Column"})
    )


def categorical_statistics(df):
    rows = []
    for c in df.select_dtypes(include=["object", "category", "bool"]).columns:
        vc = df[c].value_counts(dropna=True)
        rows.append({
            "Column": c,
            "Unique Values": int(df[c].nunique(dropna=True)),
            "Missing": int(df[c].isna().sum()),
            "Top Value": str(vc.index[0]) if not vc.empty else "",
        })
    return pd.DataFrame(rows)


def correlation_summary(df):
    n = df.select_dtypes(include=np.number)
    if n.shape[1] < 2:
        return pd.DataFrame()
    c = n.corr()
    rows = []
    for i, a in enumerate(c.columns):
        for j, b in enumerate(c.columns):
            if j > i and pd.notna(c.iloc[i, j]):
                rows.append({
                    "Field 1": a,
                    "Field 2": b,
                    "Correlation": round(float(c.iloc[i, j]), 3),
                })
    return pd.DataFrame(rows)
