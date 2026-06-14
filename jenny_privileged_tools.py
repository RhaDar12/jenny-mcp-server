from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from approval_store import (
    consume_approval,
    create_approval_request,
)


DEFAULT_SHELL_ROOT = Path(r"C:\AI-Agent")
DEFAULT_ALLOWED_EXECUTABLES = {
    "git",
    "git.exe",
    "gh",
    "gh.exe",
    "ffmpeg",
    "ffmpeg.exe",
    "ffprobe",
    "ffprobe.exe",
    "tesseract",
    "tesseract.exe",
}

BLOCKED_ARGUMENT_FRAGMENTS = {
    ".ssh",
    "id_ed25519",
    "id_rsa",
    "gh auth token",
    "github_token",
    "gh_token",
    "roblox_open_cloud_api_key",
    "password",
    "credential",
    "credentials",
    "private key",
    "private_key",
}


def _success(
    tool: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "success": True,
        "tool": tool,
        "message": message,
        "error": None,
        **extra,
    }


def _error(
    tool: str,
    message: str,
    error: str,
) -> dict[str, Any]:
    return {
        "success": False,
        "tool": tool,
        "message": message,
        "error": error,
    }


def _run(
    command: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )

    if process.returncode != 0:
        raise RuntimeError(
            f"Exit code {process.returncode}. "
            f"Output: {process.stderr or process.stdout}"
        )

    return process


