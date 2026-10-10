# Brain-SSD

[Pesquisa Brain-SSD × Neurociência (10/10/2026)](docs/NEUROCIENCIA_AUDITORIA_2026-10-10.md) — comparativo científico, lacunas e módulo de memória episódica experimental.

**Auditoria e próximas prioridades:** [Reavaliação geral (10/10/2026)](docs/AUDITORIA_GERAL_2026-10-10.md)

## Objetivo 1: Chat visual no Windows

Para conversar com a IA local, abra **INICIAR-CHAT-WINDOWS.bat** e digite
**Olá** no chat em http://127.0.0.1:8766. A resposta vem do Qwen local,
rodando via CPU. Consulte [o guia de instalação e limitações](docs/CHAT_WINDOWS.md).

O launcher .NET também tem opção de Chat no código-fonte, mas o executável
versionado precisa ser recompilado para recebê-la.


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
## Atualização do chat Windows
O primeiro marco tem três perfis (economia, equilibrado, rapido),
opera sem o corpus SSD opcional e mostra se a primeira inferência real
foi validada. O launcher Windows é compilado em uma GitHub Action separada.
Para testar uma pergunta verdadeira localmente, execute:

    python tools/validate_chat_windows.py --profile economia

O CI simula o Core e não prova qualidade nem inferência com o GGUF.

## Chat incremental e interrupção

O chat exibe progressivamente o texto emitido pelo Core e dispõe do botão **Parar**.
O backend encerra a geração e não salva respostas interrompidas. O histórico
permanece somente no SQLite local. Consulte [CHAT_WINDOWS.md](docs/CHAT_WINDOWS.md).
O CI valida o protocolo com backends de teste e encerramento real de processos,
mas não possui o modelo Qwen; ainda falta um teste completo no Windows do usuário.

### Laboratório cognitivo experimental

Atenção e memória de trabalho compacta, associação episódica, replay somente leitura,
plasticidade de metadados reversível, erro de previsão e percepção–ação simulada:
consulte [COGNITIVE_LAB.md](docs/COGNITIVE_LAB.md) e execute
`python tools/run_cognitive_lab.py`. Esses módulos não reescrevem o Qwen e
não equivalem a neurônios ou transferência de consciência.
