# ============================================================
# ADIVA - Start Script (VS Code integrated terminals)
# Prefers the current VS Code window and triggers the existing
# workspace task that opens backend + frontend terminals.
#
# Recommended fallback: press Ctrl+Shift+B in the current
# VS Code session.
# ============================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ADIVA - Starting Application" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] The 'code' CLI is not on PATH." -ForegroundColor Yellow
    Write-Host "       Press Ctrl+Shift+B in the current VS Code window." -ForegroundColor Yellow
    Write-Host "       That runs .vscode/tasks.json -> 'ADIVA: Start All'." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "       To enable the CLI: open VS Code -> Ctrl+Shift+P ->" -ForegroundColor Yellow
    Write-Host "       'Shell Command: Install code command in PATH'" -ForegroundColor Yellow
    exit 0
}

Write-Host "Using VS Code CLI to trigger the workspace task ..." -ForegroundColor Green
Write-Host ""

code --reuse-window "$ROOT" `
  --execute-command "workbench.action.tasks.runTask" `
  --args "ADIVA: Start All" 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[INFO] Could not auto-trigger the task in the current window." -ForegroundColor Yellow
    Write-Host "       Press Ctrl+Shift+B in this VS Code session." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  Requested 'ADIVA: Start All' in the current VS Code window." -ForegroundColor Cyan
    Write-Host "  Backend  -> http://localhost:8000"
    Write-Host "  Frontend -> http://localhost:5173"
    Write-Host "======================================" -ForegroundColor Cyan
}

Write-Host ""
