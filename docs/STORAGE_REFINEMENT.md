# Storage Brain Refinement — Fase 2.5

## Conclusão

A granularidade ótima de latência está abaixo de 4 MiB. 256 KiB venceu latência e Activation Cost, mas 1 MiB é o melhor baseline de equilíbrio observado entre latência, amplificação, CPU, faults e metadados. StorageExtent de 4 MiB é o menos prejudicial entre 4/8/16 MiB, porém ler o extent inteiro permanece desabilitado por padrão.

## Integridade versus performance

Checksums SHA-256 continuam no manifest.

- **integrity**: calcula SHA-256 completo em cada acesso.
- **first_activation**: calcula uma vez por página por abertura do backend; IDs verificados ficam em memória.
- **performance**: não calcula SHA no hot path. Lê um byte de cada página base de 4096 bytes e o último byte, combinando tudo em um sink determinístico de 64 bits.

O sink impede que o acesso seja ignorado e força fault/residência de todo o intervalo lógico sem varrer todos os bytes. `read_bytes`, faults e mapping RSS confirmam acesso físico real.

Varredura integral separada: 8.064 páginas, 6 GiB lógicos, 0 erros. Cada um dos seis manifests teve 100% das páginas validadas.

Política de 1 MiB/hot-set, 256 acessos:

| Política | p50 | p95 | CPU/acesso | Páginas verificadas | Tempo total |
|---|---:|---:|---:|---:|---:|
| integrity sempre | 0,759 ms | 1,364 ms | 1,153 ms | 95 | 244 ms |
| first activation | 0,045 ms | 1,455 ms | 0,615 ms | 95 | 136 ms |
| performance | 0,042 ms | 0,719 ms | 0,243 ms | 0 | 65 ms |

`first_activation` melhora hits/tempo total, mas p95 ainda inclui páginas frias verificadas pela primeira vez.

## LogicalCorticalPage

Unidade mínima ativável e contabilizada como byte cognitivamente solicitado. Possui ID, checksum, relações e offset físico. O tamanho pode variar independentemente do extent.

## StorageExtent

Agrupamento físico alinhado de LogicalCorticalPages. Na Fase 2.5 é apenas uma visão experimental; não é cache nem prefetch. Foram testados:

- logical: 256/512 KiB, 1/2 MiB;
- extent: 4/8/16 MiB;
- nove combinações selecionadas, não produto cartesiano completo.

Modos:

- `logical_only`: toca somente a página solicitada;
- `full_extent`: toca todo extent em cada solicitação;
- `group_required`: em janela de oito solicitações, toca o extent uma vez quando mais de uma página distinta requerida pertence a ele; caso contrário toca a página.

## Useful Byte Ratio

`cognitive_requested_bytes / physical_read_bytes`.

Pode superar 1 quando páginas solicitadas se repetem e o cache evita nova leitura. Para overfetch, valores abaixo de 1 indicam desperdício. Também registramos `storage_bytes_touched / cognitive_requested_bytes` para separar decisão do benchmark de readahead do kernel.

## Activation Cost

Vetor por página lógica:

- primeira latência observada;
- bytes físicos médios por ativação;
- CPU média por ativação.

Para screening existe um escalar explicitamente experimental:

`first_latency_ms + physical_MiB_per_activation + cpu_ms_per_activation`.

Ele não é uma unidade física universal e não deve substituir a leitura do vetor.

## Matriz de páginas — performance cold

Medianas entre workloads; 256 MiB lógicos por run.

| Logical page | p50 | p95 | p99 | accesses/s | amplificação | faults/acesso | CPU/acesso | manifest | Activation score |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 256 KiB | 0,075 ms | 0,290 ms | 0,389 ms | 8.270 | 0,805 | 2,41 | 0,105 ms | 1,14 MB | 1,068 |
| 512 KiB | 0,216 ms | 0,415 ms | 0,568 ms | 4.907 | 0,707 | 4,84 | 0,183 ms | 566 KB | 1,525 |
| 1 MiB | 0,432 ms | 0,692 ms | 0,894 ms | 2.823 | 0,647 | 9,47 | 0,336 ms | 281 KB | 2,458 |
| 2 MiB | 0,901 ms | 1,194 ms | 1,476 ms | 1.540 | 0,622 | 19,12 | 0,649 ms | 140 KB | 4,309 |
| 4 MiB | 1,761 ms | 2,384 ms | 3,072 ms | 761 | 0,630 | 39,75 | 1,315 ms | 70 KB | 8,196 |
| 8 MiB | 3,578 ms | 4,761 ms | 5,485 ms | 402 | 0,568 | 72,53 | 2,488 ms | 35 KB | 15,922 |

