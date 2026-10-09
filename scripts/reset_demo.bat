@echo off
echo ============================================
echo  Campus Intelligence - Reset Demo Data
echo ============================================
cd /d "%~dp0..\backend"

call .venv\Scripts\activate.bat

echo Deleting campus.db...
if exist "campus.db" del campus.db

echo Re-seeding database...
python -m app.seed.seed_all

echo Done! Restart the backend server.
