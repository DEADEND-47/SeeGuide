# SeeGuide Server Execution Script for Windows PowerShell
$ErrorActionPreference = "Stop"

$hostAddr = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$port = if ($env:PORT) { $env:PORT } else { "8000" }

$pythonCmd = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "Starting SeeGuide server on ${hostAddr}:${port}..." -ForegroundColor Cyan
& $pythonCmd -m uvicorn server.main:app --host $hostAddr --port $port --reload
