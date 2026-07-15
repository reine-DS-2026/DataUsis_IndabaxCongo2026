@echo off
cd /d "%~dp0"
echo Demarrage d'ACPE Matcher...
echo.
py -m streamlit run application/main.py
pause
