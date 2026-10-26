# RevenueRescue AI - Local frontend startup
# Run from repo root: .\start_frontend.ps1

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  RevenueRescue AI - Frontend" -ForegroundColor Cyan
Write-Host "  URL: http://localhost:3000"
Write-Host ""

Set-Location "$PSScriptRoot\frontend"
npm run dev
