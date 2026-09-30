
import io
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from docx import Document
from docx.shared import Inches, Pt
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.chart import BarChart, LineChart, Reference


def _sales_metric(df):
    if "Quantity" in df.columns and "UnitPrice" in df.columns:
        q = pd.to_numeric(df["Quantity"], errors="coerce")
        p = pd.to_numeric(df["UnitPrice"], errors="coerce")
        return q * p, "Sales Value", "Quantity × UnitPrice"
    candidates = [c for c in df.select_dtypes(include=np.number).columns
                  if not any(x in str(c).lower() for x in ["id", "code", "zip", "postal"])]
    if candidates:
        c = candidates[0]
        return pd.to_numeric(df[c], errors="coerce"), str(c), str(c)
    return None, None, None


def build_report_data(df):
    rows, cols = len(df), len(df.columns)
    cells = rows * cols
    missing = int(df.isna().sum().sum())
    return {
        "rows": rows, "columns": cols, "missing_cells": missing,
        "duplicate_rows": int(df.duplicated().sum()),
        "completeness": ((cells-missing)/cells*100) if cells else 100,
        "numeric_columns": list(df.select_dtypes(include=np.number).columns),
        "categorical_columns": list(df.select_dtypes(include=["object","category","bool"]).columns),
        "datetime_columns": list(df.select_dtypes(include=["datetime","datetimetz"]).columns),
    }


def _detect_date(df):
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    for c in df.columns:
        if any(x in str(c).lower() for x in ["date","time","timestamp"]):
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() >= 0.6:
                return c
    return None


def _kpis(df):
    values, name, formula = _sales_metric(df)
    out = []
    if values is not None:
        out.append({"label": f"Total {name}", "value": f"{values.sum():,.2f}", "raw": float(values.sum())})
        out.append({"label": f"Average {name}", "value": f"{values.mean():,.2f}", "raw": float(values.mean())})
        out.append({"label": f"Maximum {name}", "value": f"{values.max():,.2f}", "raw": float(values.max())})
    if "Quantity" in df.columns:
        q = pd.to_numeric(df["Quantity"], errors="coerce").sum()
        out.append({"label": "Total Quantity", "value": f"{q:,.0f}", "raw": float(q)})
    if "CustomerID" in df.columns:
        n = df["CustomerID"].nunique(dropna=True)
        out.append({"label": "Customers", "value": f"{n:,}", "raw": float(n)})
    out.append({"label": "Transactions / Rows", "value": f"{len(df):,}", "raw": float(len(df))})
    return out, name, formula


def _top_bottom(df, n=10):
    values, metric, formula = _sales_metric(df)
    if values is None:
        return pd.DataFrame()
    candidates = [c for c in df.select_dtypes(include=["object","category"]).columns
                  if df[c].nunique(dropna=True) <= 1000]
    if not candidates:
        return pd.DataFrame()
    # Prefer business dimensions.
    preferred = next((c for c in candidates if str(c).lower() in
                      ["country","product","description","category","region","customer","customerid"]), candidates[0])
    temp = pd.DataFrame({"Dimension": df[preferred].astype("string"), "Metric": values})
    temp = temp.dropna(subset=["Dimension"]).groupby("Dimension", as_index=False)["Metric"].sum()
    temp = temp.sort_values("Metric", ascending=False).head(n)
    temp.insert(0, "Rank", range(1, len(temp)+1))
    temp = temp.rename(columns={"Dimension": preferred, "Metric": metric})
    return temp


def _trend(df):
    values, metric, formula = _sales_metric(df)
    date_col = _detect_date(df)
    if values is None or date_col is None:
        return pd.DataFrame()
    temp = pd.DataFrame({"Date": pd.to_datetime(df[date_col], errors="coerce"), "Value": values})
    temp = temp.dropna(subset=["Date","Value"])
    if temp.empty:
        return pd.DataFrame()
    temp["Period"] = temp["Date"].dt.to_period("M").astype(str)
    out = temp.groupby("Period", as_index=False)["Value"].sum()
    out = out.rename(columns={"Value": metric})
    return out


def _summary(df, data):
    s = [f"The dataset contains {data['rows']:,} rows across {data['columns']:,} fields."]
    kpis, metric, formula = _kpis(df)
    if metric:
        total = next((x["value"] for x in kpis if x["label"].startswith("Total ")), None)
        s.append(f"Total {metric} is {total}, calculated using {formula}.")
    if len(df):
        if data["missing_cells"] == 0:
            s.append("No missing cells were detected in the selected dataset.")
        else:
            s.append(f"{data['missing_cells']:,} missing cells should be reviewed.")
    tb = _top_bottom(df)
    if not tb.empty:
        s.append(f"The leading {tb.columns[1]} is {tb.iloc[0,1]} with {tb.iloc[0,2]:,.2f} in {metric}.")
    tr = _trend(df)
    if len(tr) >= 2:
        peak = tr.loc[tr.iloc[:,1].idxmax()]
        low = tr.loc[tr.iloc[:,1].idxmin()]
        s.append(f"The peak monthly {metric} is {peak.iloc[0]} at {peak.iloc[1]:,.2f}; the lowest is {low.iloc[0]} at {low.iloc[1]:,.2f}.")
    return s


