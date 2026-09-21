import streamlit as st
import pandas as pd

from core.cleaning import (
    get_data_quality,
    trim_text_columns,
    standardize_text_case,
    fill_missing_values,
    convert_column_type,
    replace_values,
    remove_columns,
    rename_column,
    remove_duplicate_rows,
)


st.set_page_config(
    page_title="InsightAI - Data Cleaning",
    page_icon="🧹",
    layout="wide",
)


# ---------------------------------------------------------
# ACTIVE DATASET CHECK
# ---------------------------------------------------------

if (
    "active_dataframe" not in st.session_state
    or st.session_state.active_dataframe is None
):

    st.warning(
        "No active dataset is selected."
    )

    st.info(
        "Return to Home and select an existing "
        "GitHub dataset or upload a new dataset."
    )

    if st.button("🏠 Go to Home"):
        st.switch_page("streamlitapp.py")

    st.stop()


# ---------------------------------------------------------
# INITIALIZE CLEANING SESSION
# ---------------------------------------------------------

current_dataset = st.session_state.get(
    "active_dataset",
    "Dataset"
)

if (
    "cleaning_dataset_name"
    not in st.session_state
    or st.session_state.cleaning_dataset_name
    != current_dataset
):

    st.session_state.cleaning_dataset_name = (
        current_dataset
    )

    st.session_state.original_dataframe = (
        st.session_state.active_dataframe.copy()
    )

    st.session_state.cleaned_dataframe = (
        st.session_state.active_dataframe.copy()
    )

    st.session_state.cleaning_history = []


working_df = st.session_state.cleaned_dataframe


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🧹 Data Cleaning")

st.caption(
    "Clean, standardize and prepare your dataset "
    "before analysis."
)

st.info(
    f"**Dataset:** {current_dataset}"
)


# ---------------------------------------------------------
# QUALITY METRICS
# ---------------------------------------------------------

quality = get_data_quality(
    working_df
)

original_df = (
    st.session_state.original_dataframe
)

original_quality = get_data_quality(
    original_df
)


col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric(
        "Rows",
        f"{quality['rows']:,}",
        delta=(
            quality["rows"]
            - original_quality["rows"]
        ),
    )

with col2:
    st.metric(
        "Columns",
        f"{quality['columns']:,}",
        delta=(
            quality["columns"]
            - original_quality["columns"]
        ),
    )

with col3:
    st.metric(
        "Missing",
        f"{quality['missing']:,}",
        delta=(
            quality["missing"]
            - original_quality["missing"]
        ),
    )

with col4:
    st.metric(
        "Duplicates",
        f"{quality['duplicates']:,}",
        delta=(
            quality["duplicates"]
            - original_quality["duplicates"]
        ),
    )

with col5:
    st.metric(
        "Numeric",
        f"{quality['numeric']:,}",
    )

with col6:
    st.metric(
        "Text",
        f"{quality['text']:,}",
    )


st.divider()


# ---------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------

action_col1, action_col2, action_col3 = st.columns(3)

with action_col1:

    if st.button(
        "↩️ Reset All Changes",
        use_container_width=True,
    ):

        st.session_state.cleaned_dataframe = (
            st.session_state.original_dataframe.copy()
        )

        st.session_state.active_dataframe = (
            st.session_state.original_dataframe.copy()
        )

        st.session_state.cleaning_history = []

        st.success(
            "All cleaning changes have been reset."
        )

        st.rerun()


with action_col2:

    if st.button(
        "💾 Apply Cleaned Dataset",
        type="primary",
        use_container_width=True,
    ):

        st.session_state.active_dataframe = (
            st.session_state.cleaned_dataframe.copy()
        )

        st.success(
            "Cleaned dataset is now the active dataset."
        )


with action_col3:

    csv_data = working_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Cleaned CSV",
        data=csv_data,
        file_name="insightai_cleaned_dataset.csv",
        mime="text/csv",
        use_container_width=True,
    )


st.divider()


# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------

tab_quality, tab_missing, tab_duplicates, tab_text, tab_columns, tab_types, tab_replace, tab_history = st.tabs(
    [
        "🔍 Quality",
        "❓ Missing Values",
        "📑 Duplicates",
        "🔤 Text Cleaning",
        "📋 Columns",
        "🔢 Data Types",
        "🔄 Replace Values",
        "📝 History",
    ]
)


# =========================================================
# QUALITY
# =========================================================

