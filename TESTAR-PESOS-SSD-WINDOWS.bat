@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo Nao foi possivel localizar a pasta do Brain-SSD.
  exit /b 1
)

set "PYTHON=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 (
  set "PYTHON=python"
  python --version >nul 2>&1
  if errorlevel 1 (
    echo Python nao foi encontrado. Instale Python 3.11 ou superior.
    exit /b 1
  )
)

echo.
echo ===============================================
echo Brain-SSD / Laboratorio de streaming SSD - RAM
echo ===============================================
echo Sem GPU, sem Qwen em execucao e sem alterar GGUF.
echo Usa um arquivo temporario de 16 MiB.
echo Este teste NAO mede tokens por segundo.
echo.

%PYTHON% -m unittest discover -s tests -p "test_weight_streaming_lab.py" -v
if errorlevel 1 goto :error

if not exist "results\weight_lab" mkdir "results\weight_lab"
if errorlevel 1 goto :error

echo.
echo [1/2] Janelas estilo MoE sintetico
%PYTHON% tools\bench_weight_streaming.py --matrix --fixture-mib 16 --page-kib 256 --pages 64 --budget-mib 4 --turns 32 --pattern moe --output "results\weight_lab\moe.json"
if errorlevel 1 goto :error

echo.
echo [2/2] Janelas estilo DENSO sintetico
%PYTHON% tools\bench_weight_streaming.py --matrix --fixture-mib 16 --page-kib 256 --pages 64 --budget-mib 4 --turns 12 --pattern dense --output "results\weight_lab\dense.json"
if errorlevel 1 goto :error

echo.
echo Experimento concluido. Relatorios:
echo results\weight_lab\moe.json
echo results\weight_lab\dense.json
echo Compare checksum_sink, cache, RSS, CPU e latencia.
echo Estes resultados NAO comprovam inferencia Qwen.
exit /b 0

:error
echo.
echo O teste parou devido a um erro. Nao o considere aprovado.
exit /b 1
