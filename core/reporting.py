import io
from datetime import datetime
import re
import numpy as np
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from reportlab.lib.units import inch
from docx import Document
from docx.shared import Inches
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows


def build_report_data(df):
    rows, columns = len(df), len(df.columns)
    total_cells = rows * columns
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    completeness = ((total_cells - missing_cells) / total_cells * 100) if total_cells else 100
    return {
        "rows": rows, "columns": columns, "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows, "completeness": completeness,
        "numeric_columns": list(df.select_dtypes(include=np.number).columns),
        "categorical_columns": list(df.select_dtypes(include=["object", "category", "bool"]).columns),
        "datetime_columns": list(df.select_dtypes(include=["datetime", "datetimetz"]).columns),
    }


def detect_calculated_metrics(df):
    out = {}
    cols = {str(c).lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    qty = next((cols[k] for k in ["quantity", "qty", "units"] if k in cols), None)
    price = next((cols[k] for k in ["unitprice", "price", "unitcost"] if k in cols), None)
    if qty and price:
        q = pd.to_numeric(df[qty], errors="coerce")
        p = pd.to_numeric(df[price], errors="coerce")
        out["Sales Value"] = q * p
    return out


def metric_candidates(df):
    metrics = {}
    for c in df.select_dtypes(include=np.number).columns:
        metrics[str(c)] = pd.to_numeric(df[c], errors="coerce")
    metrics.update(detect_calculated_metrics(df))
    return metrics


def kpi_summary(df):
    metrics = metric_candidates(df)
    result = []
    for name, s in metrics.items():
        v = s.dropna()
        if len(v):
            result.append({
                "Metric": name,
                "Sum": float(v.sum()),
                "Average": float(v.mean()),
                "Minimum": float(v.min()),
                "Maximum": float(v.max()),
            })
    return pd.DataFrame(result)


def top_category_tables(df, limit=10):
    result = []
    metrics = metric_candidates(df)
    cats = list(df.select_dtypes(include=["object", "category", "bool"]).columns)
    for metric_name, metric in metrics.items():
        work = pd.DataFrame({"Metric": metric, **{c: df[c] for c in cats}})
        for c in cats[:8]:
            temp = work.groupby(c, dropna=False)["Metric"].sum().sort_values(ascending=False).head(limit).reset_index()
            if len(temp) > 1:
                temp.columns = [c, metric_name]
                result.append((f"Top {limit} {c} by {metric_name}", temp))
    return result[:12]


def time_series_tables(df, limit=24):
    metrics = metric_candidates(df)
    dates = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)
    # Detect object columns that are parseable as dates.
    for c in df.columns:
        if c in dates:
            continue
        if df[c].dtype == object:
            parsed = pd.to_datetime(df[c], errors="coerce")
            if len(df) and parsed.notna().mean() >= 0.8:
                dates.append(c)
    result = []
    for d in dates[:3]:
        dt = pd.to_datetime(df[d], errors="coerce")
        for metric_name, metric in list(metrics.items())[:5]:
            temp = pd.DataFrame({"Date": dt, metric_name: metric}).dropna(subset=["Date"])
            if temp.empty:
                continue
            temp["Period"] = temp["Date"].dt.to_period("M").astype(str)
            agg = temp.groupby("Period")[metric_name].sum().tail(limit).reset_index()
            if len(agg) >= 2:
                result.append((f"Monthly {metric_name} by {d}", agg.rename(columns={"Period": "Month"})))
    return result[:8]


def numeric_statistics(df):
    x = df.select_dtypes(include=np.number)
    return x.describe().T.reset_index().rename(columns={"index": "Column"}) if not x.empty else pd.DataFrame()


def categorical_statistics(df):
    out = []
    for c in df.select_dtypes(include=["object", "category", "bool"]).columns:
        vc = df[c].value_counts(dropna=True)
        out.append({"Column": c, "Unique Values": int(df[c].nunique(dropna=True)), "Missing": int(df[c].isna().sum()), "Top Value": vc.index[0] if not vc.empty else ""})
    return pd.DataFrame(out)