with tab_quality:

    st.subheader(
        "🔍 Data Quality Overview"
    )

    quality_table = pd.DataFrame(
        {
            "Metric": [
                "Rows",
                "Columns",
                "Missing Values",
                "Duplicate Rows",
                "Numeric Columns",
                "Text Columns",
                "Date/Time Columns",
            ],
            "Current": [
                quality["rows"],
                quality["columns"],
                quality["missing"],
                quality["duplicates"],
                quality["numeric"],
                quality["text"],
                quality["datetime"],
            ],
            "Original": [
                original_quality["rows"],
                original_quality["columns"],
                original_quality["missing"],
                original_quality["duplicates"],
                original_quality["numeric"],
                original_quality["text"],
                original_quality["datetime"],
            ],
        }
    )

    st.dataframe(
        quality_table,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Column Quality"
    )

    column_quality = pd.DataFrame(
        {
            "Column": working_df.columns,
            "Data Type": [
                str(working_df[column].dtype)
                for column in working_df.columns
            ],
            "Missing": [
                int(
                    working_df[column].isna().sum()
                )
                for column in working_df.columns
            ],
            "Missing %": [
                round(
                    working_df[column]
                    .isna()
                    .mean()
                    * 100,
                    2,
                )
                for column in working_df.columns
            ],
            "Unique": [
                int(
                    working_df[column]
                    .nunique(
                        dropna=True
                    )
                )
                for column in working_df.columns
            ],
        }
    )

    st.dataframe(
        column_quality,
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# MISSING VALUES
# =========================================================

with tab_missing:

    st.subheader(
        "❓ Missing Value Treatment"
    )

    missing_columns = [
        column
        for column in working_df.columns
        if working_df[column].isna().any()
    ]

    if not missing_columns:

        st.success(
            "✅ No missing values detected."
        )

    else:

        st.warning(
            f"{quality['missing']:,} missing values "
            "are currently present."
        )

        selected_column = st.selectbox(
            "Select column",
            missing_columns,
            key="missing_column",
        )

        missing_count = int(
            working_df[selected_column]
            .isna()
            .sum()
        )

        st.write(
            f"**Missing values:** {missing_count:,}"
        )

        method = st.selectbox(
            "Treatment",
            [
                "Mean",
                "Median",
                "Mode",
                "Zero",
                "Custom",
                "Forward Fill",
                "Backward Fill",
                "Remove Rows",
            ],
            key="missing_method",
        )

        custom_value = None

        if method == "Custom":

            custom_value = st.text_input(
                "Replacement value",
                key="custom_missing_value",
            )

        if st.button(
            "Apply Missing Value Treatment",
            type="primary",
        ):

            new_df = fill_missing_values(
                working_df,
                selected_column,
                method,
                custom_value,
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                f"Applied '{method}' to missing values in '{selected_column}'."
            )

            st.success(
                "Missing value treatment applied."
            )

            st.rerun()


# =========================================================
# DUPLICATES
# =========================================================

with tab_duplicates:

    st.subheader(
        "📑 Duplicate Records"
    )

    duplicate_count = int(
        working_df.duplicated().sum()
    )

    if duplicate_count == 0:

        st.success(
            "✅ No duplicate rows detected."
        )

    else:

        st.warning(
            f"{duplicate_count:,} duplicate rows detected."
        )

        if st.button(
            "🗑️ Remove Duplicate Rows",
            type="primary",
        ):

            new_df = remove_duplicate_rows(
                working_df
            )

            removed = (
                len(working_df)
                - len(new_df)
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                f"Removed {removed:,} duplicate rows."
            )

            st.success(
                f"Removed {removed:,} duplicate rows."
            )

            st.rerun()


# =========================================================
# TEXT CLEANING
# =========================================================

with tab_text:

    st.subheader(
        "🔤 Text Standardization"
    )

    text_columns = list(
        working_df.select_dtypes(
            include=[
                "object",
                "string",
                "category",
            ]
        ).columns
    )

    if not text_columns:

        st.info(
            "No text columns were detected."
        )

    else:

        text_column = st.selectbox(
            "Select text column",
            text_columns,
            key="text_column",
        )

        st.markdown(
            "### Remove Whitespace"
        )

        if st.button(
            "✂️ Trim Leading / Trailing Spaces",
        ):

            new_df = trim_text_columns(
                working_df
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                "Trimmed whitespace from text columns."
            )

            st.success(
                "Whitespace cleaned."
            )

            st.rerun()

        st.markdown(
            "### Standardize Case"
        )

        case_type = st.selectbox(
            "Case",
            [
                "lower",
                "upper",
                "title",
            ],
            key="case_type",
        )

        if st.button(
            "🔤 Apply Text Case",
        ):

            new_df = standardize_text_case(
                working_df,
                text_column,
                case_type,
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                f"Converted '{text_column}' to {case_type} case."
            )

            st.success(
                "Text formatting applied."
            )

            st.rerun()


# =========================================================
# COLUMNS
# =========================================================

with tab_columns:

    st.subheader(
        "📋 Column Management"
    )

    columns = list(
        working_df.columns
    )

    column_to_rename = st.selectbox(
        "Column to rename",
        columns,
        key="rename_column",
    )

    new_name = st.text_input(
        "New column name",
        value=column_to_rename,
        key="new_column_name",
    )

    if st.button(
        "✏️ Rename Column",
    ):

        new_df = rename_column(
            working_df,
            column_to_rename,
            new_name,
        )

        if list(new_df.columns) != list(
            working_df.columns
        ):

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                f"Renamed '{column_to_rename}' to '{new_name}'."
            )

            st.success(
                "Column renamed."
            )

            st.rerun()

        else:

            st.warning(
                "Column name was not changed."
            )

    st.divider()

    st.markdown(
        "### Remove Columns"
    )

    columns_to_remove = st.multiselect(
        "Select columns to remove",
        columns,
        key="columns_to_remove",
    )

    if st.button(
        "🗑️ Remove Selected Columns",
    ):

        if not columns_to_remove:

            st.warning(
                "Select at least one column."
            )

        else:

            new_df = remove_columns(
                working_df,
                columns_to_remove,
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                "Removed columns: "
                + ", ".join(columns_to_remove)
            )

            st.success(
                "Selected columns removed."
            )

            st.rerun()


