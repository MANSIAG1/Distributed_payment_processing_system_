# FastAPI Frontend Startup Script for Distributed Payment System
# This script starts the FastAPI web interface

Write-Host "=" * 60
Write-Host "  Distributed Payment System - Web Frontend  " -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host ""

# Check if we're in the correct directory
if (-not (Test-Path "frontend/main.py")) {
    Write-Host "Error: Please run this script from the project root directory" -ForegroundColor Red
    Write-Host "Current directory: $PWD"
    exit 1
}

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.7+ and add it to PATH." -ForegroundColor Red
    exit 1
}

# Check if required dependencies are installed
Write-Host "Checking dependencies..."
$dependencies = @("fastapi", "uvicorn", "jinja2", "python-multipart")
$missing = @()

foreach ($dep in $dependencies) {
    try {
        $result = python -c "import $dep" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ $dep installed" -ForegroundColor Green
        } else {
            $missing += $dep
        }
    } catch {
        $missing += $dep
    }
}

if ($missing.Count -gt 0) {
    Write-Host "✗ Missing dependencies: $($missing -join ', ')" -ForegroundColor Red
    Write-Host ""
    Write-Host "Installing missing dependencies..." -ForegroundColor Yellow
    pip install $($missing -join ' ')
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to install dependencies. Please run: pip install -r requirements.txt" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "🚀 Starting FastAPI Frontend Server..." -ForegroundColor Green
Write-Host ""
Write-Host "The web interface will be available at:" -ForegroundColor Yellow
Write-Host "  • http://localhost:8000       (Main interface)" -ForegroundColor White
Write-Host "  • http://localhost:8000/docs  (API documentation)" -ForegroundColor White
Write-Host ""
Write-Host "Make sure your backend nodes are running first:" -ForegroundColor Yellow
Write-Host "  • Node 1: localhost:50051" -ForegroundColor White
Write-Host "  • Node 2: localhost:50052" -ForegroundColor White  
Write-Host "  • Node 3: localhost:50053" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host "=" * 60
Write-Host ""

# Start the FastAPI server
python frontend/main.py
