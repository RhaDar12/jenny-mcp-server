import re
import subprocess
from pathlib import Path, PurePosixPath

from core import (
    ensure_dirs,
    error_response,
    success_response,
)


SUPPORTED_EXTENSIONS = {
    ".zip",
    ".rar",
}

DEFAULT_WINRAR_PATHS = [
    Path(r"C:\Program Files\WinRAR\Rar.exe"),
    Path(r"C:\Program Files (x86)\WinRAR\Rar.exe"),
]


def _validate_archive_path(archive_path):
    """
    Memastikan arsip ada, berupa file, dan formatnya didukung.
    """
    archive = Path(archive_path).expanduser().resolve()

    if not archive.exists():
        raise FileNotFoundError(
            f"File arsip tidak ditemukan: {archive}"
        )

    if not archive.is_file():
        raise ValueError(
            f"Path bukan file: {archive}"
        )

    extension = archive.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Format arsip tidak didukung: {extension}. "
            "Gunakan .zip atau .rar."
        )

    return archive


def _find_winrar():
    """
    Mencari Rar.exe, command-line tool bawaan WinRAR.
    """
    for candidate in DEFAULT_WINRAR_PATHS:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Rar.exe tidak ditemukan. Pastikan WinRAR terpasang di "
        r"C:\Program Files\WinRAR\Rar.exe"
    )


def _is_safe_member_path(member_name):
    """
    Mendeteksi path traversal seperti:
    ../../Windows/file.txt
    C:/Windows/file.txt
    """
    if not member_name:
        return False

    normalized = str(member_name).replace("\\", "/").strip()
    path = PurePosixPath(normalized)

    if path.is_absolute():
        return False

    if ".." in path.parts:
        return False

    if re.match(r"^[A-Za-z]:", normalized):
        return False

    return True


def _run_winrar_cli(command, timeout=600):
    """
    Menjalankan WinRAR CLI dan mengembalikan hasil proses.
    """
    winrar = _find_winrar()

    process = subprocess.run(
        [str(winrar), *command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    if process.returncode not in (0, 1):
        raise RuntimeError(
            "WinRAR gagal menjalankan perintah. "
            f"Exit code: {process.returncode}. "
            f"Output: {process.stdout or process.stderr}"
        )

    return process


def _parse_winrar_list_output(output_text, archive):
    """
    Parsing output `WinRAR lb`.

    Perintah `lb` menampilkan nama file arsip dalam format ringkas.
    """
    items = []

    for raw_line in output_text.splitlines():
        name = raw_line.strip()

        if not name:
            continue

        # Hindari memasukkan nama arsip itu sendiri.
        if name == archive.name or name == str(archive):
            continue

        normalized = name.replace("\\", "/")
        is_directory = normalized.endswith("/")

        items.append({
            "name": name,
            "is_directory": is_directory,
            "safe_path": _is_safe_member_path(name),
        })

    return items


def list_archive(archive_path):
    """
    Membaca daftar file di dalam ZIP/RAR tanpa mengekstraknya.
    """
    tool_name = "list_archive"

    try:
        ensure_dirs()
        archive = _validate_archive_path(archive_path)

        process = _run_winrar_cli(
            [
                "lb",
                "-c-",
                "-p-",
                str(archive),
            ],
            timeout=120,
        )

        items = _parse_winrar_list_output(
            process.stdout,
            archive,
        )

        unsafe_items = [
            item["name"]
            for item in items
            if not item["safe_path"]
        ]

        return success_response(
            tool=tool_name,
            message="Isi arsip berhasil dibaca menggunakan WinRAR",
            extra={
                "archive_path": str(archive),
                "archive_type": archive.suffix.lower(),
                "backend": "winrar",
                "item_count": len(items),
                "unsafe_items": unsafe_items,
                "items": items,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def _snapshot_files(directory):
    """
    Mengambil daftar file di suatu folder untuk membandingkan
    kondisi sebelum dan sesudah ekstraksi.
    """
    directory = Path(directory)

    if not directory.exists():
        return set()

    return {
        str(path.resolve())
        for path in directory.rglob("*")
        if path.is_file()
    }


def extract_archive(
    archive_path,
    output_dir=None,
    overwrite=False,
    password=None,
):
    """
    Mengekstrak ZIP/RAR menggunakan WinRAR.

    overwrite=False:
    melewati file yang sudah ada.

    overwrite=True:
    menimpa file yang sudah ada.
    """
    tool_name = "extract_archive"

    try:
        ensure_dirs()
        archive = _validate_archive_path(archive_path)

        if output_dir:
            destination = Path(output_dir).expanduser().resolve()
        else:
            destination = (
                archive.parent / f"{archive.stem}_extracted"
            ).resolve()

        destination.mkdir(parents=True, exist_ok=True)

        # Audit isi arsip lebih dahulu.
        listing = list_archive(str(archive))

        if not listing.get("success"):
            raise RuntimeError(
                listing.get(
                    "error",
                    "Gagal membaca isi arsip sebelum ekstraksi.",
                )
            )

        unsafe_items = listing.get("unsafe_items", [])

        if unsafe_items:
            raise RuntimeError(
                "Ekstraksi dibatalkan karena ditemukan path "
                f"berbahaya: {unsafe_items}"
            )

        files_before = _snapshot_files(destination)

        command = [
            "x",
            "-ibck",
            "-inul",
            "-y",
        ]

        if overwrite:
            # Overwrite semua tanpa bertanya.
            command.append("-o+")
        else:
            # Lewati file yang sudah ada.
            command.append("-o-")

        if password:
            command.append(f"-p{password}")
        else:
            # Jangan tampilkan prompt password interaktif.
            command.append("-p-")

        command.extend([
            str(archive),
            str(destination) + "\\",
        ])

        _run_winrar_cli(
            command,
            timeout=600,
        )

        files_after = _snapshot_files(destination)
        extracted_files = sorted(files_after - files_before)

        # Jika overwrite aktif, file mungkin tidak dianggap baru.
        # Dalam kasus itu kembalikan semua file di destination.
        if overwrite and not extracted_files:
            extracted_files = sorted(files_after)

        return success_response(
            tool=tool_name,
            message="Arsip berhasil diekstrak menggunakan WinRAR",
            file_path=destination,
            extra={
                "archive_path": str(archive),
                "archive_type": archive.suffix.lower(),
                "output_dir": str(destination),
                "backend": "winrar",
                "overwrite": bool(overwrite),
                "password_used": bool(password),
                "extracted_file_count": len(extracted_files),
                "extracted_files": extracted_files,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)