# =========================================================
# DATA TYPES
# =========================================================

with tab_types:

    st.subheader(
        "🔢 Data Type Conversion"
    )

    selected_type_column = st.selectbox(
        "Select column",
        list(working_df.columns),
        key="type_column",
    )

    target_type = st.selectbox(
        "Convert to",
        [
            "Text",
            "Integer",
            "Decimal",
            "Date",
            "DateTime",
            "Boolean",
        ],
        key="target_type",
    )

    if st.button(
        "🔄 Convert Data Type",
        type="primary",
    ):

        new_df = convert_column_type(
            working_df,
            selected_type_column,
            target_type,
        )

        st.session_state.cleaned_dataframe = (
            new_df
        )

        st.session_state.cleaning_history.append(
            f"Converted '{selected_type_column}' to {target_type}."
        )

        st.success(
            "Data type converted."
        )

        st.rerun()


# =========================================================
# REPLACE VALUES
# =========================================================

with tab_replace:

    st.subheader(
        "🔄 Replace Values"
    )

    replace_column = st.selectbox(
        "Column",
        list(working_df.columns),
        key="replace_column",
    )

    old_value = st.text_input(
        "Value to replace",
        key="old_value",
    )

    new_value = st.text_input(
        "New value",
        key="new_value",
    )

    if st.button(
        "🔄 Replace Value",
    ):

        if old_value == "":

            st.warning(
                "Enter the value to replace."
            )

        else:

            new_df = replace_values(
                working_df,
                replace_column,
                old_value,
                new_value,
            )

            st.session_state.cleaned_dataframe = (
                new_df
            )

            st.session_state.cleaning_history.append(
                f"Replaced '{old_value}' with '{new_value}' in '{replace_column}'."
            )

            st.success(
                "Value replacement completed."
            )

            st.rerun()


# =========================================================
# HISTORY
# =========================================================

with tab_history:

    st.subheader(
        "📝 Cleaning History"
    )

    history = st.session_state.get(
        "cleaning_history",
        [],
    )

    if not history:

        st.info(
            "No cleaning operations have been performed."
        )

    else:

        for index, operation in enumerate(
            history,
            start=1,
        ):

            st.write(
                f"**{index}.** {operation}"
            )


st.divider()


# ---------------------------------------------------------
# DATA PREVIEW
# ---------------------------------------------------------

st.subheader(
    "👁️ Current Cleaned Dataset Preview"
)

st.dataframe(
    working_df.head(100),
    use_container_width=True,
    height=450,
)


st.divider()

st.caption(
    f"InsightAI • Data Cleaning • {current_dataset}"
)