def _findings(df):
    findings = []
    data = build_report_data(df)
    if data["duplicate_rows"]:
        findings.append(f"{data['duplicate_rows']:,} duplicate rows were identified.")
    miss = df.isna().sum().sort_values(ascending=False)
    for c, n in miss[miss > 0].head(3).items():
        findings.append(f"{c} has {int(n):,} missing values ({n/len(df)*100:.1f}% of rows).")
    tb = _top_bottom(df)
    if not tb.empty:
        findings.append(f"{tb.iloc[0,1]} is the largest contributor in the selected dimension.")
    tr = _trend(df)
    if len(tr) >= 2:
        pct = (tr.iloc[-1,1] - tr.iloc[-2,1]) / abs(tr.iloc[-2,1]) * 100 if tr.iloc[-2,1] else 0
        findings.append(f"The latest period changed by {pct:+.1f}% versus the previous period.")
    return findings or ["No major automatic findings were identified from the selected dataset."]


def generate_management_report(df, dataset_name, selected, preview=False):
    data = build_report_data(df)
    k, metric, formula = _kpis(df)
    result = {
        "summary": _summary(df, data) if selected.get("summary") else [],
        "kpis": k if selected.get("kpis") else [],
        "findings": _findings(df) if selected.get("findings") else [],
        "top_bottom": _top_bottom(df) if selected.get("top_bottom") else pd.DataFrame(),
        "trend": _trend(df) if selected.get("trend") else pd.DataFrame(),
        "quality": data if selected.get("quality") else {},
        "metric": metric, "formula": formula, "rows": len(df),
    }
    return result


def _chart_png(df, kind):
    if kind == "trend":
        d = _trend(df)
        if d.empty: return None
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.plot(d.iloc[:,0], d.iloc[:,1], marker="o")
        ax.set_title("Monthly Trend")
        ax.set_xlabel("Period"); ax.set_ylabel(str(d.columns[1]))
        ax.tick_params(axis="x", rotation=45)
    else:
        d = _top_bottom(df)
        if d.empty: return None
        fig, ax = plt.subplots(figsize=(8, 4.2))
        dd = d.iloc[::-1]
        ax.barh(dd.iloc[:,1].astype(str), dd.iloc[:,2])
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
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1e293b")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    return t


