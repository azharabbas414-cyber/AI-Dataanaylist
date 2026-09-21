import streamlit as st
from pathlib import Path
from io import BytesIO
import pandas as pd


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="InsightAI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


# =========================================================
# SESSION STATE
# =========================================================

if "active_dataset" not in st.session_state:
    st.session_state.active_dataset = None

if "active_dataframe" not in st.session_state:
    st.session_state.active_dataframe = None

if "active_source" not in st.session_state:
    st.session_state.active_source = None


# =========================================================
# DATASET DISCOVERY
# =========================================================

def get_repository_datasets():
    if not DATA_DIR.exists():
        return []

    files = []

    for pattern in ["*.csv", "*.xlsx", "*.xls"]:
        files.extend(DATA_DIR.glob(pattern))

    return sorted(files)


repository_datasets = get_repository_datasets()


# =========================================================
# DATA LOADERS
# =========================================================

@st.cache_data
def load_repository_file(file_path):

    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path)

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)

    raise ValueError(
        "Unsupported file format."
    )


@st.cache_data
def load_uploaded_file(
    file_bytes,
    file_name,
):

    suffix = Path(file_name).suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(
            BytesIO(file_bytes)
        )

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(
            BytesIO(file_bytes)
        )

    raise ValueError(
        "Unsupported file format."
    )


# =========================================================
# CUSTOM STYLING
# =========================================================

