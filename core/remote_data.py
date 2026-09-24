from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

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
    """File-like object compatible with InsightAI's data loader."""

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


def _kaggle_target(url: str) -> tuple[str, str, str | None] | None:
    """Convert a public Kaggle dataset page into its public download API URL.

    Supports URLs such as:
    https://www.kaggle.com/datasets/owner/dataset
    https://www.kaggle.com/datasets/owner/dataset?select=My_File.csv
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "kaggle.com" not in host:
        return None

    match = re.search(r"/datasets/([^/]+)/([^/?#]+)", parsed.path)
    if not match:
        return None

    owner = unquote(match.group(1))
    dataset = unquote(match.group(2))
    query = parse_qs(parsed.query)
    selected = query.get("select", [None])[0]
    selected = unquote(selected) if selected else None

    api_url = f"https://www.kaggle.com/api/v1/datasets/download/{quote(owner)}/{quote(dataset)}"
    if selected:
        # Kaggle's public dataset API supports a file_name query for a
        # single-file download. Keep the selected path URL-encoded.
        api_url += f"?file_name={quote(selected, safe='/') }"

    return api_url, dataset, selected


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
        "text/tab-separated-values": ".tsv",
    }
    return mapping.get(value)


def _filename_from_response(response, fallback: str) -> str:
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


def _read_html_table(content: bytes) -> RemoteDatasetFile:
    """Extract the largest HTML table from a webpage."""
    try:
        tables = pd.read_html(io.BytesIO(content))
    except ImportError as exc:
        raise ValueError(
            "HTML table parsing requires html5lib and/or beautifulsoup4. "
            "Add html5lib>=1.1 and beautifulsoup4>=4.12 to requirements.txt."
        ) from exc
    except ValueError as exc:
        raise ValueError(
            "The webpage was reached, but no HTML table was found. "
            "Use a direct CSV/Excel/JSON URL, Google Sheet, Kaggle dataset link, "
            "or a webpage that exposes data as an HTML table."
        ) from exc

    if not tables:
        raise ValueError("No tabular data was found on the webpage.")

    table = max(tables, key=lambda item: item.shape[0] * max(item.shape[1], 1))
    buffer = io.BytesIO()
    table.to_csv(buffer, index=False)
    return RemoteDatasetFile("website_table.csv", buffer.getvalue())


def _browser_headers(url: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "text/csv,application/json,application/octet-stream,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": url,
    }


def _request_with_fallback(url: str, timeout: int):
    headers = _browser_headers(url)
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

    if response.status_code != 403:
        response.raise_for_status()
        return response

    try:
        from curl_cffi import requests as curl_requests

        browser_response = curl_requests.get(
            url,
            headers=headers,
            impersonate="chrome",
            timeout=timeout,
            allow_redirects=True,
        )
        browser_response.raise_for_status()
        return browser_response
    except ImportError:
        response.raise_for_status()
    except Exception:
        response.raise_for_status()

    return response


def _read_kaggle_zip(content: bytes, selected: str | None, dataset_name: str) -> RemoteDatasetFile:
    """Extract a useful data file from a Kaggle ZIP response."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        # Some Kaggle responses are a direct file rather than a ZIP.
        raise ValueError(
            f"Kaggle returned an unexpected response for dataset '{dataset_name}'. "
            "The dataset may require authentication or may be temporarily unavailable."
        ) from exc

    names = [n for n in archive.namelist() if not n.endswith("/")]
    if not names:
        raise ValueError(f"Kaggle dataset '{dataset_name}' contained no files.")

    chosen = None
    if selected:
        normalized = selected.replace("\\", "/").lstrip("/")
        for name in names:
            if name.replace("\\", "/").lstrip("/") == normalized:
                chosen = name
                break
        if chosen is None:
            # Fall back to basename matching for Kaggle paths.
            target_name = Path(normalized).name.lower()
            matches = [n for n in names if Path(n).name.lower() == target_name]
            if matches:
                chosen = matches[0]

        if chosen is None:
            available = ", ".join(Path(n).name for n in names[:10])
            raise ValueError(
                f"Kaggle file '{selected}' was not found in '{dataset_name}'. "
                f"Available files include: {available}"
            )
    else:
        supported = [n for n in names if Path(n).suffix.lower() in SUPPORTED_EXTENSIONS]
        chosen = supported[0] if supported else names[0]

    return RemoteDatasetFile(_safe_filename(chosen), archive.read(chosen))


def _fetch_kaggle_dataset(url: str, timeout: int, max_mb: int) -> RemoteDatasetFile:
    target = _kaggle_target(url)
    if not target:
        raise ValueError("Invalid Kaggle dataset URL.")

    api_url, dataset_name, selected = target
    try:
        response = _request_with_fallback(api_url, timeout)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in {401, 403}:
            raise ValueError(
                f"Kaggle denied access to dataset '{dataset_name}' (HTTP {status}). "
                "The dataset may be private, gated, or require Kaggle authentication."
            ) from exc
        raise ValueError(f"Unable to download Kaggle dataset '{dataset_name}': {exc}") from exc
    except requests.RequestException as exc:
        raise ValueError(f"Unable to download Kaggle dataset '{dataset_name}': {exc}") from exc

    content = response.content
    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(f"Kaggle response is {size_mb:.1f} MB. The current limit is {max_mb} MB.")

    content_type = response.headers.get("content-type", "").lower()
    if "zip" in content_type or content[:2] == b"PK":
        return _read_kaggle_zip(content, selected, dataset_name)

    filename = _filename_from_response(response, selected or dataset_name)
    if selected and Path(selected).suffix:
        filename = _safe_filename(selected)
    return RemoteDatasetFile(filename, content)


def fetch_remote_dataset(url: str, timeout: int = 60, max_mb: int = 250) -> RemoteDatasetFile:
    """Fetch a public dataset from Google Drive, Kaggle, a direct URL, or an HTML table."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Please enter a Google Drive link, Google Sheet, Kaggle link, or webpage/data URL.")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")

    # Kaggle dataset pages need their API download route; their HTML page
    # normally contains no static <table> for the actual dataset.
    if _kaggle_target(url):
        return _fetch_kaggle_dataset(url, timeout, max_mb)

    google_target = _google_drive_target(url)
    request_url = google_target[0] if google_target else url
    fallback_name = google_target[1] if google_target else "remote_dataset"

    try:
        response = _request_with_fallback(request_url, timeout)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 403:
            host = urlparse(url).netloc
            raise ValueError(
                f"The website {host} refused server-side access (HTTP 403). "
                "Provide the site's direct CSV/Excel/API data URL, or export the data and upload it to InsightAI."
            ) from exc
        raise ValueError(f"Unable to fetch the remote dataset: {exc}") from exc
    except requests.RequestException as exc:
        raise ValueError(f"Unable to fetch the remote dataset: {exc}") from exc

    content = response.content
    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(f"Remote file is {size_mb:.1f} MB. The current limit is {max_mb} MB.")

    content_type = response.headers.get("content-type", "").lower()
    final_url = response.url.lower()

    if "text/html" in content_type and google_target:
        if "accounts.google.com" in final_url or "signin" in final_url:
            raise ValueError(
                "This Google Drive file is not publicly accessible. Set it to 'Anyone with the link' and try again."
            )
        return _read_html_table(content)

    if "text/html" in content_type:
        return _read_html_table(content)

    filename = _filename_from_response(response, fallback_name)
    if not Path(filename).suffix:
        extension = _extension_from_content_type(content_type)
        if extension:
            filename += extension

    return RemoteDatasetFile(filename, content)
