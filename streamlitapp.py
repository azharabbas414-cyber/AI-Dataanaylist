from pathlib import Path

import pandas as pd
import streamlit as st

from core.data_loader import load_dataset, get_dataset_info
from core.dataset_intelligence import build_dataset_intelligence
from core.remote_data import fetch_remote_dataset


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="InsightAI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SESSION STATE
# ============================================================

if "active_dataframe" not in st.session_state:
    st.session_state.active_dataframe = None

if "active_dataset" not in st.session_state:
    st.session_state.active_dataset = None

if "active_source" not in st.session_state:
    st.session_state.active_source = None

if "dataset_info" not in st.session_state:
    st.session_state.dataset_info = None

if "capture_metadata" not in st.session_state:
    st.session_state.capture_metadata = None

if "dataset_intelligence" not in st.session_state:
    st.session_state.dataset_intelligence = None

if "dataset_collection" not in st.session_state:
    st.session_state.dataset_collection = {}


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_UPLOAD_TYPES = [
    "csv",
    "xlsx",
    "xls",
    "json",
    "parquet",
    "txt",
    "tsv",
    "ods",
    "pcap",
    "pcapng",
    "cap",
]


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main {
        padding-top: 1rem;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    /* ======================================================
       SIDEBAR
       ====================================================== */

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128, 128, 128, 0.18);
    }

    /* ======================================================
       HERO
       ====================================================== */

    .hero {
        padding: 38px 42px;
        border-radius: 22px;
        margin-bottom: 30px;
        background:
            linear-gradient(
                135deg,
                rgba(80, 70, 229, 0.14),
                rgba(30, 144, 255, 0.08)
            );
        border: 1px solid rgba(128, 128, 128, 0.18);
    }

    .hero-title {
        font-size: 44px;
        font-weight: 850;
        letter-spacing: -1.5px;
        line-height: 1.15;
        margin-bottom: 12px;
    }

    .hero-subtitle {
        font-size: 18px;
        opacity: 0.72;
        max-width: 900px;
        line-height: 1.6;
    }

    /* ======================================================
       SIDEBAR BRAND
       ====================================================== */

    .sidebar-brand {
        text-align: center;
        padding: 8px 0 18px 0;
    }

    .sidebar-brand-title {
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    .sidebar-brand-subtitle {
        font-size: 12px;
        opacity: 0.65;
        margin-top: 4px;
    }

    /* ======================================================
       WORKFLOW CARDS
       ====================================================== */

    .workflow-card {
        padding: 24px;
        min-height: 165px;
        border-radius: 18px;
        border: 1px solid rgba(128, 128, 128, 0.18);
        background: rgba(128, 128, 128, 0.035);
    }

    .workflow-icon {
        font-size: 30px;
        margin-bottom: 12px;
    }

    .workflow-title {
        font-size: 18px;
        font-weight: 750;
        margin-bottom: 8px;
    }

    .workflow-text {
        font-size: 13px;
        opacity: 0.68;
        line-height: 1.55;
    }

    /* ======================================================
       SECTION
       ====================================================== */

    .section-title {
        font-size: 25px;
        font-weight: 800;
        margin-top: 25px;
        margin-bottom: 6px;
    }

    .section-subtitle {
        font-size: 14px;
        opacity: 0.65;
        margin-bottom: 18px;
    }

    /* ======================================================
       ACTIVE DATASET
       ====================================================== */

    .active-card {
        padding: 24px;
        border-radius: 18px;
        border: 1px solid rgba(80, 70, 229, 0.28);
        background:
            linear-gradient(
                135deg,
                rgba(80, 70, 229, 0.09),
                rgba(30, 144, 255, 0.04)
            );
        margin-bottom: 15px;
    }

    .active-title {
        font-size: 21px;
        font-weight: 800;
        margin-bottom: 12px;
        word-break: break-word;
    }

    .active-value {
        font-size: 14px;
        margin-bottom: 5px;
    }

    /* ======================================================
       INFO BOX
       ====================================================== */

    .info-box {
        padding: 20px;
        border-radius: 16px;
        border: 1px solid rgba(128, 128, 128, 0.16);
        background: rgba(128, 128, 128, 0.035);
        margin: 10px 0 20px 0;
        line-height: 1.7;
    }

    /* ======================================================
       FOOTER
       ====================================================== */

    .footer {
        text-align: center;
        padding: 40px 0 10px 0;
        opacity: 0.5;
        font-size: 12px;
    }



    /* ======================================================
       POLISHED APP UI
       ====================================================== */

    .app-shell-note {
        font-size: 12px;
        color: #64748b;
        margin-top: -4px;
    }

    .sidebar-brand {
        background: linear-gradient(145deg, rgba(91,92,226,.12), rgba(14,165,233,.06));
        border: 1px solid rgba(91,92,226,.15);
        border-radius: 18px;
        padding: 18px 14px 16px;
        margin-bottom: 10px;
    }

    .sidebar-brand-title {
        font-size: 24px;
        font-weight: 850;
        letter-spacing: -.7px;
    }

    .sidebar-brand-subtitle {
        font-size: 11px;
        opacity: .62;
        margin-top: 5px;
    }

    .sidebar-section-label {
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .08em;
        opacity: .48;
        margin: 14px 0 7px;
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 42px 46px;
        border-radius: 26px;
        margin-bottom: 28px;
        background: linear-gradient(135deg, rgba(91,92,226,.13), rgba(14,165,233,.07) 55%, rgba(16,185,129,.05));
        border: 1px solid rgba(91,92,226,.16);
        box-shadow: 0 18px 45px rgba(15,23,42,.05);
    }

    .hero::after {
        content: "";
        position: absolute;
        width: 220px;
        height: 220px;
        right: -70px;
        top: -80px;
        border-radius: 50%;
        background: rgba(91,92,226,.08);
    }

    .source-card {
        min-height: 105px;
        padding: 20px;
        border-radius: 18px;
        border: 1px solid rgba(100,116,139,.16);
        background: rgba(255,255,255,.72);
    }

    .active-card {
        box-shadow: 0 12px 30px rgba(15,23,42,.05);
    }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,.72);
        border: 1px solid rgba(100,116,139,.13);
        border-radius: 15px;
        padding: 12px 14px;
    }

    .footer {
        border-top: 1px solid rgba(100,116,139,.12);
        margin-top: 45px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)




