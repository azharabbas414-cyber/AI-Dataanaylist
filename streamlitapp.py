from pathlib import Path

import pandas as pd
import streamlit as st

from core.data_loader import load_dataset, get_dataset_info


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

    /* SIDEBAR */

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128, 128, 128, 0.18);
    }

    .sidebar-brand {
        text-align: center;
        padding: 10px 0 20px 0;
    }

    .sidebar-brand-title {
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    .sidebar-brand-subtitle {
        font-size: 12px;
        opacity: 0.65;
        margin-top: -4px;
    }

    /* HERO */

    .hero {
        padding: 35px 38px;
        border-radius: 20px;
        margin-bottom: 28px;
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
        margin-bottom: 8px;
    }

    .hero-subtitle {
        font-size: 18px;
        opacity: 0.72;
        max-width: 850px;
        line-height: 1.6;
    }

    /* WORKFLOW */

    .workflow-card {
        padding: 22px;
        min-height: 155px;
        border-radius: 16px;
        border: 1px solid rgba(128, 128, 128, 0.18);
        background: rgba(128, 128, 128, 0.035);
    }

    .workflow-icon {
        font-size: 28px;
        margin-bottom: 10px;
    }

    .workflow-title {
        font-size: 18px;
        font-weight: 750;
        margin-bottom: 5px;
    }

    .workflow-text {
        font-size: 13px;
        opacity: 0.68;
        line-height: 1.5;
    }

    /* SECTION */

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

    /* ACTIVE DATASET */

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
        font-size: 20px;
        font-weight: 800;
        margin-bottom: 12px;
    }

    .active-value {
        font-size: 14px;
        margin-bottom: 5px;
    }

    /* INFO */

    .info-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128, 128, 128, 0.16);
        background: rgba(128, 128, 128, 0.035);
        margin: 10px 0;
    }

    /* FOOTER */

    .footer {
        text-align: center;
        padding: 35px 0 10px 0;
        opacity: 0.5;
        font-size: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


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
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">
                🧠 InsightAI
            </div>

            <div class="sidebar-brand-subtitle">
                AI-Powered Data Intelligence
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

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

    if st.session_state.active_dataframe is not None:

        st.markdown("### 📌 Active Dataset")

        st.caption(
            st.session_state.active_dataset
        )

        st.caption(
            f"{len(st.session_state.active_dataframe):,} "
            f"rows × "
            f"{len(st.session_state.active_dataframe.columns):,} "
            f"columns"
        )

    else:

        st.caption(
            "No dataset selected."
        )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">

        <div class="hero-title">
            🧠 InsightAI
        </div>

        <div class="hero-subtitle">
            AI-powered data analytics and decision intelligence
            platform for exploring, cleaning, analyzing,
            forecasting and understanding your data.
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# WORKFLOW
# ============================================================

st.markdown(
    '<div class="section-title">'
    'Your Analytics Workflow'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-subtitle">'
    'From raw data to actionable insights.'
    '</div>',
    unsafe_allow_html=True,
)

workflow_cols = st.columns(4)

workflow = [
    (
        workflow_cols[0],
        "📂",
        "1. Select",
        "Upload your dataset or select a dataset from the repository.",
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

        st.markdown(
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
            """,
            unsafe_allow_html=True,
        )


st.write("")


# ============================================================
# DATA SOURCE
# ============================================================

st.markdown(
    '<div class="section-title">'
    '📂 Select Your Data'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-subtitle">'
    'Upload a supported data file and InsightAI will automatically '
    'detect the format and create a dataset profile.'
    '</div>',
    unsafe_allow_html=True,
)


source_tab1, source_tab2 = st.tabs(
    [
        "📚 Repository Datasets",
        "⬆️ Upload New Dataset",
    ]
)


# ============================================================
# LOCAL REPOSITORY FILE CLASS
# ============================================================

class LocalUploadedFile:

    def __init__(self, path: Path):

        self.name = path.name

        with open(path, "rb") as file:
            self._bytes = file.read()

    def getvalue(self):

        return self._bytes


# ============================================================
# REPOSITORY DATASETS
# ============================================================

with source_tab1:

    data_folder = Path("data")

    if data_folder.exists():

        supported_files = [
            file
            for file in data_folder.iterdir()
            if (
                file.is_file()
                and file.suffix.lower()
                in [
                    ".csv",
                    ".xlsx",
                    ".xls",
                    ".json",
                    ".parquet",
                    ".txt",
                    ".tsv",
                    ".ods",
                    ".pcap",
                    ".pcapng",
                    ".cap",
                ]
            )
        ]

    else:

        supported_files = []


    if not supported_files:

        st.info(
            "No repository datasets were found "
            "in the data folder."
        )

    else:

        st.write(
            f"**{len(supported_files)} datasets available**"
        )

        dataset_options = [
            file.name
            for file in supported_files
        ]

        selected_dataset = st.selectbox(
            "Choose a dataset",
            dataset_options,
            key="repository_dataset_selector",
        )

        selected_path = (
            data_folder / selected_dataset
        )

        if st.button(
            "📂 Load Selected Dataset",
            type="primary",
            use_container_width=True,
            key="load_repository_dataset",
        ):

            try:

                local_file = LocalUploadedFile(
                    selected_path
                )

                with st.spinner(
                    "Loading dataset..."
                ):

                    df, detected_type = load_dataset(
                        local_file
                    )

                    info = get_dataset_info(df)

                st.session_state.active_dataframe = df

                st.session_state.active_dataset = (
                    selected_dataset
                )

                st.session_state.active_source = (
                    f"Repository • {detected_type}"
                )

                st.session_state.dataset_info = info

                st.session_state.capture_metadata = (
                    info.get("capture_metadata")
                )

                st.success(
                    f"✓ {selected_dataset} "
                    "loaded successfully."
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    "Unable to load dataset."
                )

                st.exception(exc)


# ============================================================
# UNIVERSAL FILE UPLOAD
# ============================================================

with source_tab2:

    st.markdown(
        """
        <div class="info-box">

        <b>Universal Dataset Upload</b>

        <br><br>

        InsightAI automatically detects and processes:

        <br><br>

        📄 CSV &nbsp;&nbsp;
        📊 Excel &nbsp;&nbsp;
        🧾 JSON &nbsp;&nbsp;
        🗂️ Parquet &nbsp;&nbsp;
        📝 TXT / TSV &nbsp;&nbsp;
        📑 ODS

        <br><br>

        🌐 <b>Wireshark:</b>
        PCAP / PCAPNG / CAP

        <br><br>

        After upload, InsightAI automatically creates a
        standardized dataset for analysis.

        </div>
        """,
        unsafe_allow_html=True,
    )


    uploaded_file = st.file_uploader(
        "Choose a dataset or Wireshark capture",
        type=SUPPORTED_UPLOAD_TYPES,
        key="universal_dataset_upload",
    )


    if uploaded_file is not None:

        file_size_mb = (
            uploaded_file.size
            / (1024 * 1024)
        )

        st.caption(
            f"File: **{uploaded_file.name}**  |  "
            f"Size: **{file_size_mb:.2f} MB**"
        )

        try:

            with st.spinner(
                "Detecting file type and loading data..."
            ):

                df, detected_type = load_dataset(
                    uploaded_file
                )

                info = get_dataset_info(df)


            # ------------------------------------------------
            # SAVE ACTIVE DATASET
            # ------------------------------------------------

            st.session_state.active_dataframe = df

            st.session_state.active_dataset = (
                uploaded_file.name
            )

            st.session_state.active_source = (
                f"Uploaded File • {detected_type}"
            )

            st.session_state.dataset_info = info

            st.session_state.capture_metadata = (
                info.get("capture_metadata")
            )


            # ------------------------------------------------
            # SUCCESS MESSAGE
            # ------------------------------------------------

            st.success(
                f"✓ **{detected_type}** detected "
                "and loaded successfully."
            )


            # ------------------------------------------------
            # WIRESHARK INFORMATION
            # ------------------------------------------------

            if (
                detected_type.startswith(
                    "Wireshark"
                )
                and info.get(
                    "capture_metadata"
                )
            ):

                capture = info[
                    "capture_metadata"
                ]

                st.markdown(
                    "### 🌐 Wireshark Capture Summary"
                )

                wc1, wc2, wc3, wc4 = st.columns(4)

                wc1.metric(
                    "Packets Loaded",
                    f"{capture['packets_loaded']:,}",
                )

                wc2.metric(
                    "Total Bytes",
                    f"{capture['total_bytes']:,}",
                )

                wc3.metric(
                    "Duration",
                    f"{capture['duration_seconds']:.2f} sec",
                )

                wc4.metric(
                    "Packets / Sec",
                    f"{capture['packets_per_second']:,.2f}",
                )


                bytes_per_second = capture[
                    "bytes_per_second"
                ]

                st.info(
                    f"Average throughput: "
                    f"**{bytes_per_second / (1024 * 1024):,.2f} MB/s**"
                )


                if (
                    capture["packets_loaded"]
                    >= capture["max_packets"]
                ):

                    st.warning(
                        f"The capture contains more packets "
                        f"than the current processing limit of "
                        f"{capture['max_packets']:,}. "
                        "Only the first packets were loaded "
                        "into the analytics engine."
                    )


            # ------------------------------------------------
            # DATASET SUMMARY
            # ------------------------------------------------

            st.markdown(
                "### 📊 Dataset Summary"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Rows",
                f"{info['rows']:,}",
            )

            c2.metric(
                "Columns",
                f"{info['columns']:,}",
            )

            c3.metric(
                "Missing Values",
                f"{info['missing_values']:,}",
            )

            c4.metric(
                "Duplicate Rows",
                f"{info['duplicate_rows']:,}",
            )


            # ------------------------------------------------
            # AUTOMATIC DATA TYPE DETECTION
            # ------------------------------------------------

            st.markdown(
                "### 🔍 Automatically Detected Data Types"
            )

            type_cols = st.columns(5)

            type_cols[0].metric(
                "🔢 Numeric",
                len(
                    info["column_types"][
                        "numeric"
                    ]
                ),
            )

            type_cols[1].metric(
                "🔤 Categorical",
                len(
                    info["column_types"][
                        "categorical"
                    ]
                ),
            )

            type_cols[2].metric(
                "📅 Date / Time",
                len(
                    info["column_types"][
                        "datetime"
                    ]
                ),
            )

            type_cols[3].metric(
                "🔘 Boolean",
                len(
                    info["column_types"][
                        "boolean"
                    ]
                ),
            )

            type_cols[4].metric(
                "📝 Text",
                len(
                    info["column_types"][
                        "text"
                    ]
                ),
            )


            # ------------------------------------------------
            # COLUMN CLASSIFICATION
            # ------------------------------------------------

            with st.expander(
                "🔍 View detected column classifications"
            ):

                detected_types_df = pd.DataFrame(
                    {
                        "Data Type": [
                            "Numeric",
                            "Categorical",
                            "Date / Time",
                            "Boolean",
                            "Text",
                        ],

                        "Columns": [
                            ", ".join(
                                map(
                                    str,
                                    info[
                                        "column_types"
                                    ][
                                        "numeric"
                                    ],
                                )
                            ),

                            ", ".join(
                                map(
                                    str,
                                    info[
                                        "column_types"
                                    ][
                                        "categorical"
                                    ],
                                )
                            ),

                            ", ".join(
                                map(
                                    str,
                                    info[
                                        "column_types"
                                    ][
                                        "datetime"
                                    ],
                                )
                            ),

                            ", ".join(
                                map(
                                    str,
                                    info[
                                        "column_types"
                                    ][
                                        "boolean"
                                    ],
                                )
                            ),

                            ", ".join(
                                map(
                                    str,
                                    info[
                                        "column_types"
                                    ][
                                        "text"
                                    ],
                                )
                            ),
                        ],
                    }
                )

                st.dataframe(
                    detected_types_df,
                    use_container_width=True,
                    hide_index=True,
                )


            # ------------------------------------------------
            # DATA PREVIEW
            # ------------------------------------------------

            st.markdown(
                "### 👀 Data Preview"
            )

            st.dataframe(
                df.head(10),
                use_container_width=True,
                height=350,
            )


        except Exception as exc:

            st.error(
                "❌ Unable to load this file."
            )

            st.exception(exc)


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


    st.divider()


    st.markdown(
        '<div class="section-title">'
        '📌 Active Dataset'
        '</div>',
        unsafe_allow_html=True,
    )


    st.markdown(
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
        """,
        unsafe_allow_html=True,
    )


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
# REPOSITORY DATASET SUMMARY
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">'
    '📚 Repository Datasets'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-subtitle">'
    'Datasets currently available inside the InsightAI repository.'
    '</div>',
    unsafe_allow_html=True,
)


if supported_files:

    summary_data = []


    for file in supported_files:

        try:

            local_file = LocalUploadedFile(
                file
            )

            temp_df, temp_type = (
                load_dataset(
                    local_file
                )
            )

            summary_data.append(
                {
                    "Dataset": file.name,
                    "Type": temp_type,
                    "Rows": len(temp_df),
                    "Columns": len(
                        temp_df.columns
                    ),
                }
            )

        except Exception as exc:

            summary_data.append(
                {
                    "Dataset": file.name,
                    "Type": "Unable to read",
                    "Rows": "-",
                    "Columns": "-",
                }
            )


    summary_df = pd.DataFrame(
        summary_data
    )


    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No repository datasets available."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">

        InsightAI • AI-Powered Data Intelligence Platform

        <br>

        Analyze • Understand • Decide

    </div>
    """,
    unsafe_allow_html=True,
)
