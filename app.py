import streamlit as st
import pandas as pd
import os
import time
import random
from google import genai


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Data Analyst Assistant",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("📊 AI Data Analyst Assistant")

st.write(
    "Upload your CSV or Excel dataset and analyze it using "
    "Pandas and Gemini AI."
)


# ============================================================
# GEMINI API CONFIGURATION
# ============================================================

api_key = None

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")


client = None

if api_key:
    client = genai.Client(api_key=api_key)


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload your dataset",
    type=["csv", "xlsx", "xls"]
)


# ============================================================
# FUNCTION: LOAD DATASET
# ============================================================

def load_data(file):

    try:

        if file.name.lower().endswith(".csv"):

            df = pd.read_csv(file)

        elif file.name.lower().endswith(".xlsx"):

            df = pd.read_excel(file, engine="openpyxl")

        elif file.name.lower().endswith(".xls"):

            df = pd.read_excel(file, engine="xlrd")

        else:

            st.error("Unsupported file format.")
            return None

        return df

    except Exception as e:

        st.error(f"Error loading file: {e}")

        return None


# ============================================================
# FUNCTION: GEMINI REQUEST WITH RETRY + FALLBACK
# ============================================================

def ask_gemini(prompt):

    if client is None:

        st.error("Gemini API key is not configured.")

        st.info(
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )

        return None


    # Primary and fallback models
    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash"
    ]


    # Number of retries for each model
    max_retries = 3


    last_error = None


    # --------------------------------------------------------
    # Try each model
    # --------------------------------------------------------

    for model in models:

        for attempt in range(max_retries):

            try:

                # Show retry information only when needed
                if attempt > 0:

                    st.info(
                        f"Retrying {model} "
                        f"(attempt {attempt + 1}/{max_retries})..."
                    )


                response = client.models.generate_content(

                    model=model,

                    contents=prompt
                )


                # Successful response
                if response and response.text:

                    return response.text


            except Exception as e:

                last_error = e

                error_text = str(e)


                # ------------------------------------------------
                # 503 - MODEL TEMPORARILY UNAVAILABLE
                # ------------------------------------------------

                if "503" in error_text or "UNAVAILABLE" in error_text:

                    if attempt < max_retries - 1:

                        # Exponential backoff:
                        # 2s, 4s, 8s
                        wait_time = (2 ** attempt) + random.uniform(
                            0.5,
                            1.5
                        )

                        st.warning(
                            f"{model} is temporarily busy. "
                            f"Retrying in {wait_time:.1f} seconds..."
                        )

                        time.sleep(wait_time)

                        continue

                    else:

                        st.warning(
                            f"{model} is still unavailable. "
                            f"Trying the fallback model..."
                        )

                        break


                # ------------------------------------------------
                # 429 - RATE LIMIT / QUOTA
                # ------------------------------------------------

                elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:

                    if attempt < max_retries - 1:

                        wait_time = (2 ** attempt) + random.uniform(
                            0.5,
                            1.5
                        )

                        st.warning(
                            f"Gemini rate limit reached. "
                            f"Retrying in {wait_time:.1f} seconds..."
                        )

                        time.sleep(wait_time)

                        continue

                    else:

                        st.warning(
                            f"{model} rate limit reached. "
                            f"Trying the fallback model..."
                        )

                        break


                # ------------------------------------------------
                # OTHER ERRORS
                # ------------------------------------------------

                else:

                    st.error(
                        f"Gemini request failed:\n\n{error_text}"
                    )

                    return None


    # ========================================================
    # ALL MODELS FAILED
    # ========================================================

    st.error(
        "Gemini is currently unavailable.\n\n"
        "Both Gemini models were tried with automatic retries."
    )

    if last_error:

        st.info(
            "Please wait a little and try the question again."
        )

    return None


# ============================================================
# PROCESS DATASET
# ============================================================