# ============================================================
# HOME PAGE CONTENT
# ============================================================

def home_page_content():
    # ============================================================
    # HERO
    # ============================================================

    st.html(
        """
        <div class="hero">

            <div class="hero-title">
                🧠 InsightAI
            </div>

            <div class="hero-subtitle">
                Turn raw data into answers, explanations and decisions — with analytics, AI, anomaly detection, forecasting and network intelligence in one workspace.
            </div>

        </div>
        """
    )


    # ============================================================
    # WORKFLOW HEADER
    # ============================================================

    st.html(
        """
        <div class="section-title">
            Your Analytics Workflow
        </div>

        <div class="section-subtitle">
            From raw data to actionable insights.
        </div>
        """
    )


    # ============================================================
    # WORKFLOW CARDS
    # ============================================================

    workflow_cols = st.columns(4)

    workflow = [
        (
            workflow_cols[0],
            "📂",
            "1. Select",
            "Upload one or more files or connect a public data URL.",
        ),
        (
            workflow_cols[1],
            "🧹",
            "2. Clean",
            "Identify and fix missing values, duplicates and data-quality issues.",
        ),
        (
            workflow_cols[2],
            "📊",
            "3. Explore",
            "Understand distributions, relationships, statistics and trends.",
        ),
        (
            workflow_cols[3],
            "🤖",
            "4. Analyze",
            "Use AI, anomaly detection, forecasting and advanced analytics.",
        ),
    ]


    for col, icon, title, description in workflow:

        with col:

            st.html(
                f"""
                <div class="workflow-card">

                    <div class="workflow-icon">
                        {icon}
                    </div>

                    <div class="workflow-title">
                        {title}
                    </div>

                    <div class="workflow-text">
                        {description}
                    </div>

                </div>
                """
            )


    st.write("")


    # ============================================================
    # DATA SOURCE HEADER
    # ============================================================

    st.html(
        """
        <div class="section-title">
            📂 Bring Your Data to InsightAI
        </div>

        <div class="section-subtitle">
            Upload one or more datasets, or fetch a public dataset directly
            from Google Drive, Google Sheets or a web URL.
        </div>
        """
    )


    # ============================================================
    # DATA SOURCE TABS
    # ============================================================

    source_tab1, source_tab2 = st.tabs(
        [
            "⬆️ Upload Files",
            "🔗 Google Drive / Web Link",
        ]
    )


    def _store_active_dataset(
        name: str,
        df: pd.DataFrame,
        detected_type: str,
        source: str,
    ):
        info = get_dataset_info(df)
        capture_metadata = info.get("capture_metadata")

        intelligence = build_dataset_intelligence(
            df,
            name,
            detected_type,
            capture_metadata,
        )

        st.session_state.dataset_collection[name] = {
            "dataframe": df,
            "info": info,
            "detected_type": detected_type,
            "source": source,
            "intelligence": intelligence,
        }

        st.session_state.active_dataset = name
        st.session_state.active_dataframe = df
        st.session_state.active_source = source
        st.session_state.dataset_info = info
        st.session_state.capture_metadata = capture_metadata
        st.session_state.dataset_intelligence = intelligence


    # ============================================================
    # MULTI-FILE UPLOAD
    # ============================================================

    with source_tab1:

        st.html(
            """
            <div class="info-box">
                <b>📦 Multi-File Dataset Upload</b>
                <br><br>
                Upload multiple CSV, Excel, JSON, Parquet, TXT/TSV, ODS
                or Wireshark PCAP/PCAPNG/CAP files in one operation.
                <br><br>
                Each file remains an independent dataset so you can switch
                between them without changing the original files.
            </div>
            """
        )

        uploaded_files = st.file_uploader(
            "Choose one or more datasets / Wireshark captures",
            type=SUPPORTED_UPLOAD_TYPES,
            accept_multiple_files=True,
            key="multi_dataset_upload",
            help="You can select multiple files at the same time.",
        )

        if uploaded_files:
            total_mb = sum(
                file.size for file in uploaded_files
            ) / (1024 * 1024)

            st.caption(
                f"**{len(uploaded_files)} file(s) selected** • "
                f"Total size: **{total_mb:.2f} MB**"
            )

            preview = pd.DataFrame(
                [
                    {
                        "File": file.name,
                        "Size (MB)": round(file.size / (1024 * 1024), 2),
                        "Extension": Path(file.name).suffix.lower(),
                    }
                    for file in uploaded_files
                ]
            )
            st.dataframe(preview, use_container_width=True, hide_index=True)

            if st.button(
                "🚀 Load All Selected Files",
                type="primary",
                use_container_width=True,
                key="load_multiple_files",
            ):
                loaded = 0
                errors = []

                with st.spinner("Loading and profiling selected datasets..."):
                    for file in uploaded_files:
                        try:
                            df, detected_type = load_dataset(file)
                            _store_active_dataset(
                                file.name,
                                df,
                                detected_type,
                                f"Uploaded File • {detected_type}",
                            )
                            loaded += 1
                        except Exception as exc:
                            errors.append(f"{file.name}: {exc}")

                if loaded:
                    st.success(f"✓ {loaded} dataset(s) loaded successfully.")

                for error in errors:
                    st.error(error)

                if loaded:
                    st.rerun()


    # ============================================================
    # GOOGLE DRIVE / WEB LINK
    # ============================================================

    with source_tab2:

        st.html(
            """
            <div class="info-box">
                <b>🔗 Connect a Public Data Source</b>
                <br><br>
                Paste a public <b>Google Drive</b>, <b>Google Sheets</b> or
                direct <b>web dataset URL</b>.
                <br><br>
                Supported remote formats include CSV, Excel, JSON, Parquet,
                ODS, TSV and other directly downloadable data files.
                Webpages containing HTML tables can also be imported.
                <br><br>
                <b>Google Drive:</b> the file must be shared as
                <i>Anyone with the link</i> for server-side fetching.
            </div>
            """
        )

        remote_url = st.text_input(
            "Google Drive / Google Sheets / Web Dataset URL",
            placeholder="https://drive.google.com/... or https://example.com/data.csv",
            key="remote_dataset_url",
        )

        if st.button(
            "🌐 Fetch Dataset",
            type="primary",
            use_container_width=True,
            key="fetch_remote_dataset",
        ):
            if not remote_url.strip():
                st.warning("Please paste a Google Drive or web URL first.")
            else:
                try:
                    with st.spinner("Fetching remote data and creating a dataset profile..."):
                        remote_file = fetch_remote_dataset(remote_url.strip())
                        df, detected_type = load_dataset(remote_file)
                        _store_active_dataset(
                            remote_file.name,
                            df,
                            detected_type,
                            f"Remote URL • {detected_type}",
                        )

                    st.success(
                        f"✓ {remote_file.name} fetched and loaded successfully."
                    )
                    st.rerun()

                except Exception as exc:
                    st.error("Unable to fetch this remote dataset.")
                    st.exception(exc)


    # ============================================================
    # LOADED DATASETS
    # ============================================================

    if st.session_state.dataset_collection:
        st.divider()
        st.markdown("### 🗃️ Loaded Datasets")

        collection_rows = []
        for name, item in st.session_state.dataset_collection.items():
            frame = item["dataframe"]
            collection_rows.append(
                {
                    "Dataset": name,
                    "Source": item["source"],
                    "Type": item["detected_type"],
                    "Rows": len(frame),
                    "Columns": len(frame.columns),
                }
            )

        st.dataframe(
            pd.DataFrame(collection_rows),
            use_container_width=True,
            hide_index=True,
        )

        if len(st.session_state.dataset_collection) > 1:
            names = list(st.session_state.dataset_collection.keys())
            current = st.session_state.get("active_dataset")
            index = names.index(current) if current in names else 0
            selected = st.selectbox(
                "Active dataset",
                names,
                index=index,
                key="home_active_dataset_selector",
            )

            if selected != st.session_state.active_dataset:
                item = st.session_state.dataset_collection[selected]
                st.session_state.active_dataset = selected
                st.session_state.active_dataframe = item["dataframe"]
                st.session_state.active_source = item["source"]
                st.session_state.dataset_info = item["info"]
                st.session_state.capture_metadata = item["info"].get("capture_metadata")
                st.session_state.dataset_intelligence = item["intelligence"]
                st.rerun()


    # ============================================================
    # ACTIVE DATASET
    # ============================================================

    if st.session_state.active_dataframe is not None:

        active_df = (
            st.session_state.active_dataframe
        )

        info = st.session_state.dataset_info


        if info is None:

            info = get_dataset_info(
                active_df
            )

            st.session_state.dataset_info = info

        if st.session_state.dataset_intelligence is None:
            st.session_state.dataset_intelligence = build_dataset_intelligence(
                active_df,
                st.session_state.active_dataset,
                st.session_state.active_source,
                info.get("capture_metadata") if info else None,
            )


        st.divider()


        st.html(
            """
            <div class="section-title">
                📌 Active Dataset
            </div>
            """
        )


        st.html(
            f"""
            <div class="active-card">

                <div class="active-title">
                    {st.session_state.active_dataset}
                </div>

                <div class="active-value">
                    <b>Source:</b>
                    {st.session_state.active_source}
                </div>

                <div class="active-value">
                    <b>Rows:</b>
                    {len(active_df):,}
                </div>

                <div class="active-value">
                    <b>Columns:</b>
                    {len(active_df.columns):,}
                </div>

            </div>
            """
        )

        intelligence = st.session_state.dataset_intelligence or {}
        dataset_label = intelligence.get("metadata", {}).get("dataset_type_label", "Dataset")
        st.caption(f"🧠 InsightAI detected this as: **{dataset_label}**")


        # --------------------------------------------------------
        # ACTIVE DATASET METRICS
        # --------------------------------------------------------

        metric_cols = st.columns(6)

        metric_cols[0].metric(
            "Rows",
            f"{info['rows']:,}",
        )

        metric_cols[1].metric(
            "Columns",
            f"{info['columns']:,}",
        )

        metric_cols[2].metric(
            "Missing",
            f"{info['missing_values']:,}",
        )

        metric_cols[3].metric(
            "Duplicates",
            f"{info['duplicate_rows']:,}",
        )

        metric_cols[4].metric(
            "Numeric",
            f"{info['numeric_columns']:,}",
        )

        metric_cols[5].metric(
            "Date / Time",
            f"{info['datetime_columns']:,}",
        )


        st.write("")


        # --------------------------------------------------------
        # OPEN DATA CLEANING
        # --------------------------------------------------------

        if st.button(
            "🧹 Open Data Cleaning",
            type="primary",
            use_container_width=True,
            key="open_data_cleaning",
        ):

            st.switch_page(
                "pages/00_Data_Cleaning.py"
            )


    # ============================================================
    # FOOTER
    # ============================================================

    st.html(
        """
        <div class="footer">

            InsightAI • AI-Powered Data Intelligence Platform

            <br><br>

            Analyze • Understand • Decide

        </div>
        """
    )



