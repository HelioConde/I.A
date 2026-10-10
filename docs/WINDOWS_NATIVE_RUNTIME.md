# Brain-SSD V0 — runtime funcional nativo no Windows

Este modo executa localmente o pipeline real congelado da Fase 4D: consulta, retrieval, gate, leitura seletiva do cérebro por `mmap`, construção de contexto e Qwen3-0.6B Q8_0 via `llama.cpp` CPU-only. Ele existe para desenvolvimento, demonstração, depuração e uso interativo no Windows.

> **Classificação obrigatória:** `WINDOWS_NATIVE_FUNCTIONAL` / `EXPERIMENTAL_FUNCTIONAL_RUNTIME`. Todo resultado contém `phase4e_valid=false` e `Phase 4E canonical physical baseline requires Debian/Linux environment.` Este modo não substitui nem valida a Fase 4E física canônica.

## Ambiente histórico de pesquisa, não instalação atual

Os caminhos e capacidades descritos abaixo refletem um registro de
um ambiente anterior. Um checkout novo no GitHub **não inclui** GGUF,
executáveis nem corpus SSD. Para preparar o chat com o pacote oficial,
veja `PREPARAR-CHAT-WINDOWS.bat`, separado do Core congelado desta seção.

## O que já está configurado nesta máquina

- Windows 11 x64, Intel Core i5-12400, 6 cores/12 threads e aproximadamente 16 GiB de RAM.
- Modelo em `models/Qwen3-0.6B-Q8_0.gguf`, 639.446.688 bytes, SHA-256 `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
- Fonte congelada do `llama.cpp` no commit `217df17ac30ba2a8c374088772f81926cc5beee3`.
- Executável CPU-only em `third_party/llama.cpp/build-win/bin/llama-completion.exe`.
- Corpus semântico real com 15 páginas de 1 MiB, 12.521 registros e índice real existente.

Nenhum `sudo`, `apt`, WSL, cgroup ou variável Linux é necessário para este modo.

## Início rápido

O atalho principal é `dist/windows/BrainSSD.exe`. Ele oferece o runtime funcional com ou sem HUD, os modos de demonstração/replay e a abertura da pasta para edição manual.

No PowerShell, dentro da raiz do projeto:

```powershell
python tools/setup_windows_runtime.py
python tools/run_local_brain_ssd.py
```

Para executar apenas uma pergunta:

```powershell
python tools/run_local_brain_ssd.py --query "Why can repeated json.dump calls create invalid JSON?" --technical
```

Para acompanhar eventos reais no HUD existente:

```powershell
python tools/run_local_brain_ssd.py --hud
```

O runner inicia o servidor no mesmo processo e abre `http://127.0.0.1:8765/`. Isso é necessário porque o event bus congelado é seguro, limitado e deliberadamente in-process. Use `--no-open-browser` para não abrir o navegador, ou `--hud-port 8766` para trocar a porta.

Na primeira inicialização são executados três smoke tests: uma página real via `mmap` com checksum, uma recuperação conhecida e uma inferência curta no Qwen CPU-only. Depois de um `PASS` confirmado, `--skip-smoke` evita repetir essa etapa no mesmo ambiente.

## Interface interativa

Digite perguntas diretamente. Os comandos locais são:

- `/status`: ambiente, runtime, modelo e estado dos smoke tests;
- `/metrics`: métricas da última inferência;
- `/brain`: retrieval, páginas ativadas, tempos e contexto resumido;
- `/sources`: somente origens e trechos limitados usados no contexto;
- `/clear`: limpa o terminal;
- `/help`: mostra os comandos;
- `/quit`: encerra.

`Ctrl+C` encerra o processo filho do Qwen e fecha o HUD com segurança. O runner não exibe raciocínio interno; o modelo é executado com `--reasoning off` e `/no_think`.

## Componentes preservados

O runtime local não reimplementa nem altera os algoritmos cognitivos. Ele importa e reutiliza diretamente:

- `retrieve` e `RealKnowledgeIndex`;
- `ContextBuilder` e `build_prompt`;
- `MMapStorageBackend` e `touch_view`;
- `LlamaCppBackend` e `GenerationRequest`;
- `BrainEvent`, `BrainEventBus`, `HudRuntime` e o servidor do HUD.

