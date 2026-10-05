@echo off
title Smart MedTrack - Running...
color 0B

echo =====================================================================
echo                SMART MEDTRACK LAUNCHER
echo      Automated Medication Adherence and Inventory System
echo =====================================================================
echo.

:: 1. Navigate to script directory
cd /d "%~dp0"

:: 2. Check Virtual Environment
if not exist .venv\Scripts\python.exe (
    echo [*] Virtual environment not found. Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Ensure Python is installed.
        pause
        exit /b 1
    )
    echo [*] Installing dependencies from requirements.txt...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    echo [OK] Python virtual environment ready.
)

:: 3. Optional: check if user passed "docker" argument
if /i "%1"=="docker" (
    echo [*] Docker Stack Mode requested.
    docker compose up -d
    start "Smart MedTrack - Celery Worker" cmd /k "title Smart MedTrack - Celery Worker && color 0A && cd /d %~dp0 && .venv\Scripts\activate.bat && celery -A core worker -l info -P solo"
    start "Smart MedTrack - Celery Beat" cmd /k "title Smart MedTrack - Celery Beat && color 0D && cd /d %~dp0 && .venv\Scripts\activate.bat && celery -A core beat -l info"
)

echo.
echo [*] Applying database migrations...
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 (
    echo [ERROR] Database migration failed.
    pause
    exit /b 1
)

:: 4. Check if demo users exist; if not, seed database
echo [*] Checking database seed status...
.venv\Scripts\python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth.models import User; exit(0 if User.objects.filter(username='patient1').exists() else 1)" >nul 2>nul
if errorlevel 1 (
    echo [*] Demo data not found. Seeding initial patients, regimens, and inventory...
    .venv\Scripts\python.exe manage.py seed_db
) else (
    echo [OK] Database is already initialized with demo patient accounts.
)

echo.
echo =====================================================================
echo   [OK] SYSTEM READY!
echo.
echo   Demo Login Accounts:
echo     - Username: patient1    Password: medtrack123   (Ramesh Patel - IST)
echo     - Username: patient2    Password: medtrack123   (Sarah Johnson - EST)
echo.
echo   Web Application: http://127.0.0.1:8000/
echo   Admin Panel:     http://127.0.0.1:8000/admin/
echo =====================================================================
echo.
echo Starting Django Web Server on http://127.0.0.1:8000/ ...
echo Press CTRL+C to stop the server at any time.
echo.

:: Automatically open default browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000/"

:: Start Django server
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