def github_delete_repository(
    repository: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Hapus repository GitHub dengan approval manual satu kali.

    `repository` wajib berbentuk owner/name agar gh tidak menghapus repo
    berdasarkan working directory secara tidak sengaja.
    """
    tool = "github_delete_repository"

    try:
        repository = repository.strip()

        if (
            repository.count("/") != 1
            or repository.startswith("/")
            or repository.endswith("/")
        ):
            raise ValueError(
                "repository wajib berbentuk owner/nama-repo."
            )

        gh = shutil.which("gh") or shutil.which("gh.exe")

        if not gh:
            raise FileNotFoundError(
                "GitHub CLI `gh` tidak ditemukan."
            )

        view = _run([
            gh,
            "repo",
            "view",
            repository,
            "--json",
            "nameWithOwner,url,isPrivate",
        ])
        info = json.loads(
            view.stdout
        )
        canonical = info["nameWithOwner"]

        parameters = {
            "repository": canonical,
        }
        summary = (
            "Hapus repository GitHub secara permanen: "
            f"{canonical}"
        )

        if not approval_id:
            return create_approval_request(
                action=tool,
                summary=summary,
                parameters=parameters,
            )

        consume_approval(
            approval_id=approval_id,
            action=tool,
            parameters=parameters,
        )

        process = _run([
            gh,
            "repo",
            "delete",
            canonical,
            "--yes",
        ])

        return _success(
            tool,
            "Repository GitHub berhasil dihapus",
            repository=canonical,
            repository_url=info.get("url"),
            output=(
                process.stdout.strip()
                or process.stderr.strip()
            ),
            irreversible=True,
        )

    except Exception as exc:
        return _error(
            tool,
            "Gagal menghapus repository GitHub",
            f"{type(exc).__name__}: {exc}",
        )


def credential_diagnostics(
    ssh_public_key_path: str | None = None,
) -> dict[str, Any]:
    """
    Laporan kredensial tanpa pernah mengembalikan token atau private key.
    """
    tool = "credential_diagnostics"

    try:
        sensitive_names = [
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "ROBLOX_OPEN_CLOUD_API_KEY",
        ]

        environment = {
            name: {
                "present": bool(
                    os.environ.get(name)
                ),
                "value_exposed": False,
            }
            for name in sensitive_names
        }

        public_key_info = None

        if ssh_public_key_path:
            public_path = (
                Path(ssh_public_key_path)
                .expanduser()
                .resolve()
            )

            if not public_path.exists():
                raise FileNotFoundError(
                    f"Public key tidak ditemukan: {public_path}"
                )

            ssh_keygen = (
                shutil.which("ssh-keygen")
                or shutil.which("ssh-keygen.exe")
            )

            fingerprint = None

            if ssh_keygen:
                process = _run([
                    ssh_keygen,
                    "-lf",
                    str(public_path),
                ])
                fingerprint = (
                    process.stdout.strip()
                    or process.stderr.strip()
                )

            public_key_info = {
                "path": str(public_path),
                "size_bytes": public_path.stat().st_size,
                "fingerprint": fingerprint,
                "private_key_exposed": False,
            }

        gh = shutil.which("gh") or shutil.which("gh.exe")
        gh_status = None

        if gh:
            process = subprocess.run(
                [
                    gh,
                    "auth",
                    "status",
                    "--hostname",
                    "github.com",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            gh_status = {
                "authenticated": process.returncode == 0,
                "status_output": (
                    process.stdout.strip()
                    or process.stderr.strip()
                ),
                "token_exposed": False,
            }

        return _success(
            tool,
            "Diagnostik kredensial berhasil dibaca tanpa menampilkan rahasia",
            environment=environment,
            github=gh_status,
            ssh_public_key=public_key_info,
        )

    except Exception as exc:
        return _error(
            tool,
            "Gagal membaca diagnostik kredensial",
            f"{type(exc).__name__}: {exc}",
        )


def roblox_publish_place(
    place_file: str,
    universe_id: int,
    place_id: int,
    version_type: str = "Published",
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Publish file .rbxl atau .rbxlx melalui Roblox Open Cloud.

    API key dibaca dari environment ROBLOX_OPEN_CLOUD_API_KEY dan tidak
    pernah dimasukkan ke output atau log.
    """
    tool = "roblox_publish_place"

    try:
        path = (
            Path(place_file)
            .expanduser()
            .resolve()
        )

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(
                f"Place file tidak ditemukan: {path}"
            )

        suffix = path.suffix.lower()

        if suffix == ".rbxlx":
            content_type = "application/xml"
        elif suffix == ".rbxl":
            content_type = "application/octet-stream"
        else:
            raise ValueError(
                "Format harus .rbxl atau .rbxlx."
            )

        if universe_id <= 0 or place_id <= 0:
            raise ValueError(
                "universe_id dan place_id harus lebih dari 0."
            )

        if version_type not in {
            "Published",
            "Saved",
        }:
            raise ValueError(
                "version_type harus Published atau Saved."
            )

        file_hash = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        parameters = {
            "place_file": str(path),
            "sha256": file_hash,
            "universe_id": int(universe_id),
            "place_id": int(place_id),
            "version_type": version_type,
        }
        summary = (
            f"Publish Roblox place {place_id} pada universe "
            f"{universe_id} dari file {path.name} "
            f"sebagai {version_type}"
        )

        if not approval_id:
            return create_approval_request(
                action=tool,
                summary=summary,
                parameters=parameters,
                ttl_seconds=900,
            )

        consume_approval(
            approval_id=approval_id,
            action=tool,
            parameters=parameters,
        )

        api_key = os.environ.get(
            "ROBLOX_OPEN_CLOUD_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "Environment ROBLOX_OPEN_CLOUD_API_KEY belum diatur."
            )

        query = urlencode({
            "versionType": version_type,
        })
        url = (
            "https://apis.roblox.com/universes/v1/"
            f"{universe_id}/places/{place_id}/versions?"
            f"{query}"
        )

        request = Request(
            url=url,
            data=path.read_bytes(),
            method="POST",
            headers={
                "x-api-key": api_key,
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=300,
            ) as response:
                raw = response.read().decode(
                    "utf-8",
                    errors="replace",
                )
                response_data = (
                    json.loads(raw)
                    if raw.strip()
                    else {}
                )

        except HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"Roblox HTTP {exc.code}: {body or exc.reason}"
            ) from exc

        except URLError as exc:
            raise ConnectionError(
                f"Tidak dapat terhubung ke Roblox: {exc.reason}"
            ) from exc

        return _success(
            tool,
            "Roblox place berhasil dipublikasikan",
            universe_id=universe_id,
            place_id=place_id,
            version_type=version_type,
            place_file=str(path),
            sha256=file_hash,
            api_key_exposed=False,
            response=response_data,
        )

    except Exception as exc:
        return _error(
            tool,
            "Gagal mempublikasikan Roblox place",
            f"{type(exc).__name__}: {exc}",
        )


def run_approved_command(
    executable: str,
    args: list[str] | None = None,
    cwd: str | None = None,
    timeout_seconds: int = 120,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Menjalankan executable allowlist dengan shell=False dan approval manual.

    Ini bukan shell bebas. PowerShell, cmd, Python, Node, WScript, dan
    executable interpreter lain tidak masuk allowlist default.
    """
    tool = "run_approved_command"

    try:
        arguments = [
            str(item)
            for item in (args or [])
        ]

        executable_name = Path(
            executable
        ).name.lower()

        configured = os.environ.get(
            "JENNY_SHELL_ALLOWED_EXECUTABLES",
            "",
        )
        allowed = set(
            DEFAULT_ALLOWED_EXECUTABLES
        )

        if configured.strip():
            allowed.update(
                item.strip().lower()
                for item in configured.split(",")
                if item.strip()
            )

        if executable_name not in allowed:
            raise PermissionError(
                "Executable tidak ada dalam allowlist: "
                f"{executable_name}"
            )

        combined = " ".join(
            [executable_name, *arguments]
        ).lower()

        for fragment in BLOCKED_ARGUMENT_FRAGMENTS:
            if fragment in combined:
                raise PermissionError(
                    "Command diblokir karena mencoba mengakses "
                    f"data sensitif: {fragment}"
                )

        resolved_executable = shutil.which(
            executable
        )

        if not resolved_executable:
            raise FileNotFoundError(
                f"Executable tidak ditemukan: {executable}"
            )

        root = Path(
            os.environ.get(
                "JENNY_SHELL_ROOT",
                str(DEFAULT_SHELL_ROOT),
            )
        ).expanduser().resolve()

        working_dir = (
            Path(cwd).expanduser().resolve()
            if cwd
            else root
        )

        try:
            working_dir.relative_to(root)
        except ValueError as exc:
            raise PermissionError(
                f"cwd harus berada di dalam {root}"
            ) from exc

        if timeout_seconds < 1 or timeout_seconds > 900:
            raise ValueError(
                "timeout_seconds harus antara 1 sampai 900."
            )

        parameters = {
            "executable": str(
                Path(resolved_executable).resolve()
            ),
            "args": arguments,
            "cwd": str(working_dir),
            "timeout_seconds": timeout_seconds,
        }
        summary = (
            "Jalankan command terkontrol: "
            + " ".join(
                [executable_name, *arguments]
            )
        )

        if not approval_id:
            return create_approval_request(
                action=tool,
                summary=summary,
                parameters=parameters,
            )

        consume_approval(
            approval_id=approval_id,
            action=tool,
            parameters=parameters,
        )

        sanitized_env = {
            key: value
            for key, value in os.environ.items()
            if not any(
                marker in key.upper()
                for marker in {
                    "TOKEN",
                    "SECRET",
                    "PASSWORD",
                    "CREDENTIAL",
                    "API_KEY",
                    "PRIVATE_KEY",
                }
            )
        }

        process = subprocess.run(
            [
                resolved_executable,
                *arguments,
            ],
            cwd=str(working_dir),
            env=sanitized_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )

        stdout = (
            process.stdout
            or ""
        )[:100000]
        stderr = (
            process.stderr
            or ""
        )[:100000]

        return {
            "success": process.returncode == 0,
            "tool": tool,
            "message": (
                "Command selesai"
                if process.returncode == 0
                else "Command selesai dengan error"
            ),
            "error": (
                None
                if process.returncode == 0
                else f"exit_code={process.returncode}"
            ),
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": (
                len(process.stdout or "") > 100000
                or len(process.stderr or "") > 100000
            ),
            "secrets_removed_from_environment": True,
        }

    except Exception as exc:
        return _error(
            tool,
            "Gagal menjalankan command terkontrol",
            f"{type(exc).__name__}: {exc}",
        )
