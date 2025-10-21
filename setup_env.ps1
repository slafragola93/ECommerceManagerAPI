# Setup script for ECommerceManagerAPI
# Run this before starting development: .\setup_env.ps1

# Set PYTHONPATH to project root
$env:PYTHONPATH = $PSScriptRoot
Write-Host "PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Green

# Activate virtual environment if it exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Run 'python -m venv venv' to create one." -ForegroundColor Red
}

Write-Host "Environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run:" -ForegroundColor Cyan
Write-Host "  - .\run_dev.ps1  (to run the API in development mode)" -ForegroundColor Green
Write-Host "  - uvicorn src.main:app --reload --host 0.0.0.0 --port 8000  (manual start)" -ForegroundColor Cyan
Write-Host "  - pytest  (to run tests)" -ForegroundColor Cyan
Write-Host "  - python scripts/yourscript.py  (to run scripts)" -ForegroundColor Cyan

