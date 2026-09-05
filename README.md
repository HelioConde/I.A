# Brain-SSD

## Execução local no Windows

Abra `dist/windows/BrainSSD.exe` para executar o pipeline real com HUD, usar o terminal ou abrir a pasta para editar. O runtime funcional nativo, CPU-only, está documentado em [docs/WINDOWS_NATIVE_RUNTIME.md](docs/WINDOWS_NATIVE_RUNTIME.md). Ele é classificado como `WINDOWS_NATIVE_FUNCTIONAL` e não substitui a Fase 4E física canônica.

A matriz oficial intermediária de medição está documentada em [docs/PHASE_4EW_WINDOWS_VALIDATION.md](docs/PHASE_4EW_WINDOWS_VALIDATION.md). A primeira matriz completa terminou como `PASS_WITH_WARNINGS`; ela pode ser reproduzida ou inspecionada com `python tools/run_phase4ew_windows_validation.py --dry-run`.

## Visual HUD local

No Windows, o mesmo `BrainSSD.exe` também oferece Demo, Replay da Fase 4D e modo live. O executável é apenas um launcher; todo o código permanece editável e é recarregado na próxima execução. Alternativamente, execute `python tools/run_hud.py --demo`. Veja [docs/VISUAL_HUD.md](docs/VISUAL_HUD.md).

Projeto experimental de arquitetura cognitiva SSD-native. As Fases 1–4D estão preservadas; o primeiro pipeline real end-to-end passou e a Fase 4E de validação física TARGET_8GB permanece como próximo experimento. O HUD é somente observabilidade e não muda essa sequência.

## Comandos locais

```bash
python3 -m unittest discover -s tests -v
python3 tools/hardware_audit.py --output results/hardware.json
PYTHONPATH=src python3 benchmarks/baseline.py --help
```

O benchmark aceita qualquer executável compatível por meio de um backend de processo. A configuração de referência usa `llama-completion`, CPU-only, uma thread e um modelo GGUF fornecido explicitamente. Modelos, builds de terceiros e resultados não são versionados.

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/BENCHMARKS.md](docs/BENCHMARKS.md) e [docs/REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md).
