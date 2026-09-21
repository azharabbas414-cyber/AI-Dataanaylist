# core/data_loader.py

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".csv": "CSV",
    ".xlsx": "Excel",
    ".xls": "Excel",
    ".json": "JSON",
    ".parquet": "Parquet",
    ".txt": "Text",
    ".tsv": "TSV",
    ".ods": "OpenDocument Spreadsheet",

    # Wireshark
    ".pcap": "Wireshark PCAP",
    ".pcapng": "Wireshark PCAPNG",
    ".cap": "Wireshark Capture",
}


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def detect_file_type(filename: str) -> str:
    """
    Detect file type from filename extension.
    """

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: "
            f"{extension or 'unknown'}"
        )

    return SUPPORTED_EXTENSIONS[extension]


# ============================================================
# TSHARK DETECTION
# ============================================================

def find_tshark() -> str | None:
    """
    Find tshark executable on the system.

    Returns:
        Path to tshark or None.
    """

    tshark = shutil.which("tshark")

    if tshark:
        return tshark

    # Common Windows location
    windows_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
    ]

    for path in windows_paths:

        if Path(path).exists():
            return path

    return None


# ============================================================
# CSV
# ============================================================

def _read_csv_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Automatically detect CSV encoding and delimiter.
    """

    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1",
        "cp1252",
    ]

    last_error = None

    for encoding in encodings:

        try:

            text = file_bytes.decode(encoding)

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


# ============================================================
# TEXT
# ============================================================

def _read_text_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Read TXT file using delimiter detection.
    """

    return _read_csv_auto(file_bytes)


# ============================================================
# JSON
# ============================================================

def _read_json_auto(file_bytes: bytes) -> pd.DataFrame:
    """
    Read common JSON dataset structures.
    """

    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1",
    ]

    last_error = None

    for encoding in encodings:

        try:

            text = file_bytes.decode(encoding)

            data = json.loads(text)

            if isinstance(data, list):

                return pd.json_normalize(data)

            if isinstance(data, dict):

                for key in [
                    "data",
                    "records",
                    "rows",
                    "results",
                ]:

                    if (
                        key in data
                        and isinstance(data[key], list)
                    ):

                        return pd.json_normalize(
                            data[key]
                        )

                return pd.json_normalize(data)

            raise ValueError(
                "JSON structure could not be converted "
                "into a table."
            )

        except Exception as exc:

            last_error = exc

    raise ValueError(
        f"Unable to read JSON file. {last_error}"
    )


# ============================================================
# WIRESHARK / TSHARK
# ============================================================

