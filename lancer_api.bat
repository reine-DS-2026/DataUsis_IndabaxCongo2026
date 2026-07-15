@echo off
cd /d "%~dp0"
echo Demarrage de l'API ACPE Matcher (optionnel, pour les chercheurs)...
echo Documentation : http://localhost:8000/docs
echo.
py -m uvicorn api.main:app --port 8000
pause
