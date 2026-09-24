# InsightAI — AI-Powered Data Intelligence Platform

InsightAI is a general-purpose data intelligence platform built with Python and Streamlit.

Its purpose is to move beyond charts and dashboards and answer three questions:

> **What happened?**  
> **Why did it happen?**  
> **What should I investigate next?**

## Product architecture

```text
DATA LAYER
CSV / Excel / JSON / Parquet / PCAP / API
        ↓
DATA INTELLIGENCE
Detection / Profiling / Cleaning / Analytics
        ↓
ANALYTICS
Dashboard / KPI / Anomaly / Forecast
        ↓
AI LAYER
AI Analyst / AI Chat / Root Cause / Data Story
        ↓
DECISION INTELLIGENCE
What happened? → Why? → What next?
        ↓
REPORTING
PDF / Word / Excel
```

## Current repository

```text
AI-Dataanaylist/
├── streamlitapp.py
├── core/
├── ai/
├── pages/
├── components/
├── assets/
├── data/
├── requirements.txt
└── README.md
```

## Supported data

InsightAI is designed to work with:

- CSV
- Excel
- JSON
- Parquet
- ODS
- TXT / TSV
- PCAP
- PCAPNG
- CAP

Network captures are treated as a dedicated network-intelligence domain rather than simply as generic tables.

## Main workflow

```text
Upload / Select Dataset
        ↓
Dataset Detection
        ↓
Data Cleaning
        ↓
Data Explorer
        ↓
Dashboard
        ↓
AI Analyst
        ↓
Anomaly Detection
        ↓
Forecasting
        ↓
Reports
```

## AI roadmap

Planned advanced capabilities:

- AI Command Bar
- Conversational AI Data Chat
- Explain This Chart
- Root Cause Analysis
- Data Story
- AI-generated charts
- AI-generated dashboards
- AI Executive Brief
- What-if analysis
- RAG / FAISS retrieval
- Evidence and data lineage
- Multiple AI modes
- Automated monitoring and alerts

## Network / PCAP roadmap

Network captures will receive dedicated analytics for:

- protocol distribution
- source/destination analysis
- conversations and flows
- TCP/UDP analysis
- packet rate
- throughput
- retransmissions
- latency indicators
- errors and anomalies
- network-focused AI investigation

## Running locally

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
streamlit run streamlitapp.py
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlitapp.py
```

## AI provider

AI credentials should never be committed to GitHub.

For Streamlit deployments, use Streamlit Secrets.

Example:

```toml
GROQ_API_KEY = "your-key"
GROQ_MODEL = "openai/gpt-oss-120b"
```

## Development philosophy

InsightAI is being developed as a modular platform.

Major capabilities should live in separate modules so that:

- analytics changes do not break the UI
- AI changes do not break data loading
- PCAP logic remains isolated
- future RAG functionality can be added cleanly
- the same analytics engine can serve dashboards, AI and reports

## Roadmap

### Phase 0 — Foundation
- dependency cleanup
- dataset metadata
- dataset-type detection
- unified anomaly engine
- forecasting stabilization

### Phase 1 — Universal Data Intelligence
- semantic profiling
- dataset-aware cleaning
- PCAP/network intelligence
- unified analytics context

### Phase 2 — Workspace
- projects
- datasets
- analysis state
- dashboard state
- saved reports

### Phase 3 — AI Command Center
- single AI command bar
- conversational analysis
- chart explanations
- AI-generated visualizations

### Phase 4 — Decision Intelligence
- what happened
- why it happened
- what to investigate next

### Phase 5 — Advanced AI
- RAG
- FAISS
- data story
- root cause
- AI dashboards
- executive brief
- what-if analysis

### Phase 6 — Enterprise
- authentication
- workspaces
- permissions
- dataset versioning
- alerts
- scheduled analysis
- collaboration

## Important

Do not rename the main application to `app.py`.

The current application entry point is:

```text
streamlitapp.py
```
