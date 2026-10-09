@echo off
echo ============================================
echo  Campus Intelligence - Frontend Server
echo ============================================
cd /d "%~dp0..\frontend"

if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)

echo Starting frontend on port 5173...
npm run dev
