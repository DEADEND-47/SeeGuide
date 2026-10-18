# SeeGuide Environment Setup Script for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Setting up SeeGuide Environment (Windows PowerShell)..." -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan

$pythonCmd = "python"

Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
& $pythonCmd -m venv .venv

Write-Host "[*] Upgrading pip in .venv..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "[*] Installing pinned requirements from requirements.txt..." -ForegroundColor Yellow
& .\.venv\Scripts\pip.exe install -r requirements.txt

Write-Host "[*] Running environment verification..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe scripts\check_environment.py

Write-Host "[*] Running contract validation..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe scripts\validate_contracts.py

Write-Host "====================================================================" -ForegroundColor Green
Write-Host "SeeGuide setup complete! Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