256 KiB venceu p95 e Activation Cost em todos os workloads. Amplificação favoreceu 4 MiB no associative, 8 MiB em random/hot-set/clustered/topic-switch e 256 KiB apenas no sequential.

O total de faults para 256 MiB lógico permaneceu da mesma ordem; páginas pequenas reduzem faults por acesso, mas exigem mais acessos. O manifest de 256 KiB ainda representa apenas ~0,106% do corpus de 1 GiB.

## Quanto SHA afetou a Fase 2

| Página | Fase 2 integrity p95 | Fase 2.5 performance p95 | Redução |
|---:|---:|---:|---:|
| 4 MiB | 5,103 ms | 2,384 ms | 53,3% |
| 8 MiB | 10,088 ms | 4,761 ms | 52,8% |

A conclusão direcional da Fase 2 continuou correta — páginas menores têm menor ativação —, mas aproximadamente metade do p95 observado nesses pontos vinha do SHA completo.

## Coalesced access e localidade associativa

216 runs de extent, todos íntegros, sem divergência de sequência entre random e colocated.

Exemplo representativo: logical 1 MiB, extent 4 MiB, associative cold.

| Layout/modo | p95 | amplificação física | Useful Byte Ratio | touch amplification | Activation score |
|---|---:|---:|---:|---:|---:|
| colocated logical-only | 0,826 ms | 0,719 | 1,391 | 1,0 | 1,699 |
| colocated group-required | 0,709 ms | 0,969 | 1,032 | 1,125 | 2,104 |
| colocated full-extent | 1,938 ms | 1,438 | 0,696 | 4,0 | 4,416 |
| random logical-only | 0,670 ms | 0,820 | 1,219 | 1,0 | 1,878 |
| random full-extent | 2,151 ms | 2,781 | 0,360 | 4,0 | 6,207 |

Colocalização reduziu bytes físicos do full-extent de ~89 MiB para ~46 MiB nesse caso (~48%), mas ainda leu mais que logical-only (~23 MiB). Em outras combinações, a redução do full-extent ficou aproximadamente entre 30% e 65%.

Resultado negativo: `group_required` frequentemente piorou no layout colocalizado porque encontrou pares relacionados e leu o extent; no random, frequentemente degenerou para logical-only e pareceu melhor. Coalescer não é automaticamente útil.

## Topic switch A→B→A

Exemplo logical 512 KiB, extent 8 MiB, full-extent:

| Layout | A1 físico | A2 físico | Redução no retorno |
|---|---:|---:|---:|
| colocated | 89,19 MiB | 15,75 MiB | 82,3% |
| random | 139,50 MiB | 106,00 MiB | 24,0% |

O layout colocalizado preservou mais dados úteis para o retorno A2, mas pagou overfetch alto. Sem hard pressure, isso mede retenção do page cache, não histerese cognitiva.

## Recomendação para a próxima fase

- LogicalCorticalPage baseline: **1 MiB**.
- StorageExtent: **4 MiB** como fronteira física configurável.
- Acesso default: **logical-only**.
- Full-extent: desabilitado; apenas experimento.
- Coalescência futura: somente quando múltiplas páginas já foram explicitamente requeridas, e deve evitar tocar bytes não pedidos.
- Integridade: full sweep offline/controle + `first_activation` opcional; performance mode somente para benchmark.

256 KiB teve menor Activation Cost absoluto — mínimo observado foi 0,658 no associative logical-only/colocated —, mas 1 MiB é o joelho mais equilibrado e reduz por 4 a cardinalidade/metadados em relação a 256 KiB.

## Limitações

- Volume loop/ext4 virtual, sem NVMe físico.
- Sem hard RAM limit ou reclaim significativo.
- Conteúdo é sintético; random layout remapeia IDs a slots físicos com bytes diferentes, mas sequência/quantidade de trabalho lógico são idênticas e o conteúdo não influencia decisões.
- Extent grouping usa janela fixa de oito; outras janelas podem mudar resultados.
- Activation score combina ms e MiB com pesos unitários apenas para screening.
- Corpus de 4 GiB não foi materializado: aumentaria volume, mas não pressão controlada nem informação causal neste Codespace.