if uploaded_file is not None:

    df = load_data(uploaded_file)


    if df is not None:

        st.success(
            f"Dataset loaded successfully: {uploaded_file.name}"
        )


        # ====================================================
        # DATASET OVERVIEW
        # ====================================================

        st.header("📋 Dataset Overview")


        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "Rows",
                df.shape[0]
            )


        with col2:

            st.metric(
                "Columns",
                df.shape[1]
            )


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


        # ====================================================
        # DATA PREVIEW
        # ====================================================

        st.header("👀 Data Preview")

        st.dataframe(
            df.head(20),
            use_container_width=True
        )


        # ====================================================
        # COLUMN INFORMATION
        # ====================================================

        st.header("📌 Column Information")


        column_info = pd.DataFrame({

            "Column": df.columns,

            "Data Type": [
                str(dtype)
                for dtype in df.dtypes
            ],

            "Missing Values": [
                int(df[col].isna().sum())
                for col in df.columns
            ],

            "Unique Values": [
                int(df[col].nunique())
                for col in df.columns
            ]

        })


        st.dataframe(
            column_info,
            use_container_width=True
        )


        # ====================================================
        # STATISTICAL SUMMARY
        # ====================================================

        st.header("📊 Statistical Summary")


        numeric_columns = df.select_dtypes(
            include="number"
        ).columns


        if len(numeric_columns) > 0:

            st.dataframe(
                df[numeric_columns].describe(),
                use_container_width=True
            )

        else:

            st.info(
                "No numeric columns found."
            )


        # ====================================================
        # MISSING VALUES
        # ====================================================

        st.header("🔍 Missing Values")


        missing = df.isna().sum()

        missing = missing[
            missing > 0
        ]


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


        # ====================================================
        # BASIC VISUALIZATION
        # ====================================================

        st.header("📈 Basic Visualization")


        numeric_cols = list(
            df.select_dtypes(
                include="number"
            ).columns
        )


        if numeric_cols:

            selected_column = st.selectbox(
                "Select numeric column",
                numeric_cols
            )


            chart_type = st.selectbox(
                "Select chart type",
                [
                    "Bar Chart",
                    "Line Chart",
                    "Histogram"
                ]
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

                st.bar_chart(
                    df[selected_column]
                    .value_counts()
                    .sort_index()
                )


        else:

            st.info(
                "No numeric columns available for visualization."
            )


        # ====================================================
        # AI DATA ANALYST
        # ====================================================

        st.header("🤖 Ask AI About Your Data")


        question = st.text_area(
            "Ask a question about the uploaded dataset",
            placeholder=(
                "Example: Which customer has the highest sales?"
            )
        )


        analyze_button = st.button(
            "🔎 Analyze with Gemini"
        )


        # ====================================================
        # AI ANALYSIS
        # ====================================================

        if analyze_button:

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            else:

                # --------------------------------------------
                # Prepare dataset information
                # --------------------------------------------

                dataset_info = {

                    "rows": df.shape[0],

                    "columns": list(df.columns),

                    "data_types":
                        df.dtypes.astype(str).to_dict(),

                    "missing_values":
                        df.isna().sum().to_dict(),

                    "numeric_summary":
                        df.describe(
                            include="number"
                        ).to_dict()

                }


                # --------------------------------------------
                # Sample data
                # --------------------------------------------

                sample_data = df.head(20).to_string(
                    index=False
                )


                # --------------------------------------------
                # AI PROMPT
                # --------------------------------------------

                prompt = f"""
You are an expert Data Analyst.

The user uploaded a dataset to a Streamlit application.

Answer the user's question using the dataset information
provided below.

Be accurate and concise.

If the requested calculation cannot be reliably determined
from the supplied information, clearly say so.

Do not invent data.

DATASET INFORMATION:

Rows:
{dataset_info["rows"]}

Columns:
{dataset_info["columns"]}

Data Types:
{dataset_info["data_types"]}

Missing Values:
{dataset_info["missing_values"]}

Numeric Summary:
{dataset_info["numeric_summary"]}

SAMPLE DATA:

{sample_data}

USER QUESTION:

{question}

Provide a clear answer and explain the calculation or reasoning
when appropriate.
"""


                # --------------------------------------------
                # Call Gemini
                # --------------------------------------------

                with st.spinner(
                    "Gemini is analyzing your data..."
                ):

                    answer = ask_gemini(
                        prompt
                    )


                # --------------------------------------------
                # Display result
                # --------------------------------------------

                if answer:

                    st.subheader(
                        "🤖 AI Analysis"
                    )

                    st.write(
                        answer
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "AI Data Analyst Assistant • "
    "Built with Streamlit + Pandas + Gemini"
)