O índice é carregado uma vez por sessão e o arquivo do cérebro permanece mapeado; somente as páginas selecionadas são tocadas e verificadas. O `llama-completion` congelado é um executável single-shot, portanto o processo e o modelo são carregados a cada resposta. Trocar isso por um servidor persistente mudaria a arquitetura de execução e ficou fora do escopo V0.

## Métricas no Windows

| Campo | Estado | Semântica |
|---|---|---|
| Working set / pico | `SUPPORTED` | `GetProcessMemoryInfo`, conjunto residente amostrado do filho `llama.cpp`. |
| Private bytes | `SUPPORTED` | Commit privado amostrado do processo. |
| CPU user/kernel | `SUPPORTED` | `GetProcessTimes`; também são registrados percentuais total e normalizado. |
| Operações e bytes transferidos | `SUPPORTED` | `GetProcessIoCounters`; são contadores do processo, não prova de leitura física do SSD. |
| Handles | `SUPPORTED` | `GetProcessHandleCount`. |
| Threads | `SUPPORTED` quando disponível | Enriquecimento opcional via `psutil` se já instalado; ausência não impede o runtime. |
| RAM total/disponível | `SUPPORTED` | `GlobalMemoryStatusEx`. |
| PSS / anônimo / file-backed Linux | `UNSUPPORTED` | Não são simulados no Windows. |
| Leitura física do SSD / residência | `DEGRADED` / `NOT_MEASURED` | Exige o ambiente físico canônico Debian/Linux. |
| Cache frio, `mincore`, `madvise`, PSI, cgroup | `UNSUPPORTED` | APIs/semânticas Linux ausentes. |
| Temperatura | `NOT_MEASURED` | Sem API estável de biblioteca padrão adotada. |

Valores indisponíveis permanecem `null` com uma razão explícita. Contadores de transferência nunca são renomeados como I/O físico.

## Resultados e diagnóstico

Arquivos locais são gravados atomicamente em `results/windows_native/`:

- `startup-audit.json`: host, capabilities, modelo, binário e commit;
- `smoke-tests.json`: resultado dos três smoke tests;
- `first-end-to-end.json`: primeira execução completa bem-sucedida;
- `run-AAAAMMDD-HHMMSS-ID.json`: cada consulta posterior.

O tempo é dividido entre routing/gate combinado, storage, contexto e Core Qwen. A API congelada `retrieve()` entrega routing e gate juntos; por isso `gate_separate` fica `null`, com `NOT_MEASURED`, em vez de inventar uma separação. O relatório também identifica o maior estágio realmente medido como gargalo.

Se algo falhar:

1. execute `python tools/setup_windows_runtime.py`;
2. confirme `ready: true`, `frozen_commit_match: true` e `cpu_only_build: true`;
3. confira espaço livre, antivírus/Defender e permissão de leitura do GGUF;
4. apague apenas resultados locais incompletos se necessário; não altere o corpus congelado;
5. execute novamente sem `--skip-smoke`.

O primeiro carregamento pode ser mais lento por cache do sistema e varredura do antivírus. Isso não é classificado como cold-cache canônico.

## Recompilação opcional do `llama.cpp`

O executável já está pronto. Se for necessário recompilar o mesmo checkout, use o CMake e Ninja fornecidos pelo Visual Studio Build Tools 2022, em uma pasta separada `build-win`, com CUDA, Vulkan, BLAS e CURL desativados:

```powershell
cmd.exe /d /s /c '"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" -S third_party\llama.cpp -B third_party\llama.cpp\build-win -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF && "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build third_party\llama.cpp\build-win --target llama-completion -j 6'
```

Não atualize o checkout, o modelo ou as flags congeladas durante essa recompilação.

## Compatibilidade futura

Os caminhos do backend aceitam `.exe`, nomes com espaços e também candidatos Linux sem extensão. A detecção de capabilities é explícita por plataforma. No Linux, a camada pode encaminhar a coleta para a telemetria congelada existente, mas somente o preflight canônico completo pode declarar um resultado válido de Fase 4E.
