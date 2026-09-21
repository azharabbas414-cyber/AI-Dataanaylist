# core/data_loader.py

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

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

    ".pcap": "Wireshark PCAP",
    ".pcapng": "Wireshark PCAPNG",
    ".cap": "Wireshark Capture",
}


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def detect_file_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: "
            f"{extension or 'unknown'}"
        )

    return SUPPORTED_EXTENSIONS[extension]


# ============================================================
# FIND TSHARK
# ============================================================

def find_tshark() -> str | None:

    tshark = shutil.which("tshark")

    if tshark:
        return tshark

    windows_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
    ]

    for path in windows_paths:

        if Path(path).exists():
            return path

    return None


# ============================================================
# GET AVAILABLE TSHARK FIELDS
# ============================================================

def get_available_tshark_fields(
    tshark: str,
) -> set[str]:
    """
    Get the list of fields supported by the installed
    TShark/Wireshark version.

    This prevents PCAP processing from failing because
    an optional field does not exist in a particular
    Wireshark version.
    """

    try:

        process = subprocess.run(
            [
                tshark,
                "-G",
                "fields",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if process.returncode != 0:
            return set()

        fields = set()

        for line in process.stdout.splitlines():

            parts = line.split("\t")

            # Typical format contains the field name
            # in one of the later columns.
            if len(parts) >= 3:

                field_name = parts[2].strip()

                if field_name:
                    fields.add(field_name)

        return fields

    except Exception:

        return set()


# ============================================================
# CSV
# ============================================================

def _read_csv_auto(
    file_bytes: bytes,
) -> pd.DataFrame:

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

            return pd.read_csv(
                io.StringIO(text),
                sep=None,
                engine="python",
            )

        except Exception as exc:

            last_error = exc

    raise ValueError(
        f"Unable to read CSV file. "
        f"{last_error}"
    )


# ============================================================
# TEXT
# ============================================================

def _read_text_auto(
    file_bytes: bytes,
) -> pd.DataFrame:

    return _read_csv_auto(
        file_bytes
    )


# ============================================================
# JSON
# ============================================================

def _read_json_auto(
    file_bytes: bytes,
) -> pd.DataFrame:

    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1",
    ]

    last_error = None

    for encoding in encodings:

        try:

            text = file_bytes.decode(
                encoding
            )

            data = json.loads(text)

            if isinstance(data, list):

                return pd.json_normalize(
                    data
                )

            if isinstance(data, dict):

                for key in [
                    "data",
                    "records",
                    "rows",
                    "results",
                ]:

                    if (
                        key in data
                        and isinstance(
                            data[key],
                            list,
                        )
                    ):

                        return pd.json_normalize(
                            data[key]
                        )

                return pd.json_normalize(
                    data
                )

            raise ValueError(
                "JSON structure could not "
                "be converted into a table."
            )

        except Exception as exc:

            last_error = exc

    raise ValueError(
        f"Unable to read JSON file. "
        f"{last_error}"
    )


# ============================================================
# WIRESHARK FIELD DEFINITIONS
# ============================================================

PCAP_FIELDS = {

    # Frame
    "frame.number":
        "Packet Number",

    "frame.time_epoch":
        "Timestamp",

    "frame.len":
        "Packet Length",

    "frame.protocols":
        "Protocols",

    # Ethernet
    "eth.src":
        "Ethernet Source",

    "eth.dst":
        "Ethernet Destination",

    # IPv4
    "ip.src":
        "IPv4 Source",

    "ip.dst":
        "IPv4 Destination",

    "ip.proto":
        "IP Protocol",

    # IPv6
    "ipv6.src":
        "IPv6 Source",

    "ipv6.dst":
        "IPv6 Destination",

    "ipv6.nxt":
        "IPv6 Next Header",

    # TCP
    "tcp.srcport":
        "TCP Source Port",

    "tcp.dstport":
        "TCP Destination Port",

    "tcp.flags":
        "TCP Flags",

    "tcp.stream":
        "TCP Stream",

    "tcp.analysis.retransmission":
        "TCP Retransmission",

    "tcp.analysis.out_of_order":
        "TCP Out Of Order",

    "tcp.analysis.duplicate_ack":
        "TCP Duplicate ACK",

    # UDP
    "udp.srcport":
        "UDP Source Port",

    "udp.dstport":
        "UDP Destination Port",

    "udp.stream":
        "UDP Stream",

    # ICMP
    "icmp.type":
        "ICMP Type",

    "icmp.code":
        "ICMP Code",

    # DNS
    "dns.qry.name":
        "DNS Query",

    # HTTP
    "http.host":
        "HTTP Host",

    "http.request.method":
        "HTTP Method",

    "http.response.code":
        "HTTP Response Code",

    # TLS
    "tls.handshake.type":
        "TLS Handshake Type",

    "tls.record.version":
        "TLS Version",

    # VLAN
    "vlan.id":
        "VLAN ID",

    # MPLS
    "mpls.label":
        "MPLS Label",

    # PPPoE
    #
    # IMPORTANT:
    # Do not directly depend on PPPoE fields.
    # They are version/dissector dependent.
    #
    # We intentionally do not include
    # pppoes.session_id here.
}


# ============================================================
# LOAD PCAP WITH TSHARK
# ============================================================

def load_pcap_with_tshark(
    file_bytes: bytes,
    filename: str,
    max_packets: int = 250_000,
) -> tuple[pd.DataFrame, dict]:

    tshark = find_tshark()

    if not tshark:

        raise RuntimeError(
            "TShark was not found on this system. "
            "Install Wireshark with the TShark component "
            "and make sure tshark is available."
        )

    extension = Path(
        filename
    ).suffix.lower()


    # --------------------------------------------------------
    # SAVE TEMPORARY CAPTURE
    # --------------------------------------------------------

    with tempfile.NamedTemporaryFile(
        suffix=extension,
        delete=False,
    ) as temp_file:

        temp_path = Path(
            temp_file.name
        )

        temp_file.write(
            file_bytes
        )


    try:

        # ----------------------------------------------------
        # TSHARK VERSION
        # ----------------------------------------------------

        version_process = subprocess.run(
            [
                tshark,
                "--version",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        tshark_version = (
            version_process.stdout
            or version_process.stderr
        ).splitlines()[0] \
            if (
                version_process.stdout
                or version_process.stderr
            ) \
            else "Unknown"


        # ----------------------------------------------------
        # AVAILABLE FIELDS
        # ----------------------------------------------------

        available_fields = (
            get_available_tshark_fields(
                tshark
            )
        )


        # ----------------------------------------------------
        # SELECT ONLY VALID FIELDS
        # ----------------------------------------------------

        if available_fields:

            selected_fields = [
                field
                for field in PCAP_FIELDS
                if field in available_fields
            ]

        else:

            # If field discovery fails, use a conservative
            # universally supported set.

            selected_fields = [
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
                "tcp.srcport",
                "tcp.dstport",
                "tcp.flags",
                "tcp.stream",
                "udp.srcport",
                "udp.dstport",
                "udp.stream",
            ]


        if not selected_fields:

            raise RuntimeError(
                "TShark is installed, but no usable "
                "packet fields were detected."
            )


        # ----------------------------------------------------
        # CAPTURE INFORMATION
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

        capture_info = (
            info_process.stdout
            or info_process.stderr
            or ""
        )


        # ----------------------------------------------------
        # EXTRACT PACKETS
        # ----------------------------------------------------

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


        for field in selected_fields:

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


        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if process.returncode != 0:

            error = (
                process.stderr.strip()
                or process.stdout.strip()
                or "Unknown TShark error."
            )

            raise RuntimeError(
                "TShark failed to process the capture.\n\n"
                f"{error}"
            )


        if not process.stdout.strip():

            raise ValueError(
                "No packets were extracted from "
                "the capture."
            )


        # ----------------------------------------------------
        # READ INTO PANDAS
        # ----------------------------------------------------

        df = pd.read_csv(
            io.StringIO(
                process.stdout
            ),
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )


        # ----------------------------------------------------
        # RENAME COLUMNS
        # ----------------------------------------------------

        rename_map = {
            field: PCAP_FIELDS[field]
            for field in selected_fields
            if field in PCAP_FIELDS
        }


        df.rename(
            columns=rename_map,
            inplace=True,
        )


        # ----------------------------------------------------
        # NUMERIC FIELDS
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
        ]


        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )


        # ----------------------------------------------------
        # TIMESTAMP
        # ----------------------------------------------------

        if "Timestamp" in df.columns:

            df["Timestamp"] = pd.to_datetime(
                df["Timestamp"],
                unit="s",
                errors="coerce",
            )


        # ----------------------------------------------------
        # PACKET STATISTICS
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

            timestamps = (
                df["Timestamp"]
                .dropna()
            )

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


        # ----------------------------------------------------
        # METADATA
        # ----------------------------------------------------

        if extension == ".pcap":

            file_type = "Wireshark PCAP"

        elif extension == ".pcapng":

            file_type = "Wireshark PCAPNG"

        else:

            file_type = "Wireshark Capture"


        metadata = {

            "file_type":
                file_type,

            "packets_loaded":
                packet_count,

            "max_packets":
                max_packets,

            "total_bytes":
                total_bytes,

            "duration_seconds":
                round(
                    duration_seconds,
                    3,
                ),

            "packets_per_second":
                round(
                    packets_per_second,
                    3,
                ),

            "bytes_per_second":
                round(
                    bytes_per_second,
                    3,
                ),

            "tshark":
                tshark,

            "tshark_version":
                tshark_version,

            "fields_available":
                len(
                    available_fields
                ),

            "fields_used":
                len(
                    selected_fields
                ),

            "fields_skipped":
                [
                    field
                    for field in PCAP_FIELDS
                    if field not in selected_fields
                ],

            "capture_info":
                capture_info,
        }


        # Store metadata inside DataFrame
        # so other InsightAI modules can access it.

        df.attrs[
            "source_type"
        ] = file_type

        df.attrs[
            "capture_metadata"
        ] = metadata


        return (
            df,
            metadata,
        )


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
            f"Unsupported file type "
            f"'{extension}'. "
            f"Supported types: "
            f"{supported}"
        )


    file_bytes = (
        uploaded_file.getvalue()
    )


    if not file_bytes:

        raise ValueError(
            "The uploaded file is empty."
        )


    # --------------------------------------------------------
    # WIRESHARK
    # --------------------------------------------------------

    if extension in [
        ".pcap",
        ".pcapng",
        ".cap",
    ]:

        df, metadata = (
            load_pcap_with_tshark(
                file_bytes=file_bytes,
                filename=filename,
            )
        )

        return (
            df,
            metadata["file_type"],
        )


    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if extension == ".csv":

        return (
            _read_csv_auto(
                file_bytes
            ),
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
                        io.StringIO(
                            text
                        ),
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
    # EXCEL
    # --------------------------------------------------------

    if extension == ".xlsx":

        return (
            pd.read_excel(
                io.BytesIO(
                    file_bytes
                ),
                engine="openpyxl",
            ),
            "Excel",
        )


    if extension == ".xls":

        return (
            pd.read_excel(
                io.BytesIO(
                    file_bytes
                )
            ),
            "Excel",
        )


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    if extension == ".json":

        return (
            _read_json_auto(
                file_bytes
            ),
            "JSON",
        )


    # --------------------------------------------------------
    # PARQUET
    # --------------------------------------------------------

    if extension == ".parquet":

        return (
            pd.read_parquet(
                io.BytesIO(
                    file_bytes
                )
            ),
            "Parquet",
        )


    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if extension == ".txt":

        return (
            _read_text_auto(
                file_bytes
            ),
            "Text",
        )


    # --------------------------------------------------------
    # ODS
    # --------------------------------------------------------

    if extension == ".ods":

        return (
            pd.read_excel(
                io.BytesIO(
                    file_bytes
                ),
                engine="odf",
            ),
            "OpenDocument Spreadsheet",
        )


    raise ValueError(
        f"No loader available for "
        f"{extension}"
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


        # ----------------------------------------------------
        # BOOLEAN
        # ----------------------------------------------------

        if pd.api.types.is_bool_dtype(
            series
        ):

            result[
                "boolean"
            ].append(column)

            continue


        # ----------------------------------------------------
        # NUMERIC
        # ----------------------------------------------------

        if pd.api.types.is_numeric_dtype(
            series
        ):

            result[
                "numeric"
            ].append(column)

            continue


        # ----------------------------------------------------
        # DATETIME
        # ----------------------------------------------------

        if pd.api.types.is_datetime64_any_dtype(
            series
        ):

            result[
                "datetime"
            ].append(column)

            continue


        # ----------------------------------------------------
        # TRY DATETIME
        # ----------------------------------------------------

        try:

            converted = pd.to_datetime(
                series,
                errors="coerce",
                format="mixed",
            )

            valid_ratio = (
                converted.notna()
                .mean()
            )

            if valid_ratio >= 0.80:

                result[
                    "datetime"
                ].append(column)

                continue

        except Exception:

            pass


        # ----------------------------------------------------
        # CATEGORICAL / TEXT
        # ----------------------------------------------------

        unique_ratio = (
            series.nunique(
                dropna=True
            )
            / max(
                len(series),
                1,
            )
        )


        if unique_ratio <= 0.20:

            result[
                "categorical"
            ].append(column)

        else:

            result[
                "text"
            ].append(column)


    return result


# ============================================================
# DATASET INFORMATION
# ============================================================

def get_dataset_info(
    df: pd.DataFrame,
) -> dict:

    column_types = (
        detect_column_types(df)
    )


    return {

        "rows":
            len(df),

        "columns":
            len(df.columns),

        "memory_mb":
            round(
                df.memory_usage(
                    deep=True
                ).sum()
                / (1024 * 1024),
                2,
            ),

        "missing_values":
            int(
                df.isna()
                .sum()
                .sum()
            ),

        "duplicate_rows":
            int(
                df.duplicated()
                .sum()
            ),

        "numeric_columns":
            len(
                column_types[
                    "numeric"
                ]
            ),

        "categorical_columns":
            len(
                column_types[
                    "categorical"
                ]
            ),

        "datetime_columns":
            len(
                column_types[
                    "datetime"
                ]
            ),

        "boolean_columns":
            len(
                column_types[
                    "boolean"
                ]
            ),

        "text_columns":
            len(
                column_types[
                    "text"
                ]
            ),

        "column_types":
            column_types,

        "capture_metadata":
            df.attrs.get(
                "capture_metadata"
            ),
    }
