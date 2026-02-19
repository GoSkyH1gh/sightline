@echo off
:: Set UTF-8 encoding for the terminal
chcp 65001 > nul

echo.
echo ==========================================
echo    Sightline - Startup Script
echo ==========================================
echo.

:: Check for backend folder
if not exist "backend" (
    echo [!] Error: backend folder not found.
    pause
    exit /b
)

:: Check for frontend folder
if not exist "frontend" (
    echo [!] Error: frontend folder not found.
    pause
    exit /b
)

echo [+] Launching Backend (uv run fastapi)...
start "Sightline Backend" cmd /k "cd backend && uv run fastapi dev"

echo [+] Launching Frontend (pnpm dev)...
start "Sightline Frontend" cmd /k "cd frontend && pnpm dev"

echo.
echo ------------------------------------------
echo    Services are starting in separate windows.
echo    - Backend: http://localhost:8000
echo    - Frontend: http://localhost:5173
echo.
echo    Close the separate windows to stop services.
echo ------------------------------------------
echo.
