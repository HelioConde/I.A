@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Luna - instalar e usar Qwen3-4B Q8_0
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD set "PYTHON_CMD=python"
echo =========================================================
echo LUNA - INSTALAR E USAR QWEN3-4B Q8_0
echo =========================================================
echo Modelo oficial: aprox. 4.28 GB, exige conexao para download.
echo Instalacao sera verificada por SHA-256 e cabecalho GGUF.
echo Qwen3-0.6B e todas as permissoes do LUNA.ini serao preservados.
echo Feche a Luna anterior antes de iniciar esta versao.
echo =========================================================
%PYTHON_CMD% "tools\usar_qwen4b_luna.py" --install-activate
if errorlevel 1 (
  echo.
  echo ERRO: modelo novo NAO foi ativado. Confira a mensagem acima.
  echo Para reverter: py -3 tools\usar_qwen4b_luna.py --restore-06b
  pause
  exit /b 2
)
echo.
echo Modelo 4B selecionado. Iniciando a Luna...
call "%~dp0INICIAR-COPILOTO-WINDOWS.bat"
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
