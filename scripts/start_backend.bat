@echo off
echo ============================================
echo  Campus Intelligence - Backend Server
echo ============================================
cd /d "%~dp0..\backend"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

if not exist ".env" (
    echo Generating keys...
    python -m app.seed.gen_keys
)

if not exist "campus.db" (
    echo Seeding database...
    python -m app.seed.seed_all
)

echo Starting backend on port 8000...
uvicorn app.main:app --reload --port 8000
