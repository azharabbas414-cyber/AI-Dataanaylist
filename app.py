
import streamlit as st
import pandas as pd
import os
from google import genai

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide"
)

# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------

st.title("📊 AI Data Analyst Assistant")
st.write(
    "Upload a CSV or Excel file and use AI to explore, "
    "analyze and visualize your data."
)

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Settings")

    st.info(
        "Upload a dataset and then ask questions about "
        "your data using the AI assistant."
    )

    st.markdown("---")
    st.write("Supported files:")
    st.write("• CSV")
    st.write("• XLSX")
    st.write("• XLS")

# ---------------------------------------------------------
# GEMINI CLIENT
# ---------------------------------------------------------

api_key = None

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

client = None

if api_key:
    client = genai.Client(api_key=api_key)

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------

uploaded_file = st.file_uploader(
    "📁 Upload your dataset",
    type=["csv", "xlsx", "xls"]
)

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

if uploaded_file is not None:

    try:

        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)

        else:
            df = pd.read_excel(uploaded_file)

        st.success(
            f"Successfully loaded: {uploaded_file.name}"
        )

        # -------------------------------------------------
        # DATASET OVERVIEW
        # -------------------------------------------------

        st.header("📋 Dataset Overview")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Rows", df.shape[0])

        with col2:
            st.metric("Columns", df.shape[1])

        with col3:
            st.metric(
                "Missing Values",
                int(df.isna().sum().sum())
            )

        with col4:
            st.metric(
                "Duplicate Rows",
                int(df.duplicated().sum())
            )

        # -------------------------------------------------
        # DATA PREVIEW
        # -------------------------------------------------

        st.header("👀 Data Preview")

        st.dataframe(
            df.head(100),
            use_container_width=True
        )

        # -------------------------------------------------
        # COLUMN INFORMATION
        # -------------------------------------------------

        st.header("🔍 Column Information")

        column_info = pd.DataFrame({
            "Column": df.columns,
            "Data Type": df.dtypes.astype(str).values,
            "Missing Values": df.isna().sum().values,
            "Unique Values": [
                df[column].nunique()
                for column in df.columns
            ]
        })

        st.dataframe(
            column_info,
            use_container_width=True
        )

        # -------------------------------------------------
        # STATISTICS
        # -------------------------------------------------

        st.header("📈 Statistical Summary")

        numeric_columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

        if numeric_columns:

            st.dataframe(
                df[numeric_columns].describe().T,
                use_container_width=True
            )

        else:

            st.info(
                "No numeric columns were found."
            )

        # -------------------------------------------------
        # MISSING VALUES
        # -------------------------------------------------

        st.header("⚠️ Missing Values")

        missing = df.isna().sum()
        missing = missing[missing > 0]

        if len(missing) > 0:

            missing_df = pd.DataFrame({
                "Column": missing.index,
                "Missing Values": missing.values
            })

            st.dataframe(
                missing_df,
                use_container_width=True
            )

        else:

            st.success(
                "No missing values found."
            )

        # -------------------------------------------------
        # VISUALIZATION
        # -------------------------------------------------

        st.header("📊 Visualization")

        chart_type = st.selectbox(
            "Choose chart type",
            [
                "Bar Chart",
                "Line Chart",
                "Histogram"
            ]
        )

        if numeric_columns:

            selected_column = st.selectbox(
                "Select numeric column",
                numeric_columns
            )

            if chart_type == "Bar Chart":

                st.bar_chart(
                    df[selected_column]
                )

            elif chart_type == "Line Chart":

                st.line_chart(
                    df[selected_column]
                )

            elif chart_type == "Histogram":

                histogram_data = (
                    df[selected_column]
                    .dropna()
                    .value_counts()
                    .sort_index()
                )

                st.bar_chart(
                    histogram_data
                )

        else:

            st.warning(
                "Charts require numeric data."
            )

        # -------------------------------------------------
        # AI DATA ANALYST
        # -------------------------------------------------

        st.header("🤖 Ask the AI Data Analyst")

        question = st.text_area(
            "Ask a question about your dataset",
            placeholder=(
                "Example: Which column has the highest average value?"
            )
        )

        if st.button("🔎 Analyze Data"):

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            elif client is None:

                st.error(
                    "Gemini API key is not configured."
                )

                st.info(
                    "Add GEMINI_API_KEY to Streamlit Secrets."
                )

            else:

                # Create a compact dataset description
                dataset_info = f"""
Dataset name: {uploaded_file.name}

Rows: {df.shape[0]}
Columns: {df.shape[1]}

Columns and data types:
{df.dtypes.to_string()}

Statistical summary:
{df.describe(include="all").to_string()}

First 20 rows:
{df.head(20).to_string()}
"""

                prompt = f"""
You are an expert data analyst.

Analyze the following dataset information.

{dataset_info}

User question:
{question}

Provide:
1. A clear answer.
2. Important observations.
3. Any assumptions or limitations.
4. If useful, provide Python/Pandas code.

Do not invent values that are not present in the supplied dataset information.
"""

                with st.spinner(
                    "🤖 AI is analyzing your data..."
                ):

                    try:

                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )

                        st.subheader(
                            "🤖 AI Analysis"
                        )

                        st.write(
                            response.text
                        )

                    except Exception as e:

                        st.error(
                            f"AI request failed: {e}"
                        )

    except Exception as e:

        st.error(
            f"Could not read the file: {e}"
        )

else:

    st.info(
        "👆 Upload a CSV or Excel file to get started."
    )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.markdown("---")

st.caption(
    "AI Data Analyst Assistant • Built with Python + Streamlit + Gemini"
)
