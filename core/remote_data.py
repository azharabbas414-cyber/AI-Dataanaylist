from __future__ import annotations

import io
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import requests


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


class RemoteDatasetFile:
    """Small file-like wrapper compatible with InsightAI's data_loader."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content
        self.size = len(content)

    def getvalue(self) -> bytes:
        return self._content


def _safe_filename(value: str) -> str:
    value = unquote(value or "").strip()
    value = Path(value).name
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value or "remote_dataset"


def _google_drive_target(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    if "docs.google.com" in host and "/spreadsheets/d/" in path:
        match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", path)
        if match:
            file_id = match.group(1)
            return (
                f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx",
                f"google_sheet_{file_id}.xlsx",
            )

    if "drive.google.com" not in host:
        return None

    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", path)
    if match:
        file_id = match.group(1)
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"google_drive_{file_id}",
        )

    query = parse_qs(parsed.query)
    file_id = query.get("id", [None])[0]
    if file_id:
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"google_drive_{file_id}",
        )

    return None


def _extension_from_content_type(content_type: str) -> str | None:
    value = (content_type or "").lower().split(";")[0].strip()
    mapping = {
        "text/csv": ".csv",
        "application/csv": ".csv",
        "application/json": ".json",
        "text/json": ".json",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.oasis.opendocument.spreadsheet": ".ods",
        "application/parquet": ".parquet",
        "application/octet-stream": None,
        "text/tab-separated-values": ".tsv",
    }
    return mapping.get(value)


def _filename_from_response(response: requests.Response, fallback: str) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", content_disposition, re.I)
    if match:
        return _safe_filename(match.group(1))

    parsed = urlparse(response.url)
    path_name = Path(parsed.path).name
    if path_name and Path(path_name).suffix:
        return _safe_filename(path_name)

    extension = _extension_from_content_type(response.headers.get("content-type", ""))
    if extension:
        return f"{fallback}{extension}"

    return fallback


def _read_html_table(content: bytes, url: str) -> RemoteDatasetFile:
    try:
        tables = pd.read_html(io.BytesIO(content))
    except ValueError as exc:
        raise ValueError(
            "The webpage was reached, but no HTML table was found. "
            "Please provide a direct CSV/Excel/JSON file URL instead."
        ) from exc

    if not tables:
        raise ValueError("No tabular data was found on the webpage.")

    table = max(tables, key=lambda item: item.shape[0] * max(item.shape[1], 1))
    buffer = io.BytesIO()
    table.to_csv(buffer, index=False)
    return RemoteDatasetFile("website_table.csv", buffer.getvalue())


def fetch_remote_dataset(url: str, timeout: int = 60, max_mb: int = 250) -> RemoteDatasetFile:
    """Fetch a public dataset from Google Drive, Google Sheets, or a web URL."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Please enter a Google Drive link or webpage/data URL.")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")

    google_target = _google_drive_target(url)
    request_url = google_target[0] if google_target else url
    fallback_name = google_target[1] if google_target else "remote_dataset"

    headers = {
        "User-Agent": "InsightAI/1.0 (+data-intelligence-platform)",
        "Accept": "*/*",
    }

    try:
        response = requests.get(
            request_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(
            f"Unable to fetch the remote dataset: {exc}"
        ) from exc

    content = response.content
    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"Remote file is {size_mb:.1f} MB. The current limit is {max_mb} MB."
        )

    content_type = response.headers.get("content-type", "").lower()
    final_url = response.url.lower()

    # Google Drive can return an HTML confirmation/login page instead of the file.
    if "text/html" in content_type and google_target:
        if "accounts.google.com" in final_url or "signin" in final_url:
            raise ValueError(
                "This Google Drive file is not publicly accessible. "
                "Set the file to 'Anyone with the link' and try again."
            )
        return _read_html_table(content, response.url)

    if "text/html" in content_type and not google_target:
        return _read_html_table(content, response.url)

    filename = _filename_from_response(response, fallback_name)

    # Some servers provide no useful extension. Infer one from content type.
    if not Path(filename).suffix:
        extension = _extension_from_content_type(content_type)
        if extension:
            filename += extension

    return RemoteDatasetFile(filename, content)