st.markdown(
    """
<style>

.main {
    padding-top: 1rem;
}

.hero {
    padding: 42px;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        #eef2f7,
        #dfe7ef
    );
    border: 1px solid #cbd5e1;
    margin-bottom: 30px;
}

.hero-small {
    color: #64748b;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 3px;
}

.hero-title {
    font-size: 52px;
    font-weight: 800;
    margin: 10px 0;
    color: #1e293b;
}

.hero-text {
    font-size: 18px;
    color: #64748b;
    max-width: 850px;
}

.dataset-card {
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    min-height: 110px;
    margin-bottom: 15px;
}

.dataset-name {
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
}

.dataset-type {
    color: #64748b;
    font-size: 12px;
    margin-top: 7px;
}

.active-card {
    padding: 20px;
    border-radius: 14px;
    border: 1px solid #bfdbfe;
    background: #eff6ff;
}

.workflow-card {
    padding: 20px;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    min-height: 150px;
}

.workflow-number {
    font-size: 13px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}

.workflow-title {
    font-size: 20px;
    font-weight: 750;
    color: #1e293b;
    margin-top: 8px;
}

.workflow-text {
    font-size: 14px;
    color: #64748b;
    margin-top: 8px;
}

section[data-testid="stSidebar"] {
    background-color: #f8fafc;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

with st.sidebar:

    st.markdown("## ✦ InsightAI")

    st.caption(
        "AI-Powered Data Analytics Platform"
    )

    st.divider()

    st.markdown("### Navigation")

    st.page_link(
        "streamlitapp.py",
        label="🏠 Home",
    )

    st.page_link(
        "pages/00_Data_Cleaning.py",
        label="🧹 Data Cleaning",
    )

    st.page_link(
        "pages/01_Data_Explorer.py",
        label="📊 Data Explorer",
    )

    st.page_link(
        "pages/02_Dashboard.py",
        label="📈 Dashboard",
    )

    st.page_link(
        "pages/03_AI_Analyst.py",
        label="🤖 AI Analyst",
    )

    st.page_link(
        "pages/04_Anomaly_Detection.py",
        label="🚨 Anomaly Detection",
    )

    st.page_link(
        "pages/05_Forecasting.py",
        label="🔮 Forecasting",
    )

    st.page_link(
        "pages/06_Reports.py",
        label="📄 Reports",
    )

    st.divider()

    st.metric(
        "Repository Datasets",
        len(repository_datasets),
    )

    if st.session_state.active_dataset:

        st.success(
            f"Active: "
            f"{st.session_state.active_dataset}"
        )

    else:

        st.caption(
            "No active dataset"
        )


# =========================================================
# HERO
# =========================================================

hero_html = """
<div class="hero">

<div class="hero-small">
INTELLIGENT DATA ANALYTICS
</div>

<div class="hero-title">
InsightAI
</div>

<div class="hero-text">
Transform raw data into interactive analytics,
intelligent insights and decision-ready information.
</div>

</div>
"""

st.markdown(
    hero_html,
    unsafe_allow_html=True,
)


# =========================================================
# WORKFLOW
# =========================================================

st.markdown(
    "## How InsightAI Works"
)

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.markdown(
        """
        <div class="workflow-card">

        <div class="workflow-number">
        01 · SELECT
        </div>

        <div class="workflow-title">
        Choose Data
        </div>

        <div class="workflow-text">
        Select an existing dataset from
        GitHub or upload a new CSV/Excel file.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col2:

    st.markdown(
        """
        <div class="workflow-card">

        <div class="workflow-number">
        02 · CLEAN
        </div>

        <div class="workflow-title">
        Prepare Data
        </div>

        <div class="workflow-text">
        Fix missing values, duplicates,
        data types, text and other quality issues.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col3:

    st.markdown(
        """
        <div class="workflow-card">

        <div class="workflow-number">
        03 · EXPLORE
        </div>

        <div class="workflow-title">
        Understand Data
        </div>

        <div class="workflow-text">
        Explore statistics, relationships,
        distributions, trends and data quality.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col4:

    st.markdown(
        """
        <div class="workflow-card">

        <div class="workflow-number">
        04 · ANALYZE
        </div>

        <div class="workflow-title">
        Discover Insights
        </div>

        <div class="workflow-text">
        Use AI, dashboards, anomaly detection,
        forecasting and professional reports.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


st.divider()


# =========================================================
# DATA SOURCE
# =========================================================

st.markdown(
    "## Choose Your Data Source"
)

existing_tab, upload_tab = st.tabs(
    [
        "📁 Existing GitHub Datasets",
        "⬆️ Upload New Dataset",
    ]
)


# =========================================================
# EXISTING DATASETS
# =========================================================

with existing_tab:

    st.markdown(
        "### Repository Datasets"
    )

    st.caption(
        "These datasets are already stored in "
        "the GitHub `data/` folder."
    )

    if not repository_datasets:

        st.warning(
            "No CSV or Excel datasets were found "
            "in the data folder."
        )

    else:

        dataset_names = [
            file.name
            for file in repository_datasets
        ]

        selected_name = st.selectbox(
            "Select a dataset",
            dataset_names,
            key="repository_dataset_selector",
        )

        selected_file = (
            DATA_DIR / selected_name
        )

        if st.button(
            "📊 Use This Dataset",
            type="primary",
            use_container_width=True,
            key="use_repository_dataset",
        ):

            try:

                dataframe = load_repository_file(
                    selected_file
                )

                st.session_state.active_dataset = (
                    selected_name
                )

                st.session_state.active_dataframe = (
                    dataframe
                )

                st.session_state.active_source = (
                    "GitHub Repository"
                )

                st.success(
                    f"{selected_name} loaded successfully."
                )

            except Exception as error:

                st.error(
                    f"Unable to load dataset: {error}"
                )


# =========================================================
# UPLOAD DATASET
# =========================================================

with upload_tab:

    st.markdown(
        "### Upload a New Dataset"
    )

    st.caption(
        "Use this option when you want to analyze "
        "a dataset that is not stored in GitHub."
    )

    uploaded_file = st.file_uploader(
        "Choose CSV or Excel file",
        type=[
            "csv",
            "xlsx",
            "xls",
        ],
        accept_multiple_files=False,
        key="new_dataset_uploader",
    )

    if uploaded_file is not None:

        try:

            file_bytes = (
                uploaded_file.getvalue()
            )

            dataframe = load_uploaded_file(
                file_bytes,
                uploaded_file.name,
            )

            st.session_state.active_dataset = (
                uploaded_file.name
            )

            st.session_state.active_dataframe = (
                dataframe
            )

            st.session_state.active_source = (
                "Uploaded File"
            )

            st.success(
                f"{uploaded_file.name} loaded successfully."
            )

        except Exception as error:

            st.error(
                f"Unable to read dataset: {error}"
            )


st.divider()


# =========================================================
# ACTIVE DATASET
# =========================================================

st.markdown(
    "## 🎯 Active Dataset"
)


if st.session_state.active_dataframe is not None:

    active_df = (
        st.session_state.active_dataframe
    )

    active_html = f"""
<div class="active-card">

<b>Dataset:</b>
{st.session_state.active_dataset}

<br>

<b>Source:</b>
{st.session_state.active_source}

<br>

<b>Rows:</b>
{len(active_df):,}

<br>

<b>Columns:</b>
{len(active_df.columns):,}

</div>
"""

    st.markdown(
        active_html,
        unsafe_allow_html=True,
    )

    st.write("")

    # -----------------------------------------------------
    # ACTIVE DATASET ACTIONS
    # -----------------------------------------------------

    col_clean, col_explore = st.columns(2)

    with col_clean:

        if st.button(
            "🧹 Open Data Cleaning",
            type="primary",
            use_container_width=True,
            key="open_data_cleaning",
        ):

            st.switch_page(
                "pages/00_Data_Cleaning.py"
            )

    with col_explore:

        if st.button(
            "📊 Open Data Explorer",
            use_container_width=True,
            key="open_data_explorer",
        ):

            st.switch_page(
                "pages/01_Data_Explorer.py"
            )

else:

    st.info(
        "Select an existing dataset or upload "
        "a new dataset to begin analysis."
    )


st.divider()


# =========================================================
# REPOSITORY DATASET SUMMARY
# =========================================================

st.markdown(
    "## 📁 Repository Dataset Summary"
)

if repository_datasets:

    cols = st.columns(3)

    for index, dataset in enumerate(
        repository_datasets
    ):

        with cols[index % 3]:

            size_kb = (
                dataset.stat().st_size
                / 1024
            )

            dataset_html = f"""
<div class="dataset-card">

<div class="dataset-name">
📄 {dataset.stem}
</div>

<div class="dataset-type">
{dataset.suffix.upper()[1:]}
•
{size_kb:.1f} KB
</div>

</div>
"""

            st.markdown(
                dataset_html,
                unsafe_allow_html=True,
            )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "InsightAI • AI-Powered Data Analytics "
    "& Decision Intelligence Platform"
)