def correlation_summary(df):
    x = df.select_dtypes(include=np.number)
    if x.shape[1] < 2:
        return pd.DataFrame()
    c = x.corr(); rows = []; cols = list(c.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            if pd.notna(c.iloc[i, j]):
                rows.append({"Field 1": cols[i], "Field 2": cols[j], "Correlation": round(float(c.iloc[i, j]), 3)})
    return pd.DataFrame(rows).assign(_abs=lambda z: z["Correlation"].abs()).sort_values("_abs", ascending=False).drop(columns="_abs") if rows else pd.DataFrame()


def generate_executive_summary(df, report_data=None):
    r = report_data or build_report_data(df)
    lines = [
        f"The report covers {r['rows']:,} records across {r['columns']:,} fields.",
        f"Overall data completeness is {r['completeness']:.1f}%, with {r['missing_cells']:,} missing cells and {r['duplicate_rows']:,} duplicate rows.",
    ]
    metrics = metric_candidates(df)
    if "Sales Value" in metrics:
        v = metrics["Sales Value"].dropna()
        if len(v): lines.append(f"Total sales value is {v.sum():,.2f}, with an average sales value per record of {v.mean():,.2f}.")
    for name, s in list(metrics.items())[:3]:
        v = s.dropna()
        if len(v): lines.append(f"{name}: total {v.sum():,.2f}; average {v.mean():,.2f}; maximum {v.max():,.2f}.")
    return list(dict.fromkeys(lines))


def generate_report_findings(df):
    findings = []
    missing = df.isna().sum(); missing = missing[missing > 0]
    for col, count in missing.sort_values(ascending=False).head(5).items():
        findings.append(f"{col} contains {count:,} missing values ({count / len(df) * 100:.1f}% of rows)." if len(df) else f"{col} contains {count:,} missing values.")
    dup = int(df.duplicated().sum())
    if dup:
        findings.append(f"The dataset contains {dup:,} duplicate rows.")
    metrics = metric_candidates(df)
    for name, s in list(metrics.items())[:8]:
        v = s.dropna()
        if len(v) >= 5:
            q1, q3 = v.quantile(.25), v.quantile(.75); iqr = q3 - q1
            if iqr:
                n = int(((v < q1 - 1.5 * iqr) | (v > q3 + 1.5 * iqr)).sum())
                if n:
                    findings.append(f"{name} contains approximately {n:,} potential statistical outliers.")
    return findings or ["No major automatic data-quality findings were identified."]


def _safe_sheet(name):
    return re.sub(r"[\\/*?:\[\]]", "_", name)[:31] or "Report"


def _table_pdf(data, widths=None):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _chart_png(title, frame, xcol, ycol, kind="bar"):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if kind == "line":
        ax.plot(frame[xcol].astype(str), frame[ycol])
    else:
        plot_df = frame.head(15).iloc[::-1]
        ax.barh(plot_df[xcol].astype(str), plot_df[ycol])
    ax.set_title(title)
    ax.grid(axis="y", alpha=.2)
    fig.tight_layout()
    out = io.BytesIO(); fig.savefig(out, format="png", dpi=150, bbox_inches="tight"); plt.close(fig); out.seek(0)
    return out


def _selected_sections(options):
    defaults = ["Executive Summary", "KPI Summary", "Key Findings", "Top/Bottom Analysis", "Trend Analysis", "Charts", "Data Quality"]
    return [x for x in defaults if options.get(x, True)]


def generate_excel_report(df, dataset_name="InsightAI Dataset", filters=None, options=None, saved_charts=None):
    options = options or {}; sections = _selected_sections(options)
    out = io.BytesIO(); wb = Workbook(); ws = wb.active; ws.title = "Executive Summary"
    ws.append(["InsightAI Management Analytics Report"]); ws.append(["Dataset", dataset_name]); ws.append(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")])
    if filters:
        ws.append([]); ws.append(["Applied Filters"])
        for k, v in filters.items(): ws.append([k, str(v)])
    r = build_report_data(df)
    if "Executive Summary" in sections:
        ws.append([]); ws.append(["Executive Summary"])
        for line in generate_executive_summary(df, r): ws.append([line])
    if "KPI Summary" in sections:
        ws.append([]); ws.append(["KPI", "Value"])
        metrics = metric_candidates(df)
        for name, s in metrics.items():
            v = s.dropna()
            if len(v): ws.append([f"Total {name}", float(v.sum())])
    if "Key Findings" in sections:
        ws.append([]); ws.append(["Key Findings"])
        for x in generate_report_findings(df): ws.append([x])
    if "Top/Bottom Analysis" in sections:
        for title, frame in top_category_tables(df):
            sh = wb.create_sheet(_safe_sheet(title));
            for row in dataframe_to_rows(frame, index=False, header=True): sh.append(list(row))
    if "Trend Analysis" in sections:
        for title, frame in time_series_tables(df):
            sh = wb.create_sheet(_safe_sheet(title));
            for row in dataframe_to_rows(frame, index=False, header=True): sh.append(list(row))
    if "Data Quality" in sections:
        for name, frame in [("Numeric Statistics", numeric_statistics(df)), ("Category Summary", categorical_statistics(df)), ("Correlations", correlation_summary(df))]:
            sh = wb.create_sheet(name)
            if not frame.empty:
                for row in dataframe_to_rows(frame, index=False, header=True): sh.append(list(row))
    if options.get("Raw Data", False):
        sh = wb.create_sheet("Filtered Data")
        preview = df.head(int(options.get("Raw Data Rows", 100000)))
        for row in dataframe_to_rows(preview, index=False, header=True): sh.append(list(row))
    if saved_charts and options.get("Chart Register", True):
        sh = wb.create_sheet("Chart Register")
        sh.append(["Title", "Section", "Chart Type", "Category", "Metric", "Aggregation", "Ranking"])
        for item in saved_charts:
            c = item.get("config", {})
            sh.append([item.get("title", c.get("title", "Saved Chart")), item.get("section", "Other"), c.get("chart_type", c.get("type", "")), c.get("x", c.get("category", "")), c.get("y", c.get("metric", "")), c.get("aggregation", ""), c.get("ranking", "")])
    for sh in wb.worksheets:
        sh.freeze_panes = "A2"
        sh.column_dimensions["A"].width = 34
    wb.save(out); out.seek(0); return out.getvalue()


def generate_pdf_report(df, dataset_name="InsightAI Dataset", filters=None, options=None, saved_charts=None):
    options = options or {}; sections = _selected_sections(options)
    out = io.BytesIO(); doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet(); story = [Paragraph("InsightAI Management Analytics Report", styles["Title"]), Paragraph(dataset_name, styles["Heading2"]), Paragraph(datetime.now().strftime("Generated %Y-%m-%d %H:%M"), styles["Normal"]), Spacer(1, 12)]
    if filters:
        story += [Paragraph("Report Scope & Filters", styles["Heading2"])]
        for k, v in filters.items(): story.append(Paragraph(f"• {k}: {v}", styles["BodyText"]))
    r = build_report_data(df)
    if "Executive Summary" in sections:
        story += [Spacer(1, 8), Paragraph("Executive Summary", styles["Heading2"])]
        for x in generate_executive_summary(df, r): story.append(Paragraph("• " + x, styles["BodyText"]))
    if "KPI Summary" in sections:
        story += [Spacer(1, 8), Paragraph("Management KPI Summary", styles["Heading2"])]
        rows = [["KPI", "Total", "Average", "Minimum", "Maximum"]]
        for name, s in metric_candidates(df).items():
            v = s.dropna()
            if len(v): rows.append([name, f"{v.sum():,.2f}", f"{v.mean():,.2f}", f"{v.min():,.2f}", f"{v.max():,.2f}"])
        story.append(_table_pdf(rows))
    if "Key Findings" in sections:
        story += [Spacer(1, 8), Paragraph("Key Findings", styles["Heading2"])]
        for x in generate_report_findings(df): story.append(Paragraph("• " + x, styles["BodyText"]))
    if "Top/Bottom Analysis" in sections:
        story += [Spacer(1, 8), Paragraph("Top Category Analysis", styles["Heading2"])]
        for title, frame in top_category_tables(df, limit=10)[:6]:
            story.append(Paragraph(title, styles["Heading3"]))
            story.append(_table_pdf([list(frame.columns)] + frame.round(2).astype(str).values.tolist()))
            story.append(Spacer(1, 6))
    if "Trend Analysis" in sections:
        story += [Spacer(1, 8), Paragraph("Trend Analysis", styles["Heading2"])]
        for title, frame in time_series_tables(df)[:4]:
            story.append(Paragraph(title, styles["Heading3"]))
            story.append(_table_pdf([list(frame.columns)] + frame.round(2).astype(str).values.tolist()))
    if "Charts" in sections:
        story += [PageBreak(), Paragraph("Management Charts", styles["Heading2"])]
        for title, frame in top_category_tables(df, limit=10)[:3]:
            x, y = frame.columns[:2]
            img = _chart_png(title, frame, x, y, "bar")
            story.append(Image(img, width=7.1 * inch, height=3.7 * inch)); story.append(Spacer(1, 8))
    if "Data Quality" in sections:
        story += [PageBreak(), Paragraph("Data Quality & Structure", styles["Heading2"])]
        story.append(_table_pdf([["Measure", "Value"], ["Rows", f"{r['rows']:,}"], ["Columns", f"{r['columns']:,}"], ["Completeness", f"{r['completeness']:.1f}%"], ["Missing Cells", f"{r['missing_cells']:,}"], ["Duplicate Rows", f"{r['duplicate_rows']:,}"]]))
        n = numeric_statistics(df)
        if not n.empty:
            story.append(Spacer(1, 8)); story.append(Paragraph("Numeric Statistics", styles["Heading3"]))
            show = n.head(15); story.append(_table_pdf([list(show.columns)] + show.round(3).astype(str).values.tolist()))
    if options.get("Raw Data", False):
        story += [PageBreak(), Paragraph("Filtered Data Appendix", styles["Heading2"])]
        preview = df.head(int(options.get("Raw Data Rows", 100)))
        if not preview.empty:
            show = preview.copy().astype(str).iloc[:, :8]
            story.append(_table_pdf([list(show.columns)] + show.values.tolist()))
    doc.build(story); out.seek(0); return out.getvalue()


def generate_docx_report(df, dataset_name="InsightAI Dataset", filters=None, options=None, saved_charts=None):
    options = options or {}; sections = _selected_sections(options)
    out = io.BytesIO(); doc = Document(); doc.add_heading("InsightAI Management Analytics Report", 0); doc.add_paragraph(dataset_name); doc.add_paragraph(datetime.now().strftime("Generated %Y-%m-%d %H:%M")); r = build_report_data(df)
    if filters:
        doc.add_heading("Report Scope & Filters", 1)
        for k, v in filters.items(): doc.add_paragraph(f"{k}: {v}")
    if "Executive Summary" in sections:
        doc.add_heading("Executive Summary", 1)
        for x in generate_executive_summary(df, r): doc.add_paragraph(x, style="List Bullet")
    if "KPI Summary" in sections:
        doc.add_heading("Management KPI Summary", 1)
        table = doc.add_table(rows=1, cols=5); table.style = "Table Grid"
        for i, c in enumerate(["KPI", "Total", "Average", "Minimum", "Maximum"]): table.rows[0].cells[i].text = c
        for name, s in metric_candidates(df).items():
            v = s.dropna()
            if len(v):
                cells = table.add_row().cells
                vals = [name, f"{v.sum():,.2f}", f"{v.mean():,.2f}", f"{v.min():,.2f}", f"{v.max():,.2f}"]
                for i, val in enumerate(vals): cells[i].text = val
    if "Key Findings" in sections:
        doc.add_heading("Key Findings", 1)
        for x in generate_report_findings(df): doc.add_paragraph(x, style="List Bullet")
    if "Top/Bottom Analysis" in sections:
        doc.add_heading("Top Category Analysis", 1)
        for title, frame in top_category_tables(df)[:6]:
            doc.add_heading(title, 2)
            table = doc.add_table(rows=1, cols=len(frame.columns)); table.style = "Table Grid"
            for i, c in enumerate(frame.columns): table.rows[0].cells[i].text = str(c)
            for vals in frame.round(2).astype(str).values:
                cells = table.add_row().cells
                for i, v in enumerate(vals): cells[i].text = v
    if "Trend Analysis" in sections:
        doc.add_heading("Trend Analysis", 1)
        for title, frame in time_series_tables(df)[:4]:
            doc.add_heading(title, 2); doc.add_paragraph(frame.to_string(index=False))
    if "Charts" in sections:
        doc.add_heading("Management Charts", 1)
        for title, frame in top_category_tables(df)[:3]:
            img = _chart_png(title, frame, frame.columns[0], frame.columns[1], "bar")
            doc.add_paragraph(title); doc.add_picture(img, width=Inches(6.5))
    if "Data Quality" in sections:
        doc.add_heading("Data Quality", 1)
        for x in [f"Rows: {r['rows']:,}", f"Columns: {r['columns']:,}", f"Completeness: {r['completeness']:.1f}%", f"Missing Cells: {r['missing_cells']:,}", f"Duplicate Rows: {r['duplicate_rows']:,}"]: doc.add_paragraph(x)
    if options.get("Raw Data", False):
        doc.add_heading("Filtered Data Appendix", 1); doc.add_paragraph(df.head(int(options.get("Raw Data Rows", 100))).to_string(index=False))
    doc.save(out); out.seek(0); return out.getvalue()
