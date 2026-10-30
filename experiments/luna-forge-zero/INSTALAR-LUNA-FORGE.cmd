@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR-LUNA-FORGE-WINDOWS.ps1" %*
set "LUNA_RC=%errorlevel%"
if not "%LUNA_RC%"=="0" (
  echo.
  echo O instalador nao concluiu. Copie o erro exibido acima.
  pause
)
exit /b %LUNA_RC%
