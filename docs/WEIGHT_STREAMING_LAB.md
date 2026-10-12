# Brain-SSD Runtime Lab V0 — janelas de pesos SSD → RAM

**Status: experimental, isolado, sem alterações no Qwen que já funciona.**

Esta etapa inaugura a branch `feat/ssd-weight-streaming-lab`. O código
mede leitura de janelas de bytes do SSD e estratégias de cache local.
**Não executa camadas/tensores, não altera pesos,
não faz inferência, não mede tokens/s nem produz um runtime MoE real.**

A motivação é conseguir **preservar modelos grandes** e reduzir a
quantidade de memória explicitamente retida pelo processo por meio de
carregamento sob demanda. O custo de CPU e I/O pode tornar a geração
muito lenta. O estudo não afirma que GPT-6.1 Astra ou pesos fechados possam
ser executados localmente.

## Experimentos já existentes — não misturar conclusões

- `docs/COGNITIVE_CACHE.md`: políticas LRU/LFU/Cognitive em traces
  de **recuperação de conhecimento**, não de pesos de redes neurais.
- `docs/MEMORY_PRESSURE.md`: pressão real em page cache Linux;
  `mmap` e kernel baseline, ganhos modestos/algumas regressões.
- `benchmarks/storage_benchmark.py`: acessos ao corpus do Brain-SSD.

**Este novo laboratório é distinto:** lê bytes de arquivos que representam
janelas de pesos e testa padrões de demanda **sintéticos**, para avaliar
overheads antes de pensar em integração ao `llama.cpp`.

## Executar sem instalar IA nem usar GPU

Na raiz do repositório, depois de mudar para a branch experimental:

```bat
cd /d C:\Users\helio\Documents\I.A
git fetch origin
git switch feat/ssd-weight-streaming-lab
git pull --ff-only origin feat/ssd-weight-streaming-lab

py -3 tools\bench_weight_streaming.py --matrix --fixture-mib 16 --page-kib 256 --pages 64 --budget-mib 4 --turns 32 --pattern moe --output results\weight_lab\moe.json
py -3 tools\bench_weight_streaming.py --matrix --fixture-mib 16 --page-kib 256 --pages 64 --budget-mib 4 --turns 12 --pattern dense --output results\weight_lab\dense.json
py -3 -m unittest discover -s tests -p "test_weight_streaming_lab.py" -v
```

O fixture de 16 MiB é temporário e é apagado automaticamente. Cada
estratégia roda em subprocesso independente. No Windows e Linux, o
**cache de páginas do sistema operacional pode permanecer aquecido**
entre as execuções: o modo `--matrix` **não** comprova leitura fria
isolada e não deve ser usado para alegar ganho físico em SSD.

### Usar o próprio GGUF como arquivo SOMENTE LEITURA

```bat
py -3 tools\bench_weight_streaming.py --source "models\Qwen3-0.6B-Q8_0.gguf" --mode lru --pattern moe --page-kib 256 --pages 64 --turns 32 --budget-mib 4 --offset-mib 16 --output results\weight_lab\qwen-window.json
```

**Importante:** `--source` trata GGUF como **bytes opacos**.
A `--offset-mib` seleciona uma janela alinhada, **não** um tensor
identificado. O benchmark não afirma que pesos dessa região são
especialistas, camadas ativas ou representativos da arquitetura Qwen.
O modelo original não é gravado e a saída não inclui pesos ou caminho
do arquivo. Sem `--source`, usa fixture sintético.

## V1 — diretório GGUF somente leitura

`tools\inspect_gguf.py` interpreta GGUF v2/v3 sem carregar o modelo inteiro
nem chamar `llama.cpp`. Ele valida magic, versão, metadados, alinhamento,
nome/rank/shape, tipo GGML suportado, offsets e limites antes de retornar
qualquer byte. Calcula layouts F32/F16 e blocos Q4/Q5/Q8/K comuns.

