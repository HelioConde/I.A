@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Luna - Brain-SSD Windows
if not exist "tools\launch_luna.py" (
  echo ERRO: iniciador da Luna nao encontrado nesta pasta.
  pause
  exit /b 2
)
set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (set "PYTHON_CMD=py -3.11") else (set "PYTHON_CMD=py -3")
  )
)
%PYTHON_CMD% --version
if errorlevel 1 (
  echo Python 3.11+ nao encontrado.
  pause
  exit /b 3
)
echo.
echo =====================================================
echo LUNA / BRAIN-SSD  -  Configuracao persistente INI
echo =====================================================
echo As preferencias sao lidas de LUNA.ini na raiz do projeto.
echo Na primeira execucao, o arquivo e criado automaticamente.
echo Para alterar permissoes ou pastas, edite o LUNA.ini.
echo Captura, edicao e execucao ainda exigem confirmacao na interface.
echo.
%PYTHON_CMD% "tools\launch_luna.py" --run
set "LUNA_EXIT=%ERRORLEVEL%"
if "%LUNA_EXIT%"=="3" (
  echo.
  echo Modelo ou runtime ausente. Abrindo instalador principal...
  call "%~dp0INICIAR-BRAIN-SSD.bat"
)
if not "%LUNA_EXIT%"=="0" (
  echo.
  echo Luna nao iniciou ou foi encerrada com erro %LUNA_EXIT%.
  echo Configure o arquivo LUNA.ini e execute novamente.
  pause
)
endlocal
