# Storage Brain V0

## Escopo

Storage Brain V0 mede somente organização física e acesso mmap. Não contém LLM, router, gating, cache próprio, prefetch, io_uring, O_DIRECT, LRU ou inteligência. O Linux page cache é o único cache operacional.

## Corpus sintético

Um diretório contém:

```text
corpus.json
brain.dat
manifest-4194304.json
manifest-8388608.json
manifest-16777216.json
manifest-33554432.json
```

`brain.dat` é determinístico por seed. Cada unidade global de 1 MiB deriva de SHA-256 `(seed, unit_index)` e repete o digest até preencher a unidade. Isso não simula semântica; apenas produz bytes reproduzíveis e não esparsos.

O mesmo arquivo de dados suporta vários tamanhos de página. O CLI aceita corpus de 1, 4 ou 8 GiB sem regenerar quando descriptor, seed, versão e tamanho coincidem. Nesta fase somente 1 GiB foi materializado para validar antes de crescer.

Corpus medido:

- tamanho: 1.073.741.824 bytes;
- seed: `20260807`;
- SHA-256 do arquivo: `5d973e2d80b396051830c6a588c26fc8a681cd36ab9637492258b768ade0e9ad`;
- páginas: 256×4 MiB, 128×8 MiB, 64×16 MiB ou 32×32 MiB.

## Manifest e Cortical Page

Manifest JSON v1 contém versão de schema/conteúdo, seed, arquivo, tamanho total, tamanho/quantidade de páginas e algoritmo de checksum. Cada página contém:

- `page_id` contíguo;
- `version`;
- `offset`;
- `size`;
- SHA-256;
- `related_pages` determinísticas para associative walk.

O formato aceita qualquer tamanho positivo múltiplo de 4096 que divida o corpus; adicionar 64 KiB, 256 KiB, 1 MiB ou 64 MiB não exige alterar o backend.

## StorageBackend

Contrato atual:

- `open_brain()`;
- `close_brain()`;
- `get_page(page_id, validate=True)`;
- `release_page(page)`;
- `stats()`;
- `advise_drop_cache()` como capacidade específica do baseline mmap.

`MMapStorageBackend` abre o arquivo read-only, valida manifest/tamanho/offsets, mapeia todo o endereço virtual sem torná-lo residente e devolve `memoryview` da página. Toda leitura medida calcula SHA-256 completo. Truncamento falha ao abrir; corrupção falha ao ler. Reopen foi testado.

## Estados de cache

- **best-effort cold**: `POSIX_FADV_DONTNEED` é aplicado somente ao arquivo antes de mmap. Exige também RSS do mapping igual a zero antes do acesso. Não é chamado de cold garantido.
- **best-effort warm**: aplica o mesmo reset local e valida 25% das páginas únicas da sequência antes da medição.
- **best-effort hot**: aplica o mesmo reset local e valida todas as páginas únicas da sequência antes da medição.

A matriz V1 revelou que warm herdava o run cold anterior e se comportava como hot. Ela foi preservada como resultado negativo e substituída analiticamente pela V2, que reseta localmente todos os estados antes do precondicionamento.

Nunca usamos `/proc/sys/vm/drop_caches`. O kernel não expõe hit/miss exato do page cache por acesso. Aproximações explícitas:

- Brain Cache HIT: não existe; cache gerenciado = 0 bytes.
- file-backed residente: `/proc/self/smaps` e `smaps_rollup`.
- Linux cache efetivo: página residente + zero incremento de `read_bytes`.
- physical miss: incremento de `/proc/self/io:read_bytes`.

## Telemetria

Por run:

- `/proc/self/smaps_rollup`: RSS, PSS, Pss_Anon/File, Anonymous, private/shared clean/dirty;
- `/proc/self/status`: RssAnon, RssFile e RssShmem;
- `/proc/self/io`: read/write bytes, rchar/wchar, syscr/syscw;
- `/proc/self/stat`: CPU e faults;
- `/proc/self/smaps`: residência do mapping de `brain.dat`;
- cgroup v2: current/peak/max/high, anon, file, file_mapped, faults, major faults, scan e steal.

Cgroup mede o Codespace inteiro; não é memória privada do benchmark. Picos de CPU amostrados incluem overhead do sampler. A média usa CPU do processo no loop medido, que inclui checksum e parte da observação concorrente.

## Workloads

Todos usam seed fixa: sequential, uniform random, hot-set 80/20, clustered com dwell, topic-switch A→B→A e associative walk com 85% de probabilidade de seguir link disponível.

## Orçamento lógico

`--memory-budget-mib` é metadado de política e impede página individual maior que o orçamento. Não é hard cgroup e não limita o Linux page cache. Um hard limit não foi aplicado porque `memory.max` pertence ao cgroup compartilhado e alterá-lo poderia afetar outros processos do Codespace.

## Limitações

- Volume `/dev/loop4` ext4 virtual; não é medição de NVMe físico.
- SHA-256 de página inteira faz parte da latência. Mede caminho íntegro, não I/O puro sem validação.
- A matriz mantém bytes lógicos por run em 256 MiB; páginas maiores implicam menos acessos e mudam a granularidade do trace.
- Warm não possui uma fração exata garantida porque o page cache é compartilhado.
- O corpus de 1 GiB excede o conjunto tocado por run, mas não excede a RAM visível do host.
- Não houve pressão suficiente para forçar reclaim; 4/8 GiB continuam suportados, ainda não materializados/medidos.

## Refinamento posterior

A Fase 2.5 separou LogicalCorticalPage de StorageExtent e removeu SHA do hot path de performance. O formato/checksums V0 permanecem válidos. Veja [STORAGE_REFINEMENT.md](STORAGE_REFINEMENT.md).
