# RevenueRescue AI - Local backend startup
# Run from repo root: .\start_backend.ps1

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path "$PSScriptRoot\.env") {
    Get-Content "$PSScriptRoot\.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $name = $parts[0].Trim()
            $val = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $val, "Process")
        }
    }
}

$env:PYTHONPATH = "$PSScriptRoot;$PSScriptRoot\backend"

Write-Host ""
Write-Host "  RevenueRescue AI - Backend" -ForegroundColor Cyan
Write-Host "  API:       http://localhost:8000"
Write-Host "  Docs:      http://localhost:8000/docs"
Write-Host "  Provider:  $($env:PAYMENT_PROVIDER)"
Write-Host ""

Set-Location "$PSScriptRoot\backend"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "$PSScriptRoot\backend"
