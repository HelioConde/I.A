@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul || (echo Python launcher nao encontrado.& exit /b 2)

echo [1/3] Testes V0 e leitor GGUF V1 (fixtures sinteticos)
py -3 -m unittest discover -s tests -p "test_weight_streaming_lab.py" -v || exit /b 1
py -3 -m unittest discover -s tests -p "test_gguf_inspector.py" -v || exit /b 1

echo [2/3] Matriz V0 de I/O em fixture temporario
if not exist "results\weight_lab" mkdir "results\weight_lab"
py -3 tools\bench_weight_streaming.py --matrix --fixture-mib 16 --page-kib 256 --pages 64 --budget-mib 4 --turns 32 --pattern moe --output "results\weight_lab\latest-v0.json" || exit /b 1

echo [3/3] Inspecao opcional, somente leitura, do Qwen local
if exist "models\Qwen3-0.6B-Q8_0.gguf" (
  py -3 tools\inspect_gguf.py "models\Qwen3-0.6B-Q8_0.gguf" --tensor token_embd.weight --window-bytes 64 || exit /b 1
) else (
  echo Modelo Qwen ausente: V1 validado somente com fixtures nesta maquina.
)
echo Concluido. Este laboratorio nao executa inferencia por streaming.
endlocal
