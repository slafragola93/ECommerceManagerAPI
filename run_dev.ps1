# Development server runner for ECommerceManagerAPI
# Run this to start the development server

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  ECommerceManagerAPI - Development Server" -ForegroundColor Cyan
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
    Write-Host "    Run 'python -m venv venv' to create one" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting development server..." -ForegroundColor Yellow
Write-Host "Server will be available at: http://0.0.0.0:8000" -ForegroundColor Green
Write-Host "API docs available at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press CTRL+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Run uvicorn with correct parameters
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000


