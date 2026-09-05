# Brain-SSD — Notas de Pesquisa

## Auditoria do ambiente — 2026-08-07

### Sistema

- Diretório autorizado e atual: `/workspaces/Pal-Server/Brain-SSD`.
- Ubuntu 24.04.4 LTS (Noble), x86_64.
- Kernel: Linux 6.8.0-1052-azure, executado sob hypervisor Microsoft.
- Virtualização completa AMD-V.

### CPU

- CPU exposta: AMD EPYC 9V74.
- Topologia visível: 1 socket, 8 cores, 2 threads por core, 16 CPUs lógicas online.
- Cache: L1d 256 KiB, L1i 256 KiB, L2 8 MiB e L3 32 MiB.
- ISA relevante disponível: SSE4.1/4.2, AVX, AVX2, FMA, BMI1/2 e AES; AVX-512 não foi reportado.
- Limite cgroup v2: `cpu.max = 100000 100000`, equivalente a aproximadamente 1 CPU de quota apesar das 16 CPUs visíveis.

### Memória

- RAM visível: 65.847.076 kB (~62,8 GiB).
- Disponível durante a auditoria: ~59,7 GiB.
- Swap: 0; zswap: 0.
- `memory.max` e `memory.swap.max`: sem limite explícito (`max`).
- Memória bloqueável por processo: 8 MiB.

### Armazenamento e filesystem

- Workspace em `/dev/loop4`, dispositivo virtual de 128 GiB marcado como não rotacional.
- Filesystem reportado por `findmnt`: ext4, leitura/escrita, `nosuid,nodev,relatime`.
- Capacidade útil reportada: 126 GiB; 13 GiB usados; 108 GiB disponíveis no momento.
- Bloco fundamental: 4096 bytes.
- Scheduler exposto para loop4: `none`; `mq-deadline` disponível.
- A camada loop/virtualizada impede tratar os números como desempenho de um SSD físico específico.

### GPU

- `nvidia-smi` e `lspci` não estão disponíveis.
- Nenhuma GPU pode ser confirmada neste ambiente; o baseline deve assumir CPU-only.

### Toolchain detectado

- Git 2.53.0.
- GCC/G++ 13.3.0; Clang/Clang++ 18.1.3.
- GNU Make 4.3; CMake 3.28.3; Ninja ausente.
- Python 3.12.1; pip 26.1.2; uv ausente.
- Node.js 24.14.0; npm 11.9.0; pnpm 10.32.1; Bun ausente. Yarn/Corepack não produziu versão válida na sondagem.
- Go 1.26.1.
- OpenJDK/Javac 25.0.2 LTS.
- .NET SDK 10.0.200.
- Docker 29.6.1; Podman ausente.
- SQLite 3.45.3, jq 1.7, curl 8.5.0 e wget 1.21.4.
- Valgrind 3.22.0, GDB 15.1 e LLDB 18.1.3.
- `perf`, `hyperfine` e `fio` ausentes.
- Rust/Cargo ausentes.

## Hipóteses iniciais

- A localidade do workload provavelmente dominará a eficiência do cérebro ativo.
- O tamanho e a granularidade dos blocos devem trocar amplificação de I/O por overhead de seleção.
- O page cache do Linux pode ajudar, mas também pode ocultar o orçamento real se RSS e cache de arquivo não forem medidos separadamente.
- mmap não é automaticamente superior a leitura explícita; ambos exigem medição nos padrões reais.
- Sem swap, picos de memória são um risco maior e reforçam limites explícitos do working set.

## Cuidados de interpretação

- CPUs visíveis não equivalem à CPU efetivamente concedida pelo cgroup.
- Memória disponível no Codespace é muito maior que o alvo do produto; testes deverão impor orçamento controlado.
- Benchmarks do volume loop/ext4 medem esta pilha virtualizada, não todo SSD.
- A ausência de ferramenta não justifica instalação imediata; primeiro avaliar se métricas nativas bastam.

## Auditoria do repositório — 2026-08-07

