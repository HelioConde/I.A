@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Brain-SSD - Completo com memoria e pesquisa web
if not exist "tools\auto_setup_chat_windows.py" (
  echo ERRO: Atualize o projeto completo. Faltou tools\auto_setup_chat_windows.py.
  pause
  exit /b 2
)
if not exist "tools\doctor_chat.py" (
  echo ERRO: Instale ou extraia o repositorio inteiro na mesma pasta.
  pause
  exit /b 2
)

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=py -3.11"
    ) else (
      py -3 --version >nul 2>nul
      if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
  )
  if not defined PYTHON_CMD (
    python --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)
if not defined PYTHON_CMD goto :python_missing
%PYTHON_CMD% --version
if errorlevel 1 goto :python_missing
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :python_missing

:menu
cls
echo ==================================================
echo       BRAIN-SSD  -  VERSAO COMPLETA
echo ==================================================
echo.
echo Modelos locais (CPU, GGUF):
echo.
echo [1] Qwen3 0.6B Q8_0   - leve    (~640 MB)
echo [2] Qwen3 1.7B Q4_K_M - medio   (~1,28 GB)
echo [3] Qwen3 4B Q4_K_M   - maior qualidade (~2,5 GB)
echo.
echo O instalador baixa APENAS o que estiver faltando:
echo - Modelo selecionado, com SHA-256 verificado;
echo - llama.cpp oficial CPU x64, se ausente.
echo.
echo Recursos ativados automaticamente:
echo - Memoria de conversas e aprendizado local;
echo - Pesquisa web auto - Wikipedia e noticias Brasil;
echo - Conhecimento pesquisado persistente em SQLite;
echo - Diagnosticos e analise cognitiva em modo shadow.
echo.
echo A INTERNET SO E CONSULTADA COM AUTORIZACAO
echo PARA CADA PERGUNTA NO NAVEGADOR.
echo.
echo Nada substitui os modelos anteriores nem apaga
echo conversas, memorias ou arquivos do SSD.
echo Para modelos maiores, confira sua RAM e espaco livre.
echo.
choice /C 123 /N /M "Selecione 1, 2 ou 3: "
if errorlevel 3 goto :model4b
if errorlevel 2 goto :model17
set "MODEL=0.6b"
set "PROFILE=economia"
goto :run
:model17
set "MODEL=1.7b"
set "PROFILE=equilibrado"
goto :run
:model4b
set "MODEL=4b"
set "PROFILE=equilibrado"
:run
echo.
echo Preparando o ambiente, se necessario.
echo Na primeira execucao o download pode demorar.
%PYTHON_CMD% "tools\auto_setup_chat_windows.py" --model %MODEL% --profile %PROFILE% --web
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Nao foi possivel concluir. Veja a mensagem acima.
  echo Historico, modelos anteriores e memorias foram preservados.
  pause
)
endlocal & exit /b %EXIT_CODE%

:python_missing
echo.
echo Python 3.11+ nao encontrado.
echo O instalador pode solicitar o Python oficial via winget.
where winget >nul 2>nul
if errorlevel 1 goto :manual_python
choice /C SN /N /M "Autorizar instalacao do Python 3.11 pelo winget [S/N]: "
if errorlevel 2 goto :manual_python
winget install --id Python.Python.3.11 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :manual_python
echo.
echo Python instalado. Feche esta janela e execute o .bat novamente
echo para atualizar os caminhos do Windows.
pause
endlocal & exit /b 0
:manual_python
echo Instale Python 3.11 ou mais novo em https://www.python.org/downloads/windows/
echo Depois execute este .bat novamente.
pause
endlocal & exit /b 3
