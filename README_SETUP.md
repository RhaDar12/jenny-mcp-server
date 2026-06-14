# Jenny Tools MCP Server v1

Server MCP lokal ini membungkus tools Python yang sudah berada di:

```text
C:\AI-Agent\tools
```

Arsitektur:

```text
Hermes
→ MCP stdio
→ jenny_mcp_server.py
→ modul tools Python lama
→ Windows / Brave / GitHub / Roblox Studio
```

MCP server tidak menyalin ulang logika tool. Ia mengimpor fungsi Python lama secara langsung.

## File

```text
C:\AI-Agent\mcp\
├── jenny_mcp_server.py
├── jenny_mcp_common.py
├── requirements.txt
├── hermes_config_snippet.yaml
└── README_SETUP.md
```

## 1. Install MCP SDK

```powershell
py -m pip install "mcp[cli]"
```

Tools lama tetap membutuhkan dependency masing-masing yang sebelumnya sudah dipasang.

## 2. Salin package

Ekstrak isi ZIP ke:

```text
C:\AI-Agent\mcp
```

Pastikan tools lama tetap berada di:

```text
C:\AI-Agent\tools
```

## 3. Tes server

Server stdio memang akan terlihat diam karena menunggu MCP client.

```powershell
cd C:\AI-Agent\mcp
py jenny_mcp_server.py
```

Hentikan dengan `Ctrl+C`.

Untuk pengujian interaktif gunakan MCP Inspector:

```powershell
npx -y @modelcontextprotocol/inspector `
  py C:\AI-Agent\mcp\jenny_mcp_server.py
```

Di Inspector, panggil:

```text
system_status
```

## 4. Hubungkan ke Hermes

Tambahkan isi `hermes_config_snippet.yaml` ke config Hermes pada root `mcp_servers`.

Setelah disimpan, restart Hermes atau jalankan:

```text
/reload-mcp
```

Tool akan didaftarkan dengan prefix:

```text
mcp_jenny_tools_
```

Contoh:

```text
mcp_jenny_tools_document_read
mcp_jenny_tools_roblox_visual_selection
```

## 5. Keamanan stdio

Jangan memakai `print()` ke stdout dalam server MCP. Stdout dipakai untuk JSON-RPC MCP. Server ini mengarahkan print dari tool lama ke stderr dan file log:

```text
C:\AI-Agent\logs\jenny_mcp.log
```

Hermes config mengatur:

```yaml
supports_parallel_tool_calls: false
```

Ini penting karena beberapa tool mengontrol GUI, clipboard, browser, atau Roblox Studio.

## 6. Konfirmasi tindakan

Tool yang mengubah keadaan memiliki parameter:

```text
confirm
```

Contoh:

```json
{
  "path": "Workspace/Gate",
  "properties": {
    "Transparency": 0.25
  },
  "confirm": true
}
```

`confirm=true` hanya boleh dipakai setelah pengguna menyetujui tindakan.

Tindakan yang belum diekspos:

```text
hapus Instance Roblox
edit/overwrite Script Roblox
publish Roblox place
push GitHub otomatis
hapus repository
print token GitHub
baca private SSH key
eksekusi shell bebas
```

## 7. Roblox Studio

Bridge Roblox tetap harus berjalan pada terminal tersendiri:

```powershell
cd C:\AI-Agent\tools
py cli_roblox_studio.py serve
```

Kemudian MCP dapat memanggil:

```text
roblox_health
roblox_hierarchy
roblox_selection
roblox_visual_inspect
roblox_visual_selection
roblox_set_properties
```

## 8. Browser utama

Mode `cdp` membutuhkan Brave dijalankan dengan remote debugging port 9222 sesuai setup sebelumnya. Profil Jenny dapat memakai mode `persistent`.

## 9. Environment opsional

```text
JENNY_TOOLS_DIR
JENNY_MCP_LOG_DIR
```

Contoh Hermes env:

```yaml
env:
  JENNY_TOOLS_DIR: "C:\\AI-Agent\\tools"
  JENNY_MCP_LOG_DIR: "C:\\AI-Agent\\logs"
```