def load_pcap_with_tshark(
    file_bytes: bytes,
    filename: str,
    max_packets: int = 250_000,
) -> tuple[pd.DataFrame, dict]:
    """
    Extract packet information from PCAP/PCAPNG/CAP
    using tshark.

    max_packets protects the application from attempting
    to load extremely large captures into memory.
    """

    tshark = find_tshark()

    if not tshark:

        raise RuntimeError(
            "TShark was not found on this system.\n\n"
            "Install Wireshark with the TShark component "
            "and make sure tshark.exe is available."
        )

    extension = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(
        suffix=extension,
        delete=False,
    ) as temp_file:

        temp_path = Path(temp_file.name)

        temp_file.write(file_bytes)

    try:

        # ----------------------------------------------------
        # Basic capture information
        # ----------------------------------------------------

        info_command = [
            tshark,
            "-r",
            str(temp_path),
            "-q",
            "-z",
            "io,stat,0",
        ]

        info_process = subprocess.run(
            info_command,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # ----------------------------------------------------
        # Packet extraction
        # ----------------------------------------------------

        fields = [
            "frame.number",
            "frame.time_epoch",
            "frame.len",
            "frame.protocols",

            "eth.src",
            "eth.dst",

            "ip.src",
            "ip.dst",
            "ip.proto",

            "ipv6.src",
            "ipv6.dst",
            "ipv6.nxt",

            "tcp.srcport",
            "tcp.dstport",
            "tcp.flags",
            "tcp.stream",
            "tcp.analysis.retransmission",
            "tcp.analysis.out_of_order",
            "tcp.analysis.duplicate_ack",

            "udp.srcport",
            "udp.dstport",
            "udp.stream",

            "icmp.type",
            "icmp.code",

            "dns.qry.name",

            "http.host",
            "http.request.method",
            "http.response.code",

            "tls.handshake.type",
            "tls.record.version",

            "vlan.id",

            "mpls.label",

            "pppoes.session_id",
        ]

        command = [
            tshark,
            "-r",
            str(temp_path),
            "-T",
            "fields",
            "-E",
            "header=y",
            "-E",
            "separator=\t",
            "-E",
            "quote=d",
            "-E",
            "occurrence=f",
            "-c",
            str(max_packets),
        ]

        for field in fields:

            command.extend(
                [
                    "-e",
                    field,
                ]
            )

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if process.returncode != 0:

            error = process.stderr.strip()

            raise RuntimeError(
                "TShark failed to process the capture.\n\n"
                f"{error}"
            )

        if not process.stdout.strip():

            raise ValueError(
                "No packets were extracted from the capture."
            )

        df = pd.read_csv(
            io.StringIO(process.stdout),
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        # ----------------------------------------------------
        # Rename columns
        # ----------------------------------------------------

        rename_map = {
            "frame.number": "Packet Number",
            "frame.time_epoch": "Timestamp",
            "frame.len": "Packet Length",
            "frame.protocols": "Protocols",

            "eth.src": "Ethernet Source",
            "eth.dst": "Ethernet Destination",

            "ip.src": "IPv4 Source",
            "ip.dst": "IPv4 Destination",
            "ip.proto": "IP Protocol",

            "ipv6.src": "IPv6 Source",
            "ipv6.dst": "IPv6 Destination",
            "ipv6.nxt": "IPv6 Next Header",

            "tcp.srcport": "TCP Source Port",
            "tcp.dstport": "TCP Destination Port",
            "tcp.flags": "TCP Flags",
            "tcp.stream": "TCP Stream",
            "tcp.analysis.retransmission":
                "TCP Retransmission",
            "tcp.analysis.out_of_order":
                "TCP Out Of Order",
            "tcp.analysis.duplicate_ack":
                "TCP Duplicate ACK",

            "udp.srcport": "UDP Source Port",
            "udp.dstport": "UDP Destination Port",
            "udp.stream": "UDP Stream",

            "icmp.type": "ICMP Type",
            "icmp.code": "ICMP Code",

            "dns.qry.name": "DNS Query",

            "http.host": "HTTP Host",
            "http.request.method": "HTTP Method",
            "http.response.code": "HTTP Response Code",

            "tls.handshake.type":
                "TLS Handshake Type",
            "tls.record.version":
                "TLS Version",

            "vlan.id": "VLAN ID",
            "mpls.label": "MPLS Label",

            "pppoes.session_id":
                "PPPoE Session ID",
        }

        df.rename(
            columns=rename_map,
            inplace=True,
        )

        # ----------------------------------------------------
        # Numeric conversion
        # ----------------------------------------------------

        numeric_columns = [
            "Packet Number",
            "Timestamp",
            "Packet Length",
            "IP Protocol",
            "TCP Source Port",
            "TCP Destination Port",
            "TCP Stream",
            "UDP Source Port",
            "UDP Destination Port",
            "UDP Stream",
            "ICMP Type",
            "ICMP Code",
            "HTTP Response Code",
            "VLAN ID",
            "MPLS Label",
            "PPPoE Session ID",
        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        if "Timestamp" in df.columns:

            df["Timestamp"] = pd.to_datetime(
                df["Timestamp"],
                unit="s",
                errors="coerce",
            )

        # ----------------------------------------------------
        # Packet statistics
        # ----------------------------------------------------

        packet_count = len(df)

        total_bytes = 0

        if "Packet Length" in df.columns:

            total_bytes = int(
                df["Packet Length"]
                .fillna(0)
                .sum()
            )

        duration_seconds = 0.0

        if "Timestamp" in df.columns:

            timestamps = df["Timestamp"].dropna()

            if len(timestamps) >= 2:

                duration_seconds = (
                    timestamps.max()
                    - timestamps.min()
                ).total_seconds()

        packets_per_second = 0.0
        bytes_per_second = 0.0

        if duration_seconds > 0:

            packets_per_second = (
                packet_count
                / duration_seconds
            )

            bytes_per_second = (
                total_bytes
                / duration_seconds
            )

        metadata = {
            "file_type": (
                "Wireshark PCAP"
                if extension == ".pcap"
                else (
                    "Wireshark PCAPNG"
                    if extension == ".pcapng"
                    else "Wireshark Capture"
                )
            ),
            "packets_loaded": packet_count,
            "max_packets": max_packets,
            "total_bytes": total_bytes,
            "duration_seconds": round(
                duration_seconds,
                3,
            ),
            "packets_per_second": round(
                packets_per_second,
                3,
            ),
            "bytes_per_second": round(
                bytes_per_second,
                3,
            ),
            "tshark": tshark,
            "capture_info": info_process.stdout,
        }

        return df, metadata

    finally:

        try:
            temp_path.unlink()
        except Exception:
            pass


# ============================================================
# UNIVERSAL DATASET LOADER
# ============================================================

def load_dataset(
    uploaded_file,
) -> tuple[pd.DataFrame, str]:

    if uploaded_file is None:

        raise ValueError(
            "No file was provided."
        )

    filename = uploaded_file.name

    extension = Path(
        filename
    ).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:

        supported = ", ".join(
            SUPPORTED_EXTENSIONS.keys()
        )

        raise ValueError(
            f"Unsupported file type '{extension}'. "
            f"Supported types: {supported}"
        )

    file_bytes = uploaded_file.getvalue()

    if not file_bytes:

        raise ValueError(
            "The uploaded file is empty."
        )

    # --------------------------------------------------------
    # Wireshark
    # --------------------------------------------------------

    if extension in [
        ".pcap",
        ".pcapng",
        ".cap",
    ]:

        df, metadata = load_pcap_with_tshark(
            file_bytes=file_bytes,
            filename=filename,
        )

        # Keep metadata available for the application.
        df.attrs["source_type"] = metadata[
            "file_type"
        ]

        df.attrs["capture_metadata"] = metadata

        return (
            df,
            metadata["file_type"],
        )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if extension == ".csv":

        return (
            _read_csv_auto(file_bytes),
            "CSV",
        )

    # --------------------------------------------------------
    # TSV
    # --------------------------------------------------------

    if extension == ".tsv":

        encodings = [
            "utf-8",
            "utf-8-sig",
            "latin1",
            "cp1252",
        ]

        last_error = None

        for encoding in encodings:

            try:

                text = file_bytes.decode(
                    encoding
                )

                return (
                    pd.read_csv(
                        io.StringIO(text),
                        sep="\t",
                    ),
                    "TSV",
                )

            except Exception as exc:

                last_error = exc

        raise ValueError(
            f"Unable to read TSV file. "
            f"{last_error}"
        )

    # --------------------------------------------------------
    # Excel
    # --------------------------------------------------------

    if extension == ".xlsx":

        return (
            pd.read_excel(
                io.BytesIO(file_bytes),
                engine="openpyxl",
            ),
            "Excel",
        )

    if extension == ".xls":

        return (
            pd.read_excel(
                io.BytesIO(file_bytes)
            ),
            "Excel",
        )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    if extension == ".json":

        return (
            _read_json_auto(file_bytes),
            "JSON",
        )

    # --------------------------------------------------------
    # Parquet
    # --------------------------------------------------------

    if extension == ".parquet":

        return (
            pd.read_parquet(
                io.BytesIO(file_bytes)
            ),
            "Parquet",
        )

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if extension == ".txt":

        return (
            _read_text_auto(file_bytes),
            "Text",
        )

    # --------------------------------------------------------
    # ODS
    # --------------------------------------------------------

    if extension == ".ods":

        return (
            pd.read_excel(
                io.BytesIO(file_bytes),
                engine="odf",
            ),
            "OpenDocument Spreadsheet",
        )

    raise ValueError(
        f"No loader available for {extension}"
    )


# ============================================================
# COLUMN TYPE DETECTION
# ============================================================

def detect_column_types(
    df: pd.DataFrame,
) -> dict:

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
        if pd.api.types.is_bool_dtype(
            series
        ):

            result["boolean"].append(
                column
            )

            continue

        # Numeric
        if pd.api.types.is_numeric_dtype(
            series
        ):

            result["numeric"].append(
                column
            )

            continue

        # Existing datetime
        if pd.api.types.is_datetime64_any_dtype(
            series
        ):

            result["datetime"].append(
                column
            )

            continue

        # Try datetime
        try:

            converted = pd.to_datetime(
                series,
                errors="coerce",
                format="mixed",
            )

            valid_ratio = (
                converted.notna().mean()
            )

            if valid_ratio >= 0.80:

                result["datetime"].append(
                    column
                )

                continue

        except Exception:

            pass

        # Categorical vs text
        unique_ratio = (
            series.nunique(
                dropna=True
            )
            / max(len(series), 1)
        )

        if unique_ratio <= 0.20:

            result["categorical"].append(
                column
            )

        else:

            result["text"].append(
                column
            )

    return result


# ============================================================
# DATASET INFORMATION
# ============================================================

def get_dataset_info(
    df: pd.DataFrame,
) -> dict:

    column_types = detect_column_types(
        df
    )

    return {
        "rows": len(df),
        "columns": len(df.columns),

        "memory_mb": round(
            df.memory_usage(
                deep=True
            ).sum()
            / (1024 * 1024),
            2,
        ),

        "missing_values": int(
            df.isna()
            .sum()
            .sum()
        ),

        "duplicate_rows": int(
            df.duplicated().sum()
        ),

        "numeric_columns": len(
            column_types["numeric"]
        ),

        "categorical_columns": len(
            column_types["categorical"]
        ),

        "datetime_columns": len(
            column_types["datetime"]
        ),

        "boolean_columns": len(
            column_types["boolean"]
        ),

        "text_columns": len(
            column_types["text"]
        ),

        "column_types": column_types,

        "capture_metadata": df.attrs.get(
            "capture_metadata"
        ),
    }
