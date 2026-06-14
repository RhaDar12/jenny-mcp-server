# Jenny Tools – MCP Server 🤖

Server MCP (Model Context Protocol) lokal yang membungkus tool Python untuk AI Agent, memungkinkan interaksi langsung dengan Windows — browser, clipboard, file, GitHub, Roblox Studio, screenshot, OCR, dan banyak lagi.

Dibangun dengan arsitektur **stdio MCP** + **privileged approval system**, cocok dipasangkan dengan Hermes Agent, Claude Code, atau MCP client lain.

## ✨ Fitur

| Modul | Fungsi |
|-------|--------|
| **🌐 Brave Browser** | Buka URL, klik, isi form, screenshot, baca halaman via CDP |
| **🔍 Brave Search** | Cari web + berita dengan parameter negara/bahasa |
| **🌍 Web Tools** | Baca halaman, screenshot, click-and-read via browser headless |
| **📁 Archive** | Baca & ekstrak ZIP/RAR |
| **📄 Document Reader** | Baca DOCX, XLSX, PDF |
| **🖼️ OCR** | Baca teks dari gambar via Tesseract |
| **🎬 Video Reader** | Ekstrak frame, audio, transkripsi dari video |
| **📋 Clipboard** | Baca, tulis, bersihkan clipboard Windows |
| **⬇️ Download** | Download file dari URL |
| **📸 Screenshot** | Screenshot seluruh desktop |
| **🎮 Roblox Studio** | Baca hierarchy, inspect/edit properti, visual inspect via bridge plugin |
| **🎨 ComfyUI** | Generate gambar via ComfyUI lokal |
| **🐙 GitHub CLI** | Cek auth, repo list/view/clone, SSH key management |
| **🔐 Credential Diagnostics** | Periksa token & SSH key tanpa mengekspos isinya |

## 🏗️ Arsitektur

```
AI Agent (Hermes, Claude Code, dll)
  │
  └── MCP stdio
        │
        └── jenny_mcp_server.py
              │
              ├── approval_store.py    ← sistem approval manual
              ├── jenny_privileged_tools.py  ← tools berisiko (approval-only)
              │
              └── C:\AI-Agent\tools\   ← modul Python eksternal
                    ├── cli_*.py
                    ├── brave_browser_tool.py
                    ├── web_search_tool.py
                    └── ...
```

## 🚀 Instalasi

```powershell
# 1. Install MCP SDK
py -m pip install "mcp[cli]"

# 2. Clone/extract ke C:\AI-Agent\mcp
# 3. Pastikan tools ada di C:\AI-Agent\tools

# 4. Tes server
cd C:\AI-Agent\mcp
py jenny_mcp_server.py

# 5. Tes interaktif dengan MCP Inspector
npx -y @modelcontextprotocol/inspector ^
  py C:\AI-Agent\mcp\jenny_mcp_server.py
```

## 🔌 Konfigurasi Hermes Agent

Masukkan ini ke `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  jenny_tools:
    command: "py"
    args:
      - "C:\\AI-Agent\\mcp\\jenny_mcp_server.py"
    env:
      JENNY_TOOLS_DIR: "C:\\AI-Agent\\tools"
      JENNY_MCP_LOG_DIR: "C:\\AI-Agent\\logs"
      JENNY_APPROVAL_DIR: "C:\\AI-Agent\\approvals"
      JENNY_SHELL_ROOT: "C:\\AI-Agent"
    enabled: true
    timeout: 900
```

Lalu restart Hermes atau jalankan `/reload-mcp`.

## 🛡️ Sistem Keamanan

- **Approval manual** — tindakan berisiko (hapus file, edit script, push GitHub) memerlukan persetujuan manual via `approve_mcp_action.py`
- **Tanpa hardcoded credential** — semua API key/token dibaca dari environment variable
- **Executable allowlist** — shell execution hanya untuk binary yang diizinkan
- **Parallel calls disabled** — karena banyak tool mengontrol GUI/clipboard/browser

## 🎮 Roblox Studio Integration

Membutuhkan bridge plugin yang berjalan di Roblox Studio:

```powershell
cd C:\AI-Agent\tools
py cli_roblox_studio.py serve
```

Plugin tersedia di: `C:\Users\<user>\AppData\Local\Roblox\Plugins\JennyRobloxBridge.rbxmx`

## 🔧 Environment Variables

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| `JENNY_TOOLS_DIR` | `C:\AI-Agent\tools` | Direktori modul tool Python |
| `JENNY_MCP_LOG_DIR` | `C:\AI-Agent\logs` | Direktori log server |
| `JENNY_APPROVAL_DIR` | `C:\AI-Agent\approvals` | Direktori ticket approval |
| `JENNY_SHELL_ROOT` | `C:\AI-Agent` | Root untuk eksekusi shell |
| `ROBLOX_OPEN_CLOUD_API_KEY` | — | API key untuk publish Roblox place |

## 📋 Tool Prefix

Semua tool diregistrasi dengan prefix `mcp_jenny_tools_`:

| Tool MCP | Fungsi |
|----------|--------|
| `mcp_jenny_tools_system_status` | Status semua modul |
| `mcp_jenny_tools_web_search` | Cari web |
| `mcp_jenny_tools_brave_open` | Buka URL di Brave |
| `mcp_jenny_tools_roblox_hierarchy` | Baca hierarchy Studio |
| `mcp_jenny_tools_comfy_generate` | Generate gambar |
| `mcp_jenny_tools_document_read` | Baca DOCX/XLSX/PDF |
| ...dan 30+ tool lainnya | |

## 📁 Struktur Folder

```
C:\AI-Agent\mcp\
├── jenny_mcp_server.py          ← Main MCP server
├── jenny_mcp_common.py          ← Utility & availability check
├── jenny_privileged_tools.py    ← High-risk tools
├── approval_store.py            ← Approval ticket system
├── approve_mcp_action.py        ← CLI approval tool
├── README_SETUP.md              ← Setup instructions (original)
├── hermes_config_snippet.yaml   ← Contoh config YAML
├── install_mcp.ps1              ← Instalasi script
├── requirements.txt             ← Dependency (mcp[cli])
└── .gitignore
```

## 📜 Lisensi

MIT — Silakan gunakan, modifikasi, dan distribusikan.

---

Dibuat dengan ☕ oleh **RhaDar12**
