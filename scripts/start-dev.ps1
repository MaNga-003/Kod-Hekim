# KodHekim yerel geliştirme — backend + frontend
# Not: backend'de --reload kullanılmaz; klon temp'e yazılır ama reload job store'u siler.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend on http://127.0.0.1:8001 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; python -m uvicorn main:app --host 127.0.0.1 --port 8001"
) | Out-Null

Start-Sleep -Seconds 2

Write-Host "Starting frontend on http://localhost:3000 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\frontend'; npm run dev"
) | Out-Null

Write-Host "Done. Open http://localhost:3000"
