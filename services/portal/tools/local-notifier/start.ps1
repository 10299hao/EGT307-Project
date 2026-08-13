$ErrorActionPreference = "Stop"
$receiverFolder = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = [System.IO.Path]::GetFullPath((Join-Path $receiverFolder "..\..\backend\.venv\Scripts\python.exe"))
if (-not (Test-Path $python)) {
    throw "Portal backend environment was not found. Create services/portal/backend/.venv first."
}
Set-Location $receiverFolder
& $python -m uvicorn app:app --host 0.0.0.0 --port 8090