# ============================================================
# WORKFLOW NAVIGATION
# ============================================================

WORKFLOW = [
    ("home", "📂", "Select Data", "Home"),
    ("cleaning", "🧹", "Data Cleaning", "pages/00_Data_Cleaning.py"),
    ("explorer", "🔎", "Data Explorer", "pages/01_Data_Explorer.py"),
    ("dashboard", "📊", "Dashboard", "pages/02_Dashboard.py"),
    ("ai", "🤖", "AI Analyst", "pages/03_AI_Analyst.py"),
    ("anomaly", "🚨", "Anomaly Detection", "pages/04_Anomaly_Detection.py"),
    ("forecasting", "🔮", "Forecasting", "pages/05_Forecasting.py"),
    ("network", "🌐", "Network Intelligence", "pages/07_Network_Intelligence.py"),
    ("reports", "📄", "Reports", "pages/06_Reports.py"),
]

if "workflow_completed" not in st.session_state:
    st.session_state.workflow_completed = {
        "home": False,
        "cleaning": False,
        "explorer": False,
        "dashboard": False,
        "ai": False,
        "anomaly": False,
        "forecasting": False,
        "network": False,
        "reports": False,
    }


def _dataset_is_network():
    intelligence = st.session_state.get("dataset_intelligence") or {}
    metadata = intelligence.get("metadata", {}) if isinstance(intelligence, dict) else {}
    label = str(metadata.get("dataset_type_label", "")).lower()
    source = str(st.session_state.get("active_source", "")).lower()
    return any(token in label for token in ("network", "pcap", "capture")) or "pcap" in source or "wireshark" in source