- Antes da Fase 1 havia apenas os seis documentos da Fase 0; nenhum código, modelo ou benchmark prévio.
- `Brain-SSD/.git` é um diretório vazio; `git rev-parse` resolve `/workspaces/Pal-Server`, repositório pai fora do escopo. Não executar commits/resets/clean a partir desta árvore até haver repositório isolado corretamente.
- Todas as novas escritas permaneceram em `/workspaces/Pal-Server/Brain-SSD`.

## Prova de vida — fatos medidos

- Runtime: llama.cpp `217df17ac30ba2a8c374088772f81926cc5beee3`, build CPU nativo.
- Modelo: Qwen3-0.6B Q8_0, 639.446.688 bytes, SHA-256 `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
- Cinco runs frios e cinco quentes concluíram e contiveram `AZUL`.
- Mediana fria: TTFT 1302 ms, 26,68 tok/s, RSS máximo 780.320.768 bytes, leitura 639.447.040 bytes.
- Mediana quente: TTFT 1125 ms, 26,09 tok/s, RSS máximo 780.365.824 bytes, leitura física atribuída 0 bytes.
- A diferença de TTFT observada foi ~177 ms (~13,6% da mediana fria), mas dez amostras num Codespace não sustentam generalização.

## Experimentos negativos/inconclusivos

- `llama-cli` falhou antes do load com `failed to get a free port`; substituído por `llama-completion` direto.
- Sem `/no_think`, 24 tokens terminaram antes da resposta final; execução funcionou, qualidade mínima falhou.
- `--reasoning off` sozinho não evitou tags de thinking no modo detectado; `/no_think` produziu tags vazias e `AZUL`.
- O build do commit atual puxou dependências internas de servidor/multimodal para o alvo CLI e tentou UI via npm/download. O fallback sem UI permitiu compilar, mas o overhead deve ser evitado numa distribuição futura.

## O que ainda não foi demonstrado

- Cortical Pages, Knowledge I/O, Active Brain Size, cache hit cognitivo e activation rate.
- Qualidade em linguagem, programação, matemática, memória ou recuperação.
- Operação real sob limite de 4/8 GB, NVMe físico, múltiplas threads ou GPU opcional.
- Custo proporcional ao cérebro ativo. Esta continua sendo hipótese, não resultado.

## Storage Brain V0 — fatos medidos em 2026-08-07

- Cgroup v2 presente. Nesta sessão `cpu.max = max 100000`, cpuset `0-15`, `memory.max = max`; isso diverge da quota de ~1 CPU observada na Fase 1.
- `memory.current/peak/stat` são do Codespace inteiro, não do processo. Durante a reauditoria current era ~7,74 GB e peak ~8,18 GB; a matriz elevou page cache do grupo.
- 232 runs finais de storage passaram (216 page matrix + 16 pressure/working-set), sem corrupção.
- O mmap virtual de 1 GiB iniciou cold com 0 RSS em todos os 72 runs controlados; somente páginas tocadas ficaram residentes.
- Anônimo do processo ficou perto de 10,3–10,5 MiB; a maior parte do RSS foi file-backed.
- Page cache hot evitou `read_bytes` físico nos casos observados.
- Nenhum `pgscan`/`pgsteal` ocorreu na curva; não houve evidência de thrashing.
- 4 MiB venceu latência; amplificação favoreceu tamanhos diferentes por trace. Isso refuta a hipótese de um tamanho global óbvio.

## Storage Refinement — fatos medidos em 2026-08-07

- 256 KiB venceu p95 e Activation Cost nos seis workloads; o ótimo de ativação estava abaixo de 4 MiB.
- SHA completo respondia por aproximadamente 53% do p95 de 4/8 MiB.
- 1 MiB foi escolhido como joelho multiobjetivo, não como vencedor absoluto.
- Verificação na primeira ativação aproximou hits do modo performance, mas preservou custo frio nas páginas inéditas.
- Colocalização associativa reduziu I/O quando extents eram lidos, porém full-extent permaneceu pior que logical-only em custo absoluto.
- Group-required foi frequentemente uma regressão: encontrar páginas relacionadas no mesmo extent disparou overfetch.
- Topic-switch mostrou forte retenção A2 em alguns layouts colocalizados, sem pressão suficiente para chamar isso de histerese.
- Corpus de 4 GiB foi conscientemente adiado: volume adicional sem hard limit não isolaria nova variável.
