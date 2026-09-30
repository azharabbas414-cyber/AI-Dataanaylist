import io
from datetime import datetime
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from docx import Document
from docx.shared import Inches, Pt
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


def generate_executive_summary(df, report_data=None):
    r = report_data or build_report_data(df); s = [
        f"The current report contains {r['rows']:,} rows and {r['columns']:,} columns.",
        f"Data completeness is {r['completeness']:.1f}%.",
        f"Missing cells: {r['missing_cells']:,}; duplicate rows: {r['duplicate_rows']:,}.",
    ]
    if r["numeric_columns"]: s.append(f"{len(r['numeric_columns'])} numeric fields are available for analysis.")
    if r["categorical_columns"]: s.append(f"{len(r['categorical_columns'])} categorical fields are available for segmentation.")
    return s


def generate_report_findings(df):
    findings=[]; missing=df.isna().sum(); missing=missing[missing>0]
    for col,count in missing.sort_values(ascending=False).head(5).items():
        findings.append(f"{col} contains {count:,} missing values ({count/len(df)*100:.1f}% of rows)." if len(df) else f"{col} contains {count:,} missing values.")
    dup=int(df.duplicated().sum())
    if dup: findings.append(f"The dataset contains {dup:,} duplicate rows.")
    for col in df.select_dtypes(include=np.number).columns:
        v=pd.to_numeric(df[col],errors="coerce").dropna()
        if len(v)<5: continue
        q1,q3=v.quantile(.25),v.quantile(.75); iqr=q3-q1
        if iqr: 
            n=int(((v<q1-1.5*iqr)|(v>q3+1.5*iqr)).sum())
            if n: findings.append(f"{col} contains approximately {n:,} potential statistical outliers.")
    return findings or ["No major automatic data-quality findings were identified."]


def numeric_statistics(df):
    x=df.select_dtypes(include=np.number)
    return x.describe().T.reset_index().rename(columns={"index":"Column"}) if not x.empty else pd.DataFrame()


def categorical_statistics(df):
    out=[]
    for c in df.select_dtypes(include=["object","category","bool"]).columns:
        vc=df[c].value_counts(dropna=True)
        out.append({"Column":c,"Unique Values":int(df[c].nunique(dropna=True)),"Missing":int(df[c].isna().sum()),"Top Value":vc.index[0] if not vc.empty else ""})
    return pd.DataFrame(out)


def correlation_summary(df):
    x=df.select_dtypes(include=np.number)
    if x.shape[1]<2:return pd.DataFrame()
    c=x.corr(); rows=[]; cols=list(c.columns)
    for i in range(len(cols)):
        for j in range(i+1,len(cols)):
            if pd.notna(c.iloc[i,j]): rows.append({"Field 1":cols[i],"Field 2":cols[j],"Correlation":round(float(c.iloc[i,j]),3)})
    return pd.DataFrame(rows).assign(_abs=lambda z:z["Correlation"].abs()).sort_values("_abs",ascending=False).drop(columns="_abs") if rows else pd.DataFrame()


def _summary_table(report_data):
    return pd.DataFrame({"Metric":["Rows","Columns","Completeness %","Missing Cells","Duplicate Rows"],"Value":[report_data["rows"],report_data["columns"],round(report_data["completeness"],2),report_data["missing_cells"],report_data["duplicate_rows"]]})


def generate_excel_report(df, dataset_name="InsightAI Dataset", filters=None):
    out=io.BytesIO(); wb=Workbook(); ws=wb.active; ws.title="Executive Summary"
    ws.append(["InsightAI Analytics Report"]); ws.append(["Dataset",dataset_name]); ws.append(["Generated",datetime.now().strftime("%Y-%m-%d %H:%M")]);
    r=build_report_data(df); ws.append([]); ws.append(["Metric","Value"])
    for row in _summary_table(r).itertuples(index=False): ws.append(list(row))
    if filters:
        ws.append([]); ws.append(["Applied Filters"])
        for k,v in filters.items(): ws.append([k,str(v)])
    for sheet, frame in [("Numeric Statistics",numeric_statistics(df)),("Category Summary",categorical_statistics(df)),("Correlations",correlation_summary(df))]:
        sh=wb.create_sheet(sheet)
        if not frame.empty:
            for row in dataframe_to_rows(frame,index=False,header=True): sh.append(list(row))
    raw=wb.create_sheet("Filtered Data")
    # Export a practical preview rather than creating enormous Excel files.
    preview=df.head(100000)
    for row in dataframe_to_rows(preview,index=False,header=True): raw.append(list(row))
    for sh in wb.worksheets:
        sh.freeze_panes="A2"; sh.column_dimensions["A"].width=28
    wb.save(out); out.seek(0); return out.getvalue()


def _pdf_table(data, widths=None):
    t=Table(data,colWidths=widths,repeatRows=1); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1f2937")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
    return t


def generate_pdf_report(df,dataset_name="InsightAI Dataset",filters=None):
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36); styles=getSampleStyleSheet(); story=[Paragraph("InsightAI Analytics Report",styles["Title"]),Paragraph(dataset_name,styles["Heading2"]),Paragraph(datetime.now().strftime("Generated %Y-%m-%d %H:%M"),styles["Normal"]),Spacer(1,12)]
    r=build_report_data(df); story += [Paragraph("Executive Summary",styles["Heading2"])]
    for x in generate_executive_summary(df,r): story.append(Paragraph("• "+x,styles["BodyText"]))
    if filters: story += [Spacer(1,8),Paragraph("Applied Filters",styles["Heading2"])] + [Paragraph(f"• {k}: {v}",styles["BodyText"]) for k,v in filters.items()]
    story += [Spacer(1,10),Paragraph("Key Findings",styles["Heading2"])] + [Paragraph("• "+x,styles["BodyText"]) for x in generate_report_findings(df)]
    story += [Spacer(1,10),Paragraph("Numeric Statistics",styles["Heading2"])]
    n=numeric_statistics(df)
    if not n.empty:
        show=n.head(15).copy(); story.append(_pdf_table([list(show.columns)]+show.round(3).astype(str).values.tolist()))
    doc.build(story); out.seek(0); return out.getvalue()


def generate_docx_report(df,dataset_name="InsightAI Dataset",filters=None):
    out=io.BytesIO(); doc=Document(); doc.add_heading("InsightAI Analytics Report",0); doc.add_paragraph(dataset_name); doc.add_paragraph(datetime.now().strftime("Generated %Y-%m-%d %H:%M")); r=build_report_data(df)
    doc.add_heading("Executive Summary",1)
    for x in generate_executive_summary(df,r): doc.add_paragraph(x,style="List Bullet")
    if filters:
        doc.add_heading("Applied Filters",1)
        for k,v in filters.items(): doc.add_paragraph(f"{k}: {v}")
    doc.add_heading("Key Findings",1)
    for x in generate_report_findings(df): doc.add_paragraph(x,style="List Bullet")
    doc.add_heading("Numeric Statistics",1); n=numeric_statistics(df)
    if not n.empty:
        n=n.head(30); table=doc.add_table(rows=1,cols=len(n.columns)); table.style="Table Grid"
        for i,c in enumerate(n.columns): table.rows[0].cells[i].text=str(c)
        for vals in n.round(3).astype(str).values:
            cells=table.add_row().cells
            for i,v in enumerate(vals): cells[i].text=v
    doc.save(out); out.seek(0); return out.getvalue()
