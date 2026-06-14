$ErrorActionPreference = "Stop"

$Target = "C:\AI-Agent\mcp"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

Copy-Item "$PSScriptRoot\jenny_mcp_server.py" $Target -Force
Copy-Item "$PSScriptRoot\jenny_mcp_common.py" $Target -Force
Copy-Item "$PSScriptRoot\README_SETUP.md" $Target -Force
Copy-Item "$PSScriptRoot\hermes_config_snippet.yaml" $Target -Force
Copy-Item "$PSScriptRoot\requirements.txt" $Target -Force

py -m pip install "mcp[cli]"

Write-Host ""
Write-Host "Jenny Tools MCP berhasil dipasang di $Target"
Write-Host "Tes dengan:"
Write-Host "  py C:\AI-Agent\mcp\jenny_mcp_server.py"
