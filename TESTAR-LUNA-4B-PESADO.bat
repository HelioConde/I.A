@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title LUNA - teste pesado do Qwen3-4B Q8_0
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD set "PYTHON_CMD=python"
echo.
echo =============================================================
echo     LUNA / STRESS TEST QWEN3-4B Q8_0 - CPU / WINDOWS
echo =============================================================
echo 24 perguntas de inferencia real, uma de cada vez.
echo Ha protecao de RAM, tempo e timeout; pode durar mais de 1 hora.
echo Este teste NAO usa microfone nem testa ligacao full-duplex.
echo Nao altera GGUF nem LUNA.ini. Nao faz downloads ou pesquisa web.
echo Feche a Luna antes de iniciar para liberar RAM.
echo Para cancelar: Ctrl+C.
echo.
%PYTHON_CMD% --version
if errorlevel 1 goto :fail
echo.
echo [1/6] Verificando contratos do orquestrador...
%PYTHON_CMD% -m unittest discover -s tests -p "test_stress_luna_qwen4b.py" -v
if errorlevel 1 goto :fail
echo.
echo [2/6] Verificando integridade do seletor de modelos...
%PYTHON_CMD% -m unittest discover -s tests -p "test_usar_qwen4b_luna.py" -v
if errorlevel 1 goto :fail
echo.
echo [3/6] Testando 1000 turnos simulados do orquestrador...
%PYTHON_CMD% "tools\stress_luna_qwen4b.py" --simulate --turns 1000 --tokens 48
if errorlevel 1 goto :fail
echo.
echo [4/6] Testando estados de ligacao por voz (sem mic fisico)...
where node >nul 2>nul
if errorlevel 1 (
  echo AVISO: Node.js ausente; estados da ligacao nao foram testados.
) else (
  node --test "tests\test_luna_call_state.cjs"
  if errorlevel 1 goto :fail
)
echo.
echo [5/6] Verificando GGUF e RAM (sem iniciar inferencia)...
%PYTHON_CMD% "tools\stress_luna_qwen4b.py" --check
if errorlevel 1 goto :fail
echo.
echo [6/6] Iniciando inferencia longa; relatorios em results\model_comparison\
%PYTHON_CMD% "tools\stress_luna_qwen4b.py" --real --turns 24 --tokens 96 --core-mode auto --max-minutes 90 --per-turn-seconds 360
if errorlevel 1 goto :fail
echo.
echo TESTE REAL CONCLUIDO. Confira o JSON com data em results\model_comparison\
endlocal & exit /b 0
:fail
echo.
echo O teste nao foi aprovado ou nao pode ser executado.
echo Confira a mensagem acima e o relatorio parcial.
pause
endlocal & exit /b 2