```bat
py -3 tools\inspect_gguf.py models\Qwen3-0.6B-Q8_0.gguf --tensor token_embd.weight --window-bytes 64
py -3 -m unittest discover -s tests -p "test_gguf_inspector.py" -v
```

Na validação local, o Qwen autorizado foi lido como GGUF v3 com 310 tensores;
`token_embd.weight` foi localizado como Q8_0, shape 1024×151936 e
165.306.368 bytes físicos. Uma janela de 64 bytes foi verificada. Isso não é
execução de tensor, logits ou inferência por streaming.

## Estratégias, dados e limites

| Modo | Leitura/caching |
| --- | --- |
| `stream` | Lê cada janela solicitada do arquivo; sem cache explícito |
| `lru` | Mantém páginas em `OrderedDict` dentro do limite escolhido |
| `prefetch` | Usa transições **observadas anteriormente**, sem olhar o futuro |
| `mmap` | Arquivo mapeado `ACCESS_READ`, com residência gerida pelo SO |
| `full_window` | Carrega a **janela selecionada inteira** na RAM, até 256 MiB |

A memória do **cache explícito** é limitada por `--budget-mib`.
Isso não limita o Python, buffers temporários, RAM do kernel, page cache,
KV cache ou VRAM. `mmap` não é equivalente a "RAM zero".

Padrões:
- `dense`: acessa todas as páginas a cada turno. É um **proxy** de
  carga obrigatória; ainda não simula matemática de uma rede densa.
- `moe`: acessa poucas páginas centrais e especialistas favoritos
  sintéticos. **Não é execução de um MoE de verdade.**
- `switch`: alterna entre grupos de páginas para expor churn do cache.

Todos os modos calculam CRC32 sobre **todos os bytes demandados** e o
comparador confirma `checksum_sink` idêntico. Isso valida igualdade de
dados, não a precisão de inferência neural.

Métricas: tempo total, CPU, acessos/s (não tokens/s), quantidade de
chamadas lógicas de leitura, hits, misses, prefetch, expulsões,
ocupação de cache Python, RSS amostrado (quando disponível) e
`/proc/self/io` no Linux e contador de I/O do processo no Windows. O contador
Windows é lógico e nenhum dos dois deve ser confundido automaticamente com
leitura física do SSD. **Não interpretar bytes_requested_from_file como
leitura física do SSD**: o SO mantém page cache.

### Segurança

- Fixture no diretório temporário do SO, tamanho entre 1 e 256 MiB.
- Janelas alinhadas; limite de 1.024 páginas e cache de até 256 MiB.
- Fonte real lida apenas em modo binário; nunca carregada no GGUF runtime.
- O teste não executa modelos e não modifica a branch `main` nem o
  motor Qwen atual.
- Arquivo de saída JSON é criado **somente** no caminho solicitado.

## Próximos gates

1. **V0 (esta branch):** testes unitários, benchmark com fixture e
   janela de GGUF opaca. Sem alegações de ganho de inferência.
2. **V1:** leitor validado de diretório de tensores GGUF, incluindo
   offsets e blocos de quantização; impedir leitura incorreta de tensores.
3. **V2:** adaptador experimental separado do `llama.cpp`; verificar
   igualdade de logits e de tokens em tarefas controladas antes de
   comparar desempenho/memória.
4. **V3:** modelos MoE compatíveis, observando roteamento real dos
   especialistas e distinguindo camadas sempre necessárias de experts.
5. **V4:** benchmark real com Qwen aberto de diferentes tamanhos,
   repetido em máquina física, comparando a execução padrão, RSS/VRAM,
   I/O, TTFT, tokens/s, acerto e custo de execução.
6. **Promoção:** só substituir estratégia padrão se os resultados
   forem reproduzíveis **e não houver regressão de qualidade**.

Este experimento não reutiliza as métricas históricas do Cognitive
Cache como prova de ganho em pesos neurais.
