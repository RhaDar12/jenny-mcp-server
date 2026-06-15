import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import ensure_dirs, error_response, success_response


DEFAULT_HOSTNAME = "github.com"
DEFAULT_SSH_DIR = Path.home() / ".ssh"
DEFAULT_JENNY_KEY = DEFAULT_SSH_DIR / "id_ed25519_github_jenny"


def _find_executable(*names: str) -> Path:
    for name in names:
        executable = shutil.which(name)
        if executable:
            return Path(executable).resolve()

    raise FileNotFoundError(
        f"Executable tidak ditemukan: {', '.join(names)}"
    )


def _find_gh() -> Path:
    return _find_executable("gh", "gh.exe")


def _find_git() -> Path:
    return _find_executable("git", "git.exe")


def _find_ssh() -> Path:
    return _find_executable("ssh", "ssh.exe")


def _find_ssh_keygen() -> Path:
    return _find_executable("ssh-keygen", "ssh-keygen.exe")


def _find_ssh_add() -> Path:
    return _find_executable("ssh-add", "ssh-add.exe")


def _run(
    command: List[str],
    *,
    cwd: Optional[str] = None,
    input_text: Optional[str] = None,
    timeout: int = 300,
    accepted_codes: Optional[List[int]] = None,
) -> subprocess.CompletedProcess:
    accepted = accepted_codes or [0]

    process = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )

    if process.returncode not in accepted:
        raise RuntimeError(
            f"Command gagal dengan exit code {process.returncode}. "
            f"Output: {process.stderr or process.stdout}"
        )

    return process


def _run_interactive(
    command: List[str],
    *,
    cwd: Optional[str] = None,
    timeout: int = 900,
) -> int:
    process = subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        check=False,
    )

    if process.returncode != 0:
        raise RuntimeError(
            f"Command interaktif gagal dengan exit code "
            f"{process.returncode}."
        )

    return process.returncode


