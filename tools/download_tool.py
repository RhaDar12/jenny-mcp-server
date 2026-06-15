import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import requests

from core import ensure_dirs, error_response, success_response


ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_DOWNLOAD_DIR = Path(r"C:\AI-Agent\downloads")
DEFAULT_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
CHUNK_SIZE = 1024 * 1024


def _sanitize_filename(name: str) -> str:
    name = unquote(name or "").strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r'[<>:"|?*\x00-\x1F]', "_", name)
    name = name.rstrip(" .")

    if not name:
        name = "downloaded_file"

    return name[:180]


def _filename_from_response(response: requests.Response, url: str) -> str:
    content_disposition = response.headers.get("Content-Disposition", "")

    filename_match = re.search(
        r"filename\*=UTF-8''([^;]+)",
        content_disposition,
        flags=re.IGNORECASE,
    )

    if filename_match:
        return _sanitize_filename(filename_match.group(1))

    filename_match = re.search(
        r'filename="?([^";]+)"?',
        content_disposition,
        flags=re.IGNORECASE,
    )

    if filename_match:
        return _sanitize_filename(filename_match.group(1))

    parsed = urlparse(response.url or url)
    path_name = Path(unquote(parsed.path)).name

    if path_name:
        return _sanitize_filename(path_name)

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    guessed_extension = mimetypes.guess_extension(content_type) or ""

    return f"downloaded_file{guessed_extension}"


def _unique_path(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def download_file(
    url: str,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    overwrite: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: int = 60,
    expected_sha256: Optional[str] = None,
):
    tool_name = "download_file"

    try:
        ensure_dirs()

        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError("URL harus menggunakan http:// atau https://")

        destination_dir = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else DEFAULT_DOWNLOAD_DIR.resolve()
        )
        destination_dir.mkdir(parents=True, exist_ok=True)

        with requests.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "Jenny-AI-Agent-Downloader/1.0"
            },
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length:
                declared_size = int(content_length)
                if declared_size > max_bytes:
                    raise ValueError(
                        f"Ukuran file {declared_size} byte melebihi batas "
                        f"{max_bytes} byte."
                    )
            else:
                declared_size = None

            selected_name = (
                _sanitize_filename(filename)
                if filename
                else _filename_from_response(response, url)
            )

            target_path = _unique_path(
                destination_dir / selected_name,
                overwrite=overwrite,
            )

            sha256 = hashlib.sha256()
            total_bytes = 0

            with open(target_path, "wb") as output_file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue

                    total_bytes += len(chunk)

                    if total_bytes > max_bytes:
                        output_file.close()
                        target_path.unlink(missing_ok=True)
                        raise ValueError(
                            f"Download melebihi batas {max_bytes} byte."
                        )

                    output_file.write(chunk)
                    sha256.update(chunk)

        actual_sha256 = sha256.hexdigest()

        if expected_sha256:
            normalized_expected = expected_sha256.strip().lower()

            if actual_sha256.lower() != normalized_expected:
                target_path.unlink(missing_ok=True)
                raise ValueError(
                    "Checksum SHA-256 tidak cocok. "
                    f"Expected: {normalized_expected}, actual: {actual_sha256}"
                )

        return success_response(
            tool=tool_name,
            message="File berhasil diunduh",
            file_path=target_path,
            extra={
                "requested_url": url,
                "final_url": response.url,
                "output_dir": str(destination_dir),
                "filename": target_path.name,
                "size_bytes": total_bytes,
                "declared_size_bytes": declared_size,
                "content_type": response.headers.get("Content-Type"),
                "sha256": actual_sha256,
                "checksum_verified": bool(expected_sha256),
                "overwrite": bool(overwrite),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)
