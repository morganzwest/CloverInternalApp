@echo off
echo Setting up your environment...

:: === BACKEND SETUP ===
echo Installing Python dependencies...
cd backend
pip install -r requirements.txt

echo Starting FastAPI backend...
start cmd /k "uvicorn app.main:app --reload"
pause
