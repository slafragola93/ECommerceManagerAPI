# Quick Start Guide

## 🚀 First Time Setup

1. **Clone the repository** (if you haven't already)
   ```powershell
   git clone <repo-url>
   cd ECommerceManagerAPI
   ```

2. **Create virtual environment**
   ```powershell
   python -m venv venv
   ```

3. **Activate and setup environment**
   ```powershell
   .\setup_env.ps1
   ```

4. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Copy environment file**
   ```powershell
   copy env.example .env
   # Edit .env with your configuration
   ```

## 🏃 Running the Application

### Quick Start (Recommended)
```powershell
.\run_dev.ps1
```

This will:
- Set up the Python path automatically
- Activate the virtual environment
- Start the development server with hot reload
- Server runs at: http://localhost:8000
- API docs at: http://localhost:8000/docs

### Manual Start
```powershell
# Set environment
.\setup_env.ps1

# Run server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```powershell
.\run_prod.ps1
```

## 🧪 Running Tests

```powershell
# All tests
pytest

# Specific test file
pytest test/routers/test_product.py

# With coverage report
pytest --cov=src --cov-report=html
```

## 📝 Common Commands

| Command | Description |
|---------|-------------|
| `.\run_dev.ps1` | Start development server |
| `.\run_prod.ps1` | Start production server |
| `.\setup_env.ps1` | Set up environment variables |
| `pytest` | Run all tests |
| `pytest -v` | Run tests with verbose output |
| `python scripts/create_fixtures.py` | Create test fixtures |
| `python scripts/warm_cache.py` | Warm up cache |

## 🐛 Troubleshooting

### ModuleNotFoundError: No module named 'src'

**Solution 1:** Run the setup script
```powershell
.\setup_env.ps1
```

**Solution 2:** Use the correct uvicorn command
```powershell
# ✅ Correct
uvicorn src.main:app --reload

# ❌ Wrong
uvicorn main:application --reload --app-dir src
```

**Solution 3:** Set PYTHONPATH manually
```powershell
$env:PYTHONPATH = (Get-Location).Path
```

### VSCode Not Finding Imports

1. Reload VSCode window (Ctrl+Shift+P → "Reload Window")
2. Check `.vscode/settings.json` has correct Python path settings
3. Restart the integrated terminal

### Port Already in Use

```powershell
# Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health/cache

## 🔧 Development Workflow

1. Start the dev server: `.\run_dev.ps1`
2. Make your changes
3. The server auto-reloads on file changes
4. Test your changes: `pytest`
5. Commit when ready

## 📖 More Information

- **Full Python Path Setup:** See `PYTHON_PATH_SETUP.md`
- **Architecture:** See `ARCHITETTURA_SOLID_DOCUMENTATION.md`
- **Cache Design:** See `CACHE_DESIGN.md`
- **Setup Guide:** See `SETUP_INIZIALE.md`


