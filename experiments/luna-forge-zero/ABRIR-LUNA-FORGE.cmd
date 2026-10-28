@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
 echo Luna Forge ainda nao foi instalada.
 echo Execute INSTALAR-LUNA-FORGE.cmd antes.
 pause
 exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0luna_local.py"
if errorlevel 1 pause