def _unlocked_steps():
    state = st.session_state.workflow_completed
    has_data = st.session_state.get("active_dataframe") is not None
    unlocked = {"home": True}
    unlocked["cleaning"] = has_data
    unlocked["explorer"] = state["cleaning"]
    unlocked["dashboard"] = state["explorer"]
    unlocked["ai"] = state["dashboard"]
    unlocked["anomaly"] = state["ai"]
    unlocked["forecasting"] = state["anomaly"]
    unlocked["network"] = state["forecasting"] and _dataset_is_network()
    unlocked["reports"] = state["forecasting"] and (state["network"] if _dataset_is_network() else True)
    return unlocked


def _render_workflow_sidebar():
    unlocked = _unlocked_steps()
    state = st.session_state.workflow_completed

    with st.sidebar:
        st.html("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">🧠 InsightAI</div>
            <div class="sidebar-brand-subtitle">AI-Powered Data Intelligence</div>
        </div>
        """)
        st.markdown("### Workflow")

        labels = [
            ("home", "📂", "Select Data"),
            ("cleaning", "🧹", "Data Cleaning"),
            ("explorer", "🔎", "Data Explorer"),
            ("dashboard", "📊", "Dashboard"),
            ("ai", "🤖", "AI Analyst"),
            ("anomaly", "🚨", "Anomaly Detection"),
            ("forecasting", "🔮", "Forecasting"),
            ("network", "🌐", "Network Intelligence"),
            ("reports", "📄", "Reports"),
        ]
        for key, icon, label in labels:
            if key == "network" and not _dataset_is_network():
                continue

            # All workflow modules remain available from the sidebar.
            # We keep the existing routing and page registration unchanged;
            # this only removes the lock/disabled state from the UI.
            target_page = PAGE_OBJECTS[key]
            st.page_link(target_page, label=label)

        st.divider()
        done = sum(bool(v) for k, v in state.items() if k != "home")
        total = 7 if _dataset_is_network() else 6
        st.caption(f"Workflow progress: **{done}/{total} completed**")
        if st.session_state.get("active_dataset"):
            st.caption(f"📌 {st.session_state.active_dataset}")


# Define the pages once. st.navigation takes over the pages/ directory.
home_page = st.Page(home_page_content, title="Select Data", icon="📂", url_path="home", default=True)


pages = {
    "Workspace": [home_page],
    "Workflow": [
        st.Page("pages/00_Data_Cleaning.py", title="Data Cleaning", icon="🧹", url_path="cleaning"),
        st.Page("pages/01_Data_Explorer.py", title="Data Explorer", icon="🔎", url_path="explorer"),
        st.Page("pages/02_Dashboard.py", title="Dashboard", icon="📊", url_path="dashboard"),
        st.Page("pages/03_AI_Analyst.py", title="AI Analyst", icon="🤖", url_path="ai-analyst"),
        st.Page("pages/04_Anomaly_Detection.py", title="Anomaly Detection", icon="🚨", url_path="anomaly"),
        st.Page("pages/05_Forecasting.py", title="Forecasting", icon="🔮", url_path="forecasting"),
        st.Page("pages/07_Network_Intelligence.py", title="Network Intelligence", icon="🌐", url_path="network"),
        st.Page("pages/06_Reports.py", title="Reports", icon="📄", url_path="reports"),
    ],
}

# st.navigation must know all pages so custom page links can route to them.
pg = st.navigation(pages, position="hidden")

# Keep the exact registered StreamlitPage objects for sidebar navigation.
# This is especially important for Home: linking to "streamlitapp.py" directly
# causes StreamlitPageNotFoundError because the entrypoint is not a normal page.
PAGE_OBJECTS = {
    "home": home_page,
    "cleaning": pages["Workflow"][0],
    "explorer": pages["Workflow"][1],
    "dashboard": pages["Workflow"][2],
    "ai": pages["Workflow"][3],
    "anomaly": pages["Workflow"][4],
    "forecasting": pages["Workflow"][5],
    "network": pages["Workflow"][6],
    "reports": pages["Workflow"][7],
}

# Render our custom workflow sidebar after the router is registered.
_render_workflow_sidebar()

# Mark the currently selected workflow step as completed once visited.
current_path = getattr(pg, "url_path", "home")
path_to_key = {
    "home": "home",
    "cleaning": "cleaning",
    "explorer": "explorer",
    "dashboard": "dashboard",
    "ai-analyst": "ai",
    "anomaly": "anomaly",
    "forecasting": "forecasting",
    "network": "network",
    "reports": "reports",
}
key = path_to_key.get(current_path)
if key and key != "home":
    # The page was unlocked before navigation, so it is now part of the completed journey.
    st.session_state.workflow_completed[key] = True
elif key == "home" and st.session_state.get("active_dataframe") is not None:
    st.session_state.workflow_completed["home"] = True

pg.run()
