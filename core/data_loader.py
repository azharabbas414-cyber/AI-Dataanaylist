# core/data_loader.py

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {
    ".csv": "CSV",
    ".xlsx": "Excel",
    ".xls": "Excel",
    ".json": "JSON",
    ".parquet": "Parquet",
    ".txt": "Text",
    ".tsv": "TSV",
    ".ods": "OpenDocument Spreadsheet",
}


def detect_file_type(filename: str) -> str:
    """
    Detect file type from filename extension.
    """
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension or 'unknown'}"
        )

    return SUPPORTED_EXTENSIONS[extension]


def _read_csv_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Automatically detect common CSV delimiters and encoding.
    """

    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]

    last_error = None

    for encoding in encodings:
        try:
            text = file_bytes.decode(encoding)

            # Let pandas detect the separator.
            return pd.read_csv(
                io.StringIO(text),
                sep=None,
                engine="python",
            )

        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Unable to read CSV file. {last_error}"
    )


def _read_text_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Read TXT files using automatic delimiter detection.
    """

    return _read_csv_auto(file_bytes)


def _read_json_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Read JSON and automatically handle common JSON structures.
    """

    encodings = ["utf-8", "utf-8-sig", "latin1"]

    last_error = None

    for encoding in encodings:
        try:
            text = file_bytes.decode(encoding)
            data = json.loads(text)

            # Normal list-of-records JSON
            if isinstance(data, list):
                return pd.json_normalize(data)

            # Dictionary containing records
            if isinstance(data, dict):

                # Common structure:
                # {"data": [...]}
                for key in ["data", "records", "rows", "results"]:
                    if key in data and isinstance(data[key], list):
                        return pd.json_normalize(data[key])

                # Single JSON object
                return pd.json_normalize(data)

            raise ValueError(
                "JSON structure could not be converted into a table."
            )

        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Unable to read JSON file. {last_error}"
    )


def load_dataset(uploaded_file) -> tuple[pd.DataFrame, str]:
    """
    Load an uploaded file and return:

        dataframe, detected_file_type

    Supported:
        CSV
        XLSX
        XLS
        JSON
        Parquet
        TXT
        TSV
        ODS
    """

    if uploaded_file is None:
        raise ValueError("No file was provided.")

    filename = uploaded_file.name
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS.keys())

        raise ValueError(
            f"Unsupported file type '{extension}'. "
            f"Supported types: {supported}"
        )

    file_bytes = uploaded_file.getvalue()

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    # ---------------------------------------------------------
    # CSV
    # ---------------------------------------------------------

    if extension == ".csv":

        df = _read_csv_auto(file_bytes)

        return df, "CSV"

    # ---------------------------------------------------------
    # TSV
    # ---------------------------------------------------------

    if extension == ".tsv":

        encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]

        last_error = None

        for encoding in encodings:
            try:
                text = file_bytes.decode(encoding)

                df = pd.read_csv(
                    io.StringIO(text),
                    sep="\t",
                )

                return df, "TSV"

            except Exception as exc:
                last_error = exc

        raise ValueError(
            f"Unable to read TSV file. {last_error}"
        )

    # ---------------------------------------------------------
    # Excel XLSX
    # ---------------------------------------------------------

    if extension == ".xlsx":

        df = pd.read_excel(
            io.BytesIO(file_bytes),
            engine="openpyxl",
        )

        return df, "Excel"

    # ---------------------------------------------------------
    # Excel XLS
    # ---------------------------------------------------------

    if extension == ".xls":

        df = pd.read_excel(
            io.BytesIO(file_bytes)
        )

        return df, "Excel"

    # ---------------------------------------------------------
    # JSON
    # ---------------------------------------------------------

    if extension == ".json":

        df = _read_json_auto(file_bytes)

        return df, "JSON"

    # ---------------------------------------------------------
    # Parquet
    # ---------------------------------------------------------

    if extension == ".parquet":

        df = pd.read_parquet(
            io.BytesIO(file_bytes)
        )

        return df, "Parquet"

    # ---------------------------------------------------------
    # TXT
    # ---------------------------------------------------------

    if extension == ".txt":

        df = _read_text_auto(file_bytes)

        return df, "Text"

    # ---------------------------------------------------------
    # ODS
    # ---------------------------------------------------------

    if extension == ".ods":

        df = pd.read_excel(
            io.BytesIO(file_bytes),
            engine="odf",
        )

        return df, "OpenDocument Spreadsheet"

    raise ValueError(
        f"No loader available for {extension}"
    )


def detect_column_types(df: pd.DataFrame) -> dict:
    """
    Automatically classify dataframe columns.
    """

    result = {
        "numeric": [],
        "categorical": [],
        "datetime": [],
        "boolean": [],
        "text": [],
    }

    for column in df.columns:

        series = df[column]

        # Boolean
        if pd.api.types.is_bool_dtype(series):
            result["boolean"].append(column)
            continue

        # Numeric
        if pd.api.types.is_numeric_dtype(series):
            result["numeric"].append(column)
            continue

        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            result["datetime"].append(column)
            continue

        # Try datetime detection
        try:

            converted = pd.to_datetime(
                series,
                errors="coerce",
                format="mixed",
            )

            valid_ratio = converted.notna().mean()

            if valid_ratio >= 0.80:
                result["datetime"].append(column)
                continue

        except Exception:
            pass

        # Text / categorical
        unique_ratio = (
            series.nunique(dropna=True) / max(len(series), 1)
        )

        if unique_ratio <= 0.20:
            result["categorical"].append(column)
        else:
            result["text"].append(column)

    return result


def get_dataset_info(df: pd.DataFrame) -> dict:
    """
    Generate basic dataset information after loading.
    """

    column_types = detect_column_types(df)

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "memory_mb": round(
            df.memory_usage(deep=True).sum() / (1024 * 1024),
            2,
        ),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": len(column_types["numeric"]),
        "categorical_columns": len(column_types["categorical"]),
        "datetime_columns": len(column_types["datetime"]),
        "boolean_columns": len(column_types["boolean"]),
        "text_columns": len(column_types["text"]),
        "column_types": column_types,
    }
