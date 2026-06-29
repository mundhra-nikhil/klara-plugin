@echo off
echo Starting Klara Backend Deployment...

echo 1. Checking Python Environment...
python -m pip install -r requirements.txt

echo 2. Running Database Migrations...
python -m alembic upgrade head
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Alembic migrations failed!
    exit /b %ERRORLEVEL%
)

echo 3. Deployment Scripts Finished!
