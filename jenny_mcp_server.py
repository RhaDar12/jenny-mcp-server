from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from jenny_mcp_common import (
    SERVER_VERSION,
    availability_report,
    invoke,
    require_confirmation,
)



from jenny_privileged_tools import (
    credential_diagnostics as privileged_credential_diagnostics,
    github_delete_repository as privileged_github_delete_repository,
    roblox_publish_place as privileged_roblox_publish_place,
    run_approved_command as privileged_run_approved_command,
)
from approval_store import (
    consume_approval,
    create_approval_request,
)

mcp = FastMCP(
    "Jenny Tools",
)


@mcp.tool()
def system_status() -> dict[str, Any]:
    """Periksa versi MCP, direktori tools, dan ketersediaan semua modul."""
    return availability_report()


# ---------------------------------------------------------------------------
# ARCHIVE
# ---------------------------------------------------------------------------

@mcp.tool()
def archive_list(
    archive_path: str,
) -> dict[str, Any]:
    """Baca isi ZIP/RAR tanpa mengekstraknya."""
    return invoke(
        "archive_tool",
        "list_archive",
        archive_path,
    )


@mcp.tool()
def archive_extract(
    archive_path: str,
    output_dir: str | None = None,
    overwrite: bool = False,
    password: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Ekstrak ZIP/RAR ke folder lokal.

    Tindakan ini menulis file ke disk. `confirm=true` hanya boleh diberikan
    setelah pengguna menyetujui lokasi output dan kebijakan overwrite.
    """
    guard = require_confirmation(
        tool="archive_extract",
        action=(
            f"mengekstrak {archive_path} "
            f"ke {output_dir or 'folder otomatis'}"
        ),
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "archive_tool",
        "extract_archive",
        archive_path,
        output_dir=output_dir,
        overwrite=overwrite,
        password=password,
    )


# ---------------------------------------------------------------------------
# DOCUMENT / OCR / VIDEO
# ---------------------------------------------------------------------------

@mcp.tool()
def document_read(
    file_path: str,
    sheet_name: str | None = None,
    max_rows: int = 200,
    max_columns: int = 50,
    page_start: int | None = None,
    page_end: int | None = None,
    max_chars: int = 50000,
) -> dict[str, Any]:
    """Baca DOCX, XLSX, atau PDF lokal dengan batas output terkontrol."""
    return invoke(
        "document_reader_tool",
        "read_document",
        file_path,
        sheet_name=sheet_name,
        max_rows=max_rows,
        max_columns=max_columns,
        page_start=page_start,
        page_end=page_end,
        max_chars=max_chars,
    )


@mcp.tool()
def image_ocr_languages() -> dict[str, Any]:
    """Daftar bahasa yang tersedia pada Tesseract OCR lokal."""
    return invoke(
        "image_text_tool",
        "list_ocr_languages",
    )


@mcp.tool()
def image_ocr(
    image_path: str,
    lang: str = "eng",
    preprocess: str = "grayscale",
    scale: float = 1.5,
    psm: int = 6,
    max_chars: int = 50000,
    include_words: bool = False,
) -> dict[str, Any]:
    """Baca teks dalam gambar menggunakan Tesseract OCR lokal."""
    return invoke(
        "image_text_tool",
        "read_image_text",
        image_path,
        lang=lang,
        preprocess=preprocess,
        scale=scale,
        psm=psm,
        max_chars=max_chars,
        include_words=include_words,
    )


@mcp.tool()
def video_probe(
    video_path: str,
) -> dict[str, Any]:
    """Baca metadata video tanpa mengekstrak frame atau audio."""
    return invoke(
        "video_reader_tool",
        "probe_video",
        video_path,
    )


@mcp.tool()
def video_read(
    video_path: str,
    output_dir: str | None = None,
    frame_count: int = 8,
    extract_audio_file: bool = True,
    transcribe: bool = False,
    whisper_model: str = "small",
    language: str | None = None,
    whisper_device: str = "cpu",
    whisper_compute_type: str = "int8",
) -> dict[str, Any]:
    """Ekstrak frame, audio, dan opsional transkripsi dari video lokal."""
    return invoke(
        "video_reader_tool",
        "read_video",
        video_path,
        output_dir=output_dir,
        frame_count=frame_count,
        extract_audio_file=extract_audio_file,
        transcribe=transcribe,
        whisper_model=whisper_model,
        language=language,
        whisper_device=whisper_device,
        whisper_compute_type=whisper_compute_type,
    )


# ---------------------------------------------------------------------------
# DOWNLOAD / CLIPBOARD / SCREENSHOT
# ---------------------------------------------------------------------------

@mcp.tool()
def download_file(
    url: str,
    output_dir: str | None = None,
    filename: str | None = None,
    overwrite: bool = False,
    max_bytes: int = 524288000,
    timeout_seconds: int = 60,
    expected_sha256: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Download file dari URL ke komputer lokal.

    Wajib `confirm=true` setelah pengguna menyetujui URL dan lokasi output.
    """
    guard = require_confirmation(
        tool="download_file",
        action=f"mengunduh file dari {url}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "download_tool",
        "download_file",
        url,
        output_dir=output_dir,
        filename=filename,
        overwrite=overwrite,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        expected_sha256=expected_sha256,
    )


@mcp.tool()
def clipboard_read(
    max_chars: int = 50000,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Baca clipboard Windows.

    Clipboard dapat memuat data sensitif. Gunakan `confirm=true` hanya ketika
    pengguna secara eksplisit meminta isi clipboard dibaca.
    """
    guard = require_confirmation(
        tool="clipboard_read",
        action="membaca clipboard pengguna",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "clipboard_tool",
        "read_clipboard",
        max_chars=max_chars,
    )


@mcp.tool()
def clipboard_write(
    text: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Tulis teks ke clipboard setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="clipboard_write",
        action="mengganti isi clipboard",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "clipboard_tool",
        "write_clipboard",
        text,
    )


@mcp.tool()
def clipboard_clear(
    confirm: bool = False,
) -> dict[str, Any]:
    """Kosongkan clipboard setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="clipboard_clear",
        action="mengosongkan clipboard",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "clipboard_tool",
        "clear_clipboard",
    )


@mcp.tool()
def screenshot_full(
    output_dir: str | None = None,
    filename: str | None = None,
    delay: float = 0.0,
) -> dict[str, Any]:
    """Ambil screenshot seluruh desktop/semua monitor."""
    return invoke(
        "screenshot_tool",
        "take_full_screenshot",
        output_dir=output_dir,
        filename=filename,
        delay=delay,
    )


# ---------------------------------------------------------------------------
# WEB SEARCH / HEADLESS WEB
# ---------------------------------------------------------------------------

@mcp.tool()
def web_search(
    query: str,
    max_results: int = 10,
    region: str = "id-id",
    safesearch: str = "moderate",
    timelimit: str | None = None,
) -> dict[str, Any]:
    """Cari web menggunakan mesin pencari ringan."""
    return invoke(
        "web_search_tool",
        "search_web",
        query,
        max_results=max_results,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
    )


@mcp.tool()
def web_news(
    query: str,
    max_results: int = 10,
    region: str = "id-id",
    safesearch: str = "moderate",
    timelimit: str | None = "m",
) -> dict[str, Any]:
    """Cari berita web berdasarkan kata kunci."""
    return invoke(
        "web_search_tool",
        "search_news",
        query,
        max_results=max_results,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
    )


@mcp.tool()
def web_read(
    url: str,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    max_chars: int = 50000,
    include_links: bool = True,
    max_links: int = 100,
    headless: bool = True,
) -> dict[str, Any]:
    """Buka dan baca halaman web dalam browser terisolasi."""
    return invoke(
        "web_browser_tool",
        "read_web_page",
        url,
        wait_until=wait_until,
        timeout_ms=timeout_ms,
        max_chars=max_chars,
        include_links=include_links,
        max_links=max_links,
        headless=headless,
    )


@mcp.tool()
def web_screenshot(
    url: str,
    output_dir: str | None = None,
    filename: str | None = None,
    full_page: bool = True,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    wait_until: str = "networkidle",
    timeout_ms: int = 45000,
    headless: bool = True,
) -> dict[str, Any]:
    """Ambil screenshot halaman web pada browser terisolasi."""
    return invoke(
        "web_browser_tool",
        "screenshot_web_page",
        url,
        output_dir=output_dir,
        filename=filename,
        full_page=full_page,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        wait_until=wait_until,
        timeout_ms=timeout_ms,
        headless=headless,
    )


@mcp.tool()
def web_click_read(
    url: str,
    selector: str,
    timeout_ms: int = 30000,
    max_chars: int = 50000,
    headless: bool = True,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Buka URL, klik selector, lalu baca hasilnya.

    Klik dapat memicu tindakan. Gunakan hanya setelah konfirmasi pengguna.
    """
    guard = require_confirmation(
        tool="web_click_read",
        action=f"mengklik selector {selector} pada {url}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "web_browser_tool",
        "browser_click_and_read",
        url,
        selector,
        timeout_ms=timeout_ms,
        max_chars=max_chars,
        headless=headless,
    )


# ---------------------------------------------------------------------------
# BRAVE SEARCH / INTERACTIVE BROWSER
# ---------------------------------------------------------------------------

@mcp.tool()
def brave_search(
    query: str,
    max_results: int = 10,
    country: str = "id",
    language: str = "id-id",
    freshness: str | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """Cari web memakai halaman Brave Search."""
    return invoke(
        "brave_search_tool",
        "search_brave",
        query,
        max_results=max_results,
        country=country,
        language=language,
        freshness=freshness,
        headless=headless,
    )


@mcp.tool()
def brave_open(
    url: str,
    mode: str = "persistent",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 45000,
) -> dict[str, Any]:
    """Buka URL di Brave profil Jenny atau Brave utama melalui CDP."""
    return invoke(
        "brave_browser_tool",
        "open_page",
        url,
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
        wait_until=wait_until,
        timeout_ms=timeout_ms,
    )


@mcp.tool()
def brave_read(
    mode: str = "persistent",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
    max_chars: int = 50000,
    max_links: int = 100,
) -> dict[str, Any]:
    """Baca tab aktif Brave secara real time."""
    return invoke(
        "brave_browser_tool",
        "read_current_page",
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
        max_chars=max_chars,
        max_links=max_links,
    )


@mcp.tool()
def brave_tabs(
    mode: str = "cdp",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
) -> dict[str, Any]:
    """Daftar tab Brave yang sedang tersedia."""
    return invoke(
        "brave_browser_tool",
        "list_tabs",
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
    )


@mcp.tool()
def brave_screenshot(
    output_dir: str | None = None,
    filename: str | None = None,
    mode: str = "persistent",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
    full_page: bool = True,
) -> dict[str, Any]:
    """Ambil screenshot tab aktif Brave."""
    return invoke(
        "brave_browser_tool",
        "screenshot_current_page",
        output_dir=output_dir,
        filename=filename,
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
        full_page=full_page,
    )


@mcp.tool()
def brave_fill(
    selector: str,
    value: str,
    mode: str = "persistent",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
    clear_first: bool = True,
    confirm: bool = False,
) -> dict[str, Any]:
    """Isi form Brave setelah pengguna mengonfirmasi target dan nilainya."""
    guard = require_confirmation(
        tool="brave_fill",
        action=f"mengisi selector {selector}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "brave_browser_tool",
        "fill_field",
        selector,
        value,
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
        clear_first=clear_first,
    )


@mcp.tool()
def brave_click(
    selector: str,
    mode: str = "persistent",
    profile_dir: str | None = None,
    cdp_url: str = "http://127.0.0.1:9222",
    wait_after_ms: int = 1000,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Klik elemen Brave.

    Wajib konfirmasi karena klik dapat mengirim form, membeli, menghapus,
    mempublikasikan, atau menjalankan tindakan lain.
    """
    guard = require_confirmation(
        tool="brave_click",
        action=f"mengklik selector {selector}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "brave_browser_tool",
        "click_element",
        selector,
        mode=mode,
        profile_dir=profile_dir,
        cdp_url=cdp_url,
        wait_after_ms=wait_after_ms,
    )


# ---------------------------------------------------------------------------
# GITHUB
# ---------------------------------------------------------------------------

@mcp.tool()
def github_check() -> dict[str, Any]:
    """Periksa ketersediaan gh, git, dan OpenSSH."""
    return invoke(
        "github_cli_tool",
        "check_github_tools",
    )


@mcp.tool()
def github_status(
    hostname: str = "github.com",
) -> dict[str, Any]:
    """Periksa status autentikasi GitHub CLI tanpa menampilkan token."""
    return invoke(
        "github_cli_tool",
        "auth_status",
        hostname=hostname,
    )


@mcp.tool()
def github_repo_list(
    owner: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """Daftar repository milik akun atau owner tertentu."""
    return invoke(
        "github_cli_tool",
        "repo_list",
        owner=owner,
        limit=limit,
    )


@mcp.tool()
def github_repo_view(
    repository: str,
) -> dict[str, Any]:
    """Lihat informasi repository, misalnya owner/nama-repo."""
    return invoke(
        "github_cli_tool",
        "repo_view",
        repository,
    )


@mcp.tool()
def github_clone(
    repository: str,
    directory: str | None = None,
    parent_dir: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Clone repository ke disk setelah konfirmasi lokasi tujuan."""
    guard = require_confirmation(
        tool="github_clone",
        action=f"clone repository {repository}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "github_cli_tool",
        "repo_clone",
        repository,
        directory=directory,
        parent_dir=parent_dir,
    )


@mcp.tool()
def github_create_repo(
    name: str,
    visibility: str,
    description: str | None = None,
    source: str | None = None,
    push: bool = False,
    clone: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Buat repository GitHub baru setelah konfirmasi eksplisit pengguna."""
    guard = require_confirmation(
        tool="github_create_repo",
        action=(
            f"membuat repository GitHub {name} "
            f"dengan visibility {visibility}"
        ),
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "github_cli_tool",
        "repo_create",
        name,
        visibility,
        description=description,
        source=source,
        push=push,
        clone=clone,
        confirm=True,
    )


@mcp.tool()
def github_ssh_local(
    ssh_dir: str | None = None,
) -> dict[str, Any]:
    """Daftar public/private SSH key lokal tanpa membaca isi private key."""
    return invoke(
        "github_cli_tool",
        "ssh_list_local",
        ssh_dir=ssh_dir,
    )


@mcp.tool()
def github_ssh_remote() -> dict[str, Any]:
    """Daftar SSH public key yang terpasang pada akun GitHub."""
    return invoke(
        "github_cli_tool",
        "ssh_list_remote",
    )


@mcp.tool()
def github_ssh_test() -> dict[str, Any]:
    """Tes autentikasi SSH ke GitHub."""
    return invoke(
        "github_cli_tool",
        "ssh_test_github",
    )


# ---------------------------------------------------------------------------
# COMFYUI IMAGE GENERATION
# ---------------------------------------------------------------------------

@mcp.tool()
def comfy_status() -> dict[str, Any]:
    """Periksa apakah ComfyUI lokal siap digunakan."""
    return invoke(
        "comfy_image_tool",
        "check_comfyui",
    )


@mcp.tool()
def comfy_generate(
    prompt: str,
    negative_prompt: str = (
        "low quality, blurry, distorted, watermark, text"
    ),
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    seed: int | None = None,
    workflow_path: str | None = None,
    target: str | None = None,
    caption: str = "Gambar dari ComfyUI AI-Agent",
) -> dict[str, Any]:
    """Generate gambar menggunakan ComfyUI lokal."""
    return invoke(
        "comfy_image_tool",
        "generate_comfy_image",
        prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        sampler_name=sampler_name,
        scheduler=scheduler,
        seed=seed,
        workflow_path=workflow_path,
        target=target,
        caption=caption,
    )


# ---------------------------------------------------------------------------
# ROBLOX STUDIO
# ---------------------------------------------------------------------------

@mcp.tool()
def roblox_health(
    bridge_url: str = "http://127.0.0.1:8765",
) -> dict[str, Any]:
    """Periksa server bridge dan koneksi plugin Roblox Studio."""
    return invoke(
        "roblox_studio_tool",
        "bridge_health",
        bridge_url=bridge_url,
    )


@mcp.tool()
def roblox_place_info(
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
) -> dict[str, Any]:
    """Baca PlaceId, GameId, nama project, dan status Play Test."""
    return invoke(
        "roblox_studio_tool",
        "send_command",
        "get_place_info",
        {},
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_hierarchy(
    root: str = "Workspace",
    max_depth: int = 3,
    max_children: int = 100,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
) -> dict[str, Any]:
    """Baca hierarchy Roblox Studio dari root tertentu."""
    return invoke(
        "roblox_studio_tool",
        "send_command",
        "get_hierarchy",
        {
            "root": root,
            "max_depth": max_depth,
            "max_children": max_children,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_selection(
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
) -> dict[str, Any]:
    """Baca objek yang sedang dipilih di Roblox Studio."""
    return invoke(
        "roblox_studio_tool",
        "send_command",
        "get_selection",
        {},
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_inspect(
    path: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
) -> dict[str, Any]:
    """Baca class, path, parent, transform, dan property target Studio."""
    return invoke(
        "roblox_studio_tool",
        "send_command",
        "get_instance",
        {"path": path},
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_select(
    path: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
) -> dict[str, Any]:
    """Pilih objek pada Explorer Roblox Studio."""
    return invoke(
        "roblox_studio_tool",
        "send_command",
        "select_instance",
        {"path": path},
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_visual_inspect(
    path: str,
    views: str = "isometric,front",
    padding: float = 1.25,
    screenshot: bool = True,
    settle_seconds: float = 1.25,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Fokuskan kamera ke path, ambil screenshot, dan kembalikan path visual."""
    return invoke(
        "roblox_studio_tool",
        "visual_inspect",
        path=path,
        use_selection=False,
        views=views,
        padding=padding,
        screenshot=screenshot,
        settle_seconds=settle_seconds,
        bridge_url=bridge_url,
        token_file=token_file,
        output_dir=output_dir,
    )


@mcp.tool()
def roblox_visual_selection(
    views: str = "isometric,front",
    padding: float = 1.25,
    screenshot: bool = True,
    settle_seconds: float = 1.25,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Visual Inspect terhadap objek yang sedang dipilih di Studio."""
    return invoke(
        "roblox_studio_tool",
        "visual_inspect",
        use_selection=True,
        views=views,
        padding=padding,
        screenshot=screenshot,
        settle_seconds=settle_seconds,
        bridge_url=bridge_url,
        token_file=token_file,
        output_dir=output_dir,
    )


@mcp.tool()
def roblox_create_part(
    name: str = "JennyPart",
    parent: str = "Workspace",
    position: dict[str, float] | None = None,
    size: dict[str, float] | None = None,
    anchored: bool = True,
    can_collide: bool = True,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Buat Part baru di Studio setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="roblox_create_part",
        action=f"membuat Part {parent}/{name}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "create_part",
        {
            "name": name,
            "parent": parent,
            "position": position or {
                "x": 0,
                "y": 5,
                "z": 0,
            },
            "size": size or {
                "x": 4,
                "y": 1,
                "z": 4,
            },
            "anchored": anchored,
            "can_collide": can_collide,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_set_properties(
    path: str,
    properties: dict[str, Any],
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Ubah property allowlist pada Instance setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="roblox_set_properties",
        action=f"mengubah property {path}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "set_properties",
        {
            "path": path,
            "properties": properties,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_rename(
    path: str,
    new_name: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Rename Instance Roblox Studio setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="roblox_rename",
        action=f"rename {path} menjadi {new_name}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "rename_instance",
        {
            "path": path,
            "new_name": new_name,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_reparent(
    path: str,
    new_parent: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Pindahkan parent Instance setelah konfirmasi pengguna."""
    guard = require_confirmation(
        tool="roblox_reparent",
        action=f"memindahkan {path} ke {new_parent}",
        confirm=confirm,
    )
    if guard:
        return guard

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "reparent_instance",
        {
            "path": path,
            "new_parent": new_parent,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )



# ---------------------------------------------------------------------------
# PRIVILEGED ACTIONS WITH MANUAL HUMAN APPROVAL
# ---------------------------------------------------------------------------

@mcp.tool()
def github_delete_repository(
    repository: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Hapus repository GitHub secara permanen.

    Panggilan pertama membuat approval ticket. Pengguna harus menyetujuinya
    manual lewat approve_mcp_action.py, lalu panggil ulang dengan approval_id.
    """
    return privileged_github_delete_repository(
        repository=repository,
        approval_id=approval_id,
    )


@mcp.tool()
def credential_diagnostics(
    ssh_public_key_path: str | None = None,
) -> dict[str, Any]:
    """
    Periksa status token/API key dan fingerprint public key tanpa pernah
    menampilkan token atau isi private SSH key.
    """
    return privileged_credential_diagnostics(
        ssh_public_key_path=ssh_public_key_path,
    )


@mcp.tool()
def roblox_delete_instance(
    path: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Hapus Instance Roblox Studio. Perubahan direkam oleh ChangeHistoryService
    dan dapat di-undo selama sesi Studio masih mendukungnya.
    """
    tool = "roblox_delete_instance"
    parameters = {
        "path": path,
        "bridge_url": bridge_url,
        "token_file": token_file,
    }

    if not approval_id:
        return create_approval_request(
            action=tool,
            summary=f"Hapus Instance Roblox Studio: {path}",
            parameters=parameters,
        )

    try:
        consume_approval(
            approval_id=approval_id,
            action=tool,
            parameters=parameters,
        )
    except Exception as exc:
        return {
            "success": False,
            "tool": tool,
            "message": "Approval tidak valid",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "delete_instance",
        {"path": path},
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
    )


@mcp.tool()
def roblox_update_script(
    path: str,
    source: str,
    bridge_url: str = "http://127.0.0.1:8765",
    token_file: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Ganti seluruh source Script/LocalScript/ModuleScript menggunakan
    ScriptEditorService. Tindakan memerlukan approval manual satu kali.
    """
    tool = "roblox_update_script"

    if len(source) > 500000:
        return {
            "success": False,
            "tool": tool,
            "message": "Source terlalu besar",
            "error": "Batas source adalah 500.000 karakter.",
        }

    import hashlib

    parameters = {
        "path": path,
        "source_sha256": hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest(),
        "source_length": len(source),
        "bridge_url": bridge_url,
        "token_file": token_file,
    }

    if not approval_id:
        return create_approval_request(
            action=tool,
            summary=(
                f"Ganti seluruh source Roblox script {path} "
                f"({len(source)} karakter)"
            ),
            parameters=parameters,
        )

    try:
        consume_approval(
            approval_id=approval_id,
            action=tool,
            parameters=parameters,
        )
    except Exception as exc:
        return {
            "success": False,
            "tool": tool,
            "message": "Approval tidak valid",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return invoke(
        "roblox_studio_tool",
        "send_command",
        "update_script_source",
        {
            "path": path,
            "source": source,
        },
        bridge_url=bridge_url,
        token_file=token_file,
        wait=True,
        wait_timeout=60,
    )


@mcp.tool()
def roblox_publish_place(
    place_file: str,
    universe_id: int,
    place_id: int,
    version_type: str = "Published",
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Publish .rbxl/.rbxlx melalui Roblox Open Cloud. API key dibaca dari
    environment ROBLOX_OPEN_CLOUD_API_KEY dan tidak pernah diekspos.
    """
    return privileged_roblox_publish_place(
        place_file=place_file,
        universe_id=universe_id,
        place_id=place_id,
        version_type=version_type,
        approval_id=approval_id,
    )


@mcp.tool()
def run_approved_command(
    executable: str,
    args: list[str] | None = None,
    cwd: str | None = None,
    timeout_seconds: int = 120,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """
    Jalankan executable allowlist memakai shell=False dan approval manual.
    Ini bukan shell bebas; interpreter dan akses kredensial diblokir.
    """
    return privileged_run_approved_command(
        executable=executable,
        args=args,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        approval_id=approval_id,
    )



@mcp.tool()
def market_watch(
    symbols: list[str] | None = None,
    news_status: str = "Manual check required",
    spread_text: str | None = None,
    target: str | None = None,
    send_only_on_entry: bool = True,
    force_send: bool = False,
    timeframe: str = "5m",
) -> dict[str, Any]:
    """Scan M5 market (XAUUSD, GBPUSD, EURUSD) buat liquidity sweep — deteksi entry, S&R, dan risk reward."""
    return invoke(
        "market_watch_tool",
        "run_market_watch",
        news_status=news_status,
        spread_text=spread_text,
        target=target,
        symbols=symbols,
        send_only_on_entry=send_only_on_entry,
        force_send=force_send,
        timeframe=timeframe,
    )



def main() -> None:
    """Jalankan Jenny Tools sebagai MCP stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