def generate_pdf_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {k: True for k in ["summary","kpis","findings","top_bottom","trend","charts","quality","appendix","anomalies","forecast"]}
    r = generate_management_report(df, dataset_name, selected)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=24, alignment=TA_CENTER, spaceAfter=16)
    h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=15, spaceBefore=14, spaceAfter=8)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=5)
    story = [Paragraph("InsightAI Management Report", title),
             Paragraph(f"<b>Dataset:</b> {dataset_name}", body),
             Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", body), Spacer(1,10)]
    if selected.get("summary"):
        story += [Paragraph("Executive Summary",h)] + [Paragraph("• "+x,body) for x in r["summary"]]
    if selected.get("kpis"):
        story.append(Paragraph("Important KPIs / Values",h))
        kdf = pd.DataFrame([{"Metric":x["label"],"Value":x["value"]} for x in r["kpis"]])
        story.append(_table(kdf, [3.4*inch,2.3*inch]))
    if selected.get("top_bottom") and not r["top_bottom"].empty:
        story += [Paragraph("Top Performers",h), _table(r["top_bottom"])]
    if selected.get("trend") and not r["trend"].empty:
        story += [Paragraph("Trend Analysis",h)]
        if selected.get("charts"):
            img = _chart_png(df,"trend")
            if img: story.append(Image(img,width=6.7*inch,height=3.0*inch))
        story.append(_table(r["trend"].tail(24)))
    if selected.get("findings"):
        story += [Paragraph("Key Findings",h)] + [Paragraph("• "+x,body) for x in r["findings"]]
    if selected.get("charts") and not selected.get("trend"):
        img = _chart_png(df,"top")
        if img: story += [Paragraph("Management Chart",h), Image(img,width=6.7*inch,height=3.2*inch)]
    if selected.get("quality"):
        story += [Paragraph("Data Quality",h), Paragraph(f"Completeness: {r['quality']['completeness']:.1f}% | Missing cells: {r['quality']['missing_cells']:,} | Duplicates: {r['quality']['duplicate_rows']:,}",body)]
    if selected.get("appendix"):
        story.append(PageBreak())
        story += [Paragraph("Filtered Data Appendix",h), _table(df.head(100))]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_docx_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {k: True for k in ["summary","kpis","findings","top_bottom","trend","charts","quality","appendix","anomalies","forecast"]}
    r = generate_management_report(df, dataset_name, selected)
    doc = Document()
    doc.add_heading("InsightAI Management Report", 0)
    doc.add_paragraph(f"Dataset: {dataset_name}")
    doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if selected.get("summary"):
        doc.add_heading("Executive Summary", level=1)
        for x in r["summary"]: doc.add_paragraph(x, style="List Bullet")
    if selected.get("kpis"):
        doc.add_heading("Important KPIs / Values", level=1)
        for x in r["kpis"]: doc.add_paragraph(f"{x['label']}: {x['value']}")
    if selected.get("top_bottom") and not r["top_bottom"].empty:
        doc.add_heading("Top Performers", level=1)
        t = doc.add_table(rows=1, cols=len(r["top_bottom"].columns))
        for i,c in enumerate(r["top_bottom"].columns): t.rows[0].cells[i].text = str(c)
        for _,row in r["top_bottom"].iterrows():
            cells=t.add_row().cells
            for i,v in enumerate(row): cells[i].text=str(v)
    if selected.get("trend") and not r["trend"].empty:
        doc.add_heading("Trend Analysis", level=1)
        for _,row in r["trend"].tail(24).iterrows(): doc.add_paragraph(" | ".join(map(str,row.tolist())))
    if selected.get("findings"):
        doc.add_heading("Key Findings", level=1)
        for x in r["findings"]: doc.add_paragraph(x, style="List Bullet")
    if selected.get("quality"):
        doc.add_heading("Data Quality", level=1)
        q=r["quality"]; doc.add_paragraph(f"Completeness: {q['completeness']:.1f}% | Missing: {q['missing_cells']:,} | Duplicates: {q['duplicate_rows']:,}")
    if selected.get("appendix"):
        doc.add_heading("Filtered Data Appendix", level=1)
        t=doc.add_table(rows=1, cols=len(df.columns))
        for i,c in enumerate(df.columns): t.rows[0].cells[i].text=str(c)
        for _,row in df.head(100).iterrows():
            cells=t.add_row().cells
            for i,v in enumerate(row): cells[i].text=str(v)
    out=io.BytesIO(); doc.save(out); out.seek(0); return out.getvalue()


def generate_excel_report(df, dataset_name="InsightAI Dataset", selected=None):
    selected = selected or {k: True for k in ["summary","kpis","findings","top_bottom","trend","charts","quality","appendix","anomalies","forecast"]}
    r = generate_management_report(df, dataset_name, selected)
    out=io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        if selected.get("kpis"):
            pd.DataFrame([{"Metric":x["label"],"Value":x["value"]} for x in r["kpis"]]).to_excel(writer,index=False,sheet_name="KPIs")
        if selected.get("top_bottom") and not r["top_bottom"].empty:
            r["top_bottom"].to_excel(writer,index=False,sheet_name="Top Performers")
        if selected.get("trend") and not r["trend"].empty:
            r["trend"].to_excel(writer,index=False,sheet_name="Trend")
        if selected.get("findings"):
            pd.DataFrame({"Finding":r["findings"]}).to_excel(writer,index=False,sheet_name="Findings")
        if selected.get("quality"):
            pd.DataFrame([r["quality"]]).to_excel(writer,index=False,sheet_name="Data Quality")
        if selected.get("appendix"):
            df.head(10000).to_excel(writer,index=False,sheet_name="Data Appendix")
        if selected.get("summary"):
            pd.DataFrame({"Executive Summary":r["summary"]}).to_excel(writer,index=False,sheet_name="Executive Summary")
    out.seek(0)
    return out.getvalue()


# Backward-compatible helpers used by older modules.
def generate_executive_summary(df, report_data=None):
    return _summary(df, report_data or build_report_data(df))

def generate_report_findings(df):
    return _findings(df)

def numeric_statistics(df):
    return df.select_dtypes(include=np.number).describe().T.reset_index().rename(columns={"index":"Column"})

def categorical_statistics(df):
    rows=[]
    for c in df.select_dtypes(include=["object","category","bool"]).columns:
        vc=df[c].value_counts(dropna=True)
        rows.append({"Column":c,"Unique Values":int(df[c].nunique(dropna=True)),
                     "Missing":int(df[c].isna().sum()),"Top Value":str(vc.index[0]) if not vc.empty else ""})
    return pd.DataFrame(rows)

def correlation_summary(df):
    n=df.select_dtypes(include=np.number)
    if n.shape[1]<2:return pd.DataFrame()
    c=n.corr(); rows=[]
    for i,a in enumerate(c.columns):
        for j,b in enumerate(c.columns):
            if j>i and pd.notna(c.iloc[i,j]):
                rows.append({"Field 1":a,"Field 2":b,"Correlation":round(float(c.iloc[i,j]),3)})
    return pd.DataFrame(rows)
