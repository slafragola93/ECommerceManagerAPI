# Production server runner for ECommerceManagerAPI
# Run this to start the production server

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  ECommerceManagerAPI - Production Server" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Set PYTHONPATH to project root
$env:PYTHONPATH = $PSScriptRoot
Write-Host "[✓] PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Green

# Check if virtual environment exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[✓] Activating virtual environment..." -ForegroundColor Green
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "[!] Warning: Virtual environment not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting production server..." -ForegroundColor Yellow
Write-Host "Server will be available at: http://0.0.0.0:8000" -ForegroundColor Green
Write-Host ""

# Run uvicorn with production settings (no reload, multiple workers)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4