def check_github_tools() -> Dict[str, Any]:
    tool_name = "check_github_tools"

    try:
        ensure_dirs()

        gh = _find_gh()
        git = _find_git()
        ssh = _find_ssh()
        ssh_keygen = _find_ssh_keygen()

        gh_version = _run([str(gh), "--version"]).stdout.strip()
        git_version = _run([str(git), "--version"]).stdout.strip()
        ssh_version_process = _run(
            [str(ssh), "-V"],
            accepted_codes=[0],
        )
        ssh_version = (
            ssh_version_process.stderr.strip()
            or ssh_version_process.stdout.strip()
        )

        return success_response(
            tool=tool_name,
            message="GitHub CLI, Git, dan OpenSSH tersedia",
            extra={
                "gh_path": str(gh),
                "git_path": str(git),
                "ssh_path": str(ssh),
                "ssh_keygen_path": str(ssh_keygen),
                "gh_version": gh_version,
                "git_version": git_version,
                "ssh_version": ssh_version,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def auth_status(hostname: str = DEFAULT_HOSTNAME) -> Dict[str, Any]:
    tool_name = "github_auth_status"

    try:
        gh = _find_gh()

        process = _run(
            [
                str(gh),
                "auth",
                "status",
                "--hostname",
                hostname,
            ],
            accepted_codes=[0, 1],
        )

        combined = "\n".join(
            value
            for value in [
                process.stdout.strip(),
                process.stderr.strip(),
            ]
            if value
        )

        authenticated = process.returncode == 0

        return success_response(
            tool=tool_name,
            message=(
                "GitHub CLI sudah terautentikasi"
                if authenticated
                else "GitHub CLI belum terautentikasi atau sesi bermasalah"
            ),
            extra={
                "hostname": hostname,
                "authenticated": authenticated,
                "status_output": combined,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def auth_login_web(
    hostname: str = DEFAULT_HOSTNAME,
    protocol: str = "ssh",
    skip_ssh_key: bool = False,
) -> Dict[str, Any]:
    tool_name = "github_auth_login_web"

    try:
        if protocol not in {"ssh", "https"}:
            raise ValueError("protocol harus ssh atau https.")

        gh = _find_gh()

        command = [
            str(gh),
            "auth",
            "login",
            "--hostname",
            hostname,
            "--git-protocol",
            protocol,
            "--web",
        ]

        if skip_ssh_key:
            command.append("--skip-ssh-key")

        _run_interactive(command)

        status = auth_status(hostname)

        return success_response(
            tool=tool_name,
            message="Login GitHub melalui browser selesai",
            extra={
                "hostname": hostname,
                "protocol": protocol,
                "skip_ssh_key": bool(skip_ssh_key),
                "auth_status": status,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def auth_login_token(
    token: str,
    hostname: str = DEFAULT_HOSTNAME,
    protocol: str = "https",
) -> Dict[str, Any]:
    """
    Login memakai token yang diberikan melalui stdin ke gh.
    Token tidak dimasukkan ke command line dan tidak dikembalikan.
    """
    tool_name = "github_auth_login_token"

    try:
        if not token or not token.strip():
            raise ValueError("Token tidak boleh kosong.")

        if protocol not in {"ssh", "https"}:
            raise ValueError("protocol harus ssh atau https.")

        gh = _find_gh()

        _run(
            [
                str(gh),
                "auth",
                "login",
                "--hostname",
                hostname,
                "--git-protocol",
                protocol,
                "--with-token",
            ],
            input_text=token.strip() + "\n",
            timeout=300,
        )

        status = auth_status(hostname)

        return success_response(
            tool=tool_name,
            message="Login GitHub menggunakan token selesai",
            extra={
                "hostname": hostname,
                "protocol": protocol,
                "token_received": True,
                "token_exposed": False,
                "auth_status": status,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def auth_setup_git(hostname: str = DEFAULT_HOSTNAME) -> Dict[str, Any]:
    tool_name = "github_auth_setup_git"

    try:
        gh = _find_gh()

        process = _run(
            [
                str(gh),
                "auth",
                "setup-git",
                "--hostname",
                hostname,
            ]
        )

        return success_response(
            tool=tool_name,
            message="Git credential helper berhasil dikonfigurasi",
            extra={
                "hostname": hostname,
                "output": process.stdout.strip(),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def repo_list(
    owner: Optional[str] = None,
    limit: int = 30,
) -> Dict[str, Any]:
    tool_name = "github_repo_list"

    try:
        if limit < 1 or limit > 1000:
            raise ValueError("limit harus antara 1 sampai 1000.")

        gh = _find_gh()

        command = [
            str(gh),
            "repo",
            "list",
        ]

        if owner:
            command.append(owner)

        command.extend([
            "--limit",
            str(limit),
            "--json",
            "name,nameWithOwner,description,isPrivate,url,sshUrl,updatedAt",
        ])

        process = _run(command)
        repositories = json.loads(process.stdout or "[]")

        return success_response(
            tool=tool_name,
            message="Daftar repository berhasil dibaca",
            extra={
                "owner": owner,
                "limit": limit,
                "repository_count": len(repositories),
                "repositories": repositories,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def repo_view(repository: str) -> Dict[str, Any]:
    tool_name = "github_repo_view"

    try:
        if not repository.strip():
            raise ValueError("Nama repository tidak boleh kosong.")

        gh = _find_gh()

        process = _run([
            str(gh),
            "repo",
            "view",
            repository,
            "--json",
            (
                "name,nameWithOwner,description,url,sshUrl,isPrivate,"
                "defaultBranchRef,homepageUrl,createdAt,updatedAt"
            ),
        ])

        data = json.loads(process.stdout)

        return success_response(
            tool=tool_name,
            message="Informasi repository berhasil dibaca",
            extra={
                "repository": repository,
                "data": data,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def repo_clone(
    repository: str,
    directory: Optional[str] = None,
    parent_dir: Optional[str] = None,
) -> Dict[str, Any]:
    tool_name = "github_repo_clone"

    try:
        if not repository.strip():
            raise ValueError("Nama repository tidak boleh kosong.")

        gh = _find_gh()

        cwd = None
        if parent_dir:
            parent = Path(parent_dir).expanduser().resolve()
            parent.mkdir(parents=True, exist_ok=True)
            cwd = str(parent)

        command = [
            str(gh),
            "repo",
            "clone",
            repository,
        ]

        if directory:
            command.append(directory)

        process = _run(
            command,
            cwd=cwd,
            timeout=1800,
        )

        return success_response(
            tool=tool_name,
            message="Repository berhasil di-clone",
            extra={
                "repository": repository,
                "directory": directory,
                "parent_dir": cwd,
                "output": (
                    process.stdout.strip()
                    or process.stderr.strip()
                ),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def repo_create(
    name: str,
    visibility: str,
    description: Optional[str] = None,
    source: Optional[str] = None,
    push: bool = False,
    clone: bool = False,
    confirm: bool = False,
) -> Dict[str, Any]:
    tool_name = "github_repo_create"

    try:
        if not confirm:
            raise PermissionError(
                "Pembuatan repository dibatalkan karena confirm=false."
            )

        if visibility not in {"private", "public", "internal"}:
            raise ValueError(
                "visibility harus private, public, atau internal."
            )

        gh = _find_gh()

        command = [
            str(gh),
            "repo",
            "create",
            name,
            f"--{visibility}",
        ]

        if description:
            command.extend(["--description", description])

        if source:
            command.extend(["--source", str(Path(source).expanduser().resolve())])

        if push:
            command.append("--push")

        if clone:
            command.append("--clone")

        process = _run(
            command,
            timeout=900,
        )

        return success_response(
            tool=tool_name,
            message="Repository GitHub berhasil dibuat",
            extra={
                "name": name,
                "visibility": visibility,
                "description": description,
                "source": source,
                "push": bool(push),
                "clone": bool(clone),
                "confirmed": True,
                "output": (
                    process.stdout.strip()
                    or process.stderr.strip()
                ),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_list_local(
    ssh_dir: Optional[str] = None,
) -> Dict[str, Any]:
    tool_name = "github_ssh_list_local"

    try:
        directory = (
            Path(ssh_dir).expanduser().resolve()
            if ssh_dir
            else DEFAULT_SSH_DIR.resolve()
        )
        directory.mkdir(parents=True, exist_ok=True)

        ssh_keygen = _find_ssh_keygen()
        keys = []

        for public_key in sorted(directory.glob("*.pub")):
            fingerprint_process = _run(
                [
                    str(ssh_keygen),
                    "-lf",
                    str(public_key),
                ],
                accepted_codes=[0, 1],
            )

            private_key = public_key.with_suffix("")

            keys.append({
                "public_key_path": str(public_key),
                "private_key_path": (
                    str(private_key)
                    if private_key.exists()
                    else None
                ),
                "has_private_key": private_key.exists(),
                "fingerprint": (
                    fingerprint_process.stdout.strip()
                    or fingerprint_process.stderr.strip()
                ),
            })

        return success_response(
            tool=tool_name,
            message="Daftar SSH key lokal berhasil dibaca",
            extra={
                "ssh_dir": str(directory),
                "key_count": len(keys),
                "keys": keys,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_generate_interactive(
    email: str,
    key_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ssh-keygen akan meminta passphrase secara interaktif.
    Passphrase tidak diterima melalui argument CLI tool ini.
    """
    tool_name = "github_ssh_generate_interactive"

    try:
        if not email.strip():
            raise ValueError("Email tidak boleh kosong.")

        target = (
            Path(key_path).expanduser().resolve()
            if key_path
            else DEFAULT_JENNY_KEY.resolve()
        )

        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists() or target.with_suffix(".pub").exists():
            raise FileExistsError(
                f"SSH key sudah ada: {target}"
            )

        ssh_keygen = _find_ssh_keygen()

        _run_interactive([
            str(ssh_keygen),
            "-t",
            "ed25519",
            "-C",
            email,
            "-f",
            str(target),
        ])

        return success_response(
            tool=tool_name,
            message="SSH key Ed25519 berhasil dibuat",
            extra={
                "private_key_path": str(target),
                "public_key_path": str(target) + ".pub",
                "private_key_exposed": False,
                "passphrase_logged": False,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_add_to_agent(key_path: str) -> Dict[str, Any]:
    tool_name = "github_ssh_add_to_agent"

    try:
        path = Path(key_path).expanduser().resolve()

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Private SSH key tidak ditemukan: {path}")

        ssh_add = _find_ssh_add()

        process = _run(
            [
                str(ssh_add),
                str(path),
            ],
            timeout=300,
        )

        return success_response(
            tool=tool_name,
            message="SSH key berhasil ditambahkan ke ssh-agent",
            extra={
                "key_path": str(path),
                "output": (
                    process.stdout.strip()
                    or process.stderr.strip()
                ),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_upload_public_key(
    public_key_path: str,
    title: str,
) -> Dict[str, Any]:
    tool_name = "github_ssh_upload_public_key"

    try:
        path = Path(public_key_path).expanduser().resolve()

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Public SSH key tidak ditemukan: {path}")

        if path.suffix.lower() != ".pub":
            raise ValueError("Hanya file public key .pub yang boleh diunggah.")

        if not title.strip():
            raise ValueError("Title SSH key tidak boleh kosong.")

        gh = _find_gh()

        process = _run([
            str(gh),
            "ssh-key",
            "add",
            str(path),
            "--title",
            title,
            "--type",
            "authentication",
        ])

        return success_response(
            tool=tool_name,
            message="Public SSH key berhasil ditambahkan ke GitHub",
            extra={
                "public_key_path": str(path),
                "title": title,
                "key_type": "authentication",
                "private_key_uploaded": False,
                "output": (
                    process.stdout.strip()
                    or process.stderr.strip()
                ),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_list_remote() -> Dict[str, Any]:
    tool_name = "github_ssh_list_remote"

    try:
        gh = _find_gh()
        process = _run([str(gh), "ssh-key", "list"])

        return success_response(
            tool=tool_name,
            message="SSH key pada akun GitHub berhasil dibaca",
            extra={
                "output": process.stdout.strip(),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def ssh_test_github() -> Dict[str, Any]:
    tool_name = "github_ssh_test"

    try:
        ssh = _find_ssh()

        process = _run(
            [
                str(ssh),
                "-T",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "git@github.com",
            ],
            timeout=60,
            accepted_codes=[0, 1],
        )

        combined = "\n".join(
            value
            for value in [
                process.stdout.strip(),
                process.stderr.strip(),
            ]
            if value
        )

        authenticated = "successfully authenticated" in combined.lower()

        return success_response(
            tool=tool_name,
            message=(
                "Koneksi SSH GitHub berhasil"
                if authenticated
                else "Tes SSH selesai tetapi autentikasi belum terkonfirmasi"
            ),
            extra={
                "authenticated": authenticated,
                "exit_code": process.returncode,
                "output": combined,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)
