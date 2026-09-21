import pandas as pd
import numpy as np


def get_data_quality(df):
    """Return basic data-quality information."""

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "missing": int(df.isna().sum().sum()),
        "duplicates": int(df.duplicated().sum()),
        "numeric": len(
            df.select_dtypes(include="number").columns
        ),
        "text": len(
            df.select_dtypes(
                include=["object", "category"]
            ).columns
        ),
        "datetime": len(
            df.select_dtypes(
                include=["datetime", "datetimetz"]
            ).columns
        ),
    }


def trim_text_columns(df):
    """Remove leading and trailing spaces from text fields."""

    result = df.copy()

    text_columns = result.select_dtypes(
        include=["object", "string", "category"]
    ).columns

    for column in text_columns:
        result[column] = result[column].apply(
            lambda value:
            value.strip()
            if isinstance(value, str)
            else value
        )

    return result


def standardize_text_case(df, column, case_type):
    """Standardize text capitalization."""

    result = df.copy()

    if column not in result.columns:
        return result

    if case_type == "lower":
        result[column] = result[column].apply(
            lambda value:
            value.lower()
            if isinstance(value, str)
            else value
        )

    elif case_type == "upper":
        result[column] = result[column].apply(
            lambda value:
            value.upper()
            if isinstance(value, str)
            else value
        )

    elif case_type == "title":
        result[column] = result[column].apply(
            lambda value:
            value.title()
            if isinstance(value, str)
            else value
        )

    return result


def fill_missing_values(
    df,
    column,
    method,
    custom_value=None,
):
    """Fill missing values using the selected method."""

    result = df.copy()

    if column not in result.columns:
        return result

    if method == "Mean":

        if pd.api.types.is_numeric_dtype(
            result[column]
        ):
            result[column] = result[column].fillna(
                result[column].mean()
            )

    elif method == "Median":

        if pd.api.types.is_numeric_dtype(
            result[column]
        ):
            result[column] = result[column].fillna(
                result[column].median()
            )

    elif method == "Mode":

        mode = result[column].mode()

        if not mode.empty:
            result[column] = result[column].fillna(
                mode.iloc[0]
            )

    elif method == "Zero":

        result[column] = result[column].fillna(0)

    elif method == "Custom":

        result[column] = result[column].fillna(
            custom_value
        )

    elif method == "Forward Fill":

        result[column] = result[column].ffill()

    elif method == "Backward Fill":

        result[column] = result[column].bfill()

    elif method == "Remove Rows":

        result = result.dropna(
            subset=[column]
        )

    return result


def convert_column_type(
    df,
    column,
    target_type,
):
    """Convert a column to the requested data type."""

    result = df.copy()

    if column not in result.columns:
        return result

    if target_type == "Text":

        result[column] = result[column].astype(
            "string"
        )

    elif target_type == "Integer":

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        ).round().astype("Int64")

    elif target_type == "Decimal":

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    elif target_type == "Date":

        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        ).dt.date

    elif target_type == "DateTime":

        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        )

    elif target_type == "Boolean":

        mapping = {
            "true": True,
            "false": False,
            "yes": True,
            "no": False,
            "1": True,
            "0": False,
        }

        result[column] = (
            result[column]
            .astype(str)
            .str.lower()
            .map(mapping)
        )

    return result


def replace_values(
    df,
    column,
    old_value,
    new_value,
):
    """Replace a specific value in a column."""

    result = df.copy()

    if column not in result.columns:
        return result

    result[column] = result[column].replace(
        old_value,
        new_value,
    )

    return result


def remove_columns(df, columns):
    """Remove selected columns."""

    result = df.copy()

    valid_columns = [
        column
        for column in columns
        if column in result.columns
    ]

    if valid_columns:
        result = result.drop(
            columns=valid_columns
        )

    return result


def rename_column(
    df,
    old_name,
    new_name,
):
    """Rename a column."""

    result = df.copy()

    if old_name not in result.columns:
        return result

    if not new_name.strip():
        return result

    if (
        new_name != old_name
        and new_name in result.columns
    ):
        return result

    result = result.rename(
        columns={
            old_name: new_name.strip()
        }
    )

    return result


def remove_duplicate_rows(df):
    """Remove duplicate records."""

    return df.drop_duplicates().reset_index(
        drop=True
    )


def reset_index(df):
    """Reset dataframe index."""

    return df.reset_index(
        drop=True
    )
