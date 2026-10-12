# Brain-SSD V2 — código-fonte nativo do llama.cpp em build separado

## Marco comprovado e o que falta

Commit `efa4dc9`: o laboratório Windows mapeou uma janela Q8_0 de 4 MiB,
medindo 0 páginas residentes antes do acesso e 1.024 páginas de 4 KiB após
o toque, via QueryWorkingSetEx. Esses dados pertencem **ao processo experimental**.
Não demonstram redução no Qwen real, cujo baseline informado foi
955 MB de memória residente e 676 MB de memória privada, TTFT de 2,06 s e
28,33 tokens/s. Os 438 testes aprovados e oito ignorados referem-se à
bateria reportada pelo Windows, não à compilação abaixo.

O pacote instalado no Brain-SSD inclui binários/DLLs, mas o fonte do
llama.cpp é público: https://github.com/ggml-org/llama.cpp.
Arquivos relevantes: src/llama-model-loader.cpp,
src/llama-model.cpp, src/llama-mmap.cpp e include/llama.h.

O upstream moderno já suporta --load-mode e --lazy-mode para algumas classes
específicas de tensores. Isso **não** faz streaming de todos os tensores
densos do Qwen e não substitui a necessidade de validação matemática.

## Preparador isolado para Windows

O arquivo tools/prepare_native_llama_windows.py não clona nem compila
automaticamente. Ele usa uma revisão fixa da fonte oficial:
972b5fcc19670e597f8de9bf5cacfb85752a5fff
(revisão pública consultada em 12 de outubro de 2026).

É necessário Git for Windows, CMake e Visual Studio com ferramentas C++.
Abra o Developer Command Prompt/PowerShell correspondente:

```bat
cd /d C:\Users\helio\Documents\I.A
git switch feat/ssd-weight-streaming-lab
git pull --ff-only origin feat/ssd-weight-streaming-lab

py -3 tools\prepare_native_llama_windows.py
py -3 tools\prepare_native_llama_windows.py --fetch
py -3 tools\prepare_native_llama_windows.py --build --output results\weight_lab\native-build.json
```

A fonte é clonada (apenas com --fetch) para:
%LOCALAPPDATA%\BrainSSD\native-llama-source\972b5fcc1967

A compilação CPU-only (apenas com --build) fica dentro dessa cópia, em
build-brainssd-cpu. O código compara o checkout ao SHA integral esperado.
Não sobrescreve nem edita o llama.cpp já utilizado pelo Chat Windows.
A fonte upstream pode não ter a mesma versão do pacote binário existente;
não compare desempenho sem controlar essa diferença.

Teste de preparação isolado (sem baixar fonte ou executar modelo):

```bat
py -3 -m unittest discover -s tests -p "test_prepare_native_llama_windows.py" -v
```

## Gates para integração ao runtime

1. Compilar o upstream sem patch e confirmar a versão, o SHA da revisão
   e o checksum dos executáveis resultantes.
2. Confirmar que o Qwen atual funciona na compilação experimental e
   observar o suporte de --load-mode e --lazy-mode no --help. Não presumir
   que --lazy-mode consiga descarregar pesos obrigatórios desse Qwen denso.
3. Criar instrumentação de residência do **processo que executa tokens**,
   separando mapeamento virtual, working set, memória privada, page cache,
   page faults, KV cache e I/O físico.
4. Só então prototipar a menor alteração nativa de carregamento/tensores.
   Não remover camadas essenciais e não alegar ganho a partir de apenas
   liberar janelas em outro processo.
5. Comparar logits (com tolerâncias) e tokens com prompts/seed iguais;
   medir RSS, TTFT, tokens/s e custo de I/O. Preservar fallback ao
   llama.cpp convencional.

**Este módulo é infraestrutura para investigação de código-fonte e compilação,
não é uma implementação de inferência com streaming.**

## Baseline do processo nativo compilado

`tools/bench_native_llama_windows.py` inicia o `llama-cli.exe` que foi
produzido na árvore isolada e mede o processo que realmente executa o Qwen.
Ele usa contadores Windows de working set, memória privada, pico, page faults,
CPU e I/O do processo. I/O é **lógico do processo**, não uma medida física do
SSD: o Windows pode responder a um page fault pelo cache de arquivos.

Exemplo (o caminho do fonte permanece fora do repositório):

```bat
py -3 tools\bench_native_llama_windows.py ^
  --cli "%LOCALAPPDATA%\BrainSSD\native-llama-source\972b5fcc1967\build-brainssd-cpu\bin\Release\llama-cli.exe" ^
  --model models\Qwen3-0.6B-Q8_0.gguf ^
  --context-size 512 ^
  --comparison-load-mode none ^
  --output results\weight_lab\native-llama-mmap-vs-none.json
```

O modo `mmap` existente no upstream executa a inferência real por páginas
sob demanda do SO, mas não é o `Brain-SSD Native Weight Loader`. Em particular,
nesta revisão `llama_mmap::unmap_fragment()` não descarrega fragmentos no
Windows. O runner registra logits e TTFT como indisponíveis porque a interface
de linha de comando não expõe callback de logits nem de primeiro token; não
estima esses valores.

O tamanho de contexto é fixado e registrado; deixar o padrão do modelo pode
alocar vários gigabytes para KV cache e invalidar uma comparação de pesos.


## Medição direta dos logits e do primeiro token — instrumento de integridade

Para contornar a limitação do `llama-cli`, o projeto inclui um executável de
**diagnóstico nativo independente**, usando a API C oficial de llama.cpp
na revisão fixa `972b5fcc19670e597f8de9bf5cacfb85752a5fff`:

- `tools/native_llama_probe/native_logits_probe.cpp`: executa prompt e amostra
  gananciosa (`greedy`) determinística, registra token IDs, top-8 logits do
  primeiro passo e um hash FNV64 sobre TODOS os logits desse mesmo passo;
- `tools/native_llama_probe/CMakeLists.txt`: compila em diretório separado
  a partir da fonte verificada; somente CPU, sem modificar o upstream;
- `tools/bench_native_logits_windows.py`: compara `mmap` e `none` no mesmo
  executável, GGUF e contexto; registra primeiro token, memória do processo e
  equivalência de tokens/primeiro passo.

**Não foi compilado nem testado com o Qwen real nesta atualização.** Os testes
Python da comparação usam resultados simulados. É obrigatória validação física
antes de considerar as métricas reais. O executável só será criado ao passar
`--build`, e a execução do modelo só acontece ao chamar o benchmark.

Use o Visual Studio Developer Command Prompt com ferramentas MSVC/CMake:

```bat
cd /d C:\Users\helio\Documents\I.A
git switch feat/ssd-weight-streaming-lab
git pull --ff-only origin feat/ssd-weight-streaming-lab
py -3 -m unittest discover -s tests -p "test_bench_native_logits_windows.py" -v
py -3 tools\bench_native_logits_windows.py --model models\Qwen3-0.6B-Q8_0.gguf --build --mode both --context 512 --threads 4 --predict 16 --output results\weight_lab\native-logits-comparison.json
```

A compilação requer o checkout fixado via
`py -3 tools\prepare_native_llama_windows.py --fetch` já executado.
O binário será colocado no diretório isolado
`%LOCALAPPDATA%\BrainSSD\native-llama-source\972b5fcc1967\build-brainssd-logits`.
O primeiro token é cronometrado dentro da API, desde o início do processo e
inclui o carregamento do modelo; **não é diretamente comparável com o TTFT
que o CLI antigo não expõe**.

A validação atual compara **IDs dos tokens gananciosos gerados e top-8 logits
do PRIMEIRO passo**, com tolerância absoluta `1e-5`. Também fornece hash
bit a bit do vetor completo de logits desse primeiro passo, mas não compara
todos os logits dos passos subsequentes. Se o hash completo diferir apesar de
os top-8 e tokens baterem, a diferença deve ser investigada antes de declarar
identidade matemática exata. Todas essas medições continuam sendo do
**llama.cpp original**: ainda não existe carregador Brain-SSD de pesos em
inferência, nem ganho adicional de RAM comprovado.

## Execução medida em 12 de outubro de 2026

O probe foi compilado com a revisão fixada e executado com o mesmo
`Qwen3-0.6B-Q8_0.gguf` (SHA-256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`),
contexto 512, quatro threads e 16 tokens gananciosos. O artefato JSON local
fica em `results/weight_lab/` e não é versionado porque contém medições da
máquina.

| Modo upstream | Pico de working set | Pico privado/commit | Primeiro token API | Integridade |
| --- | ---: | ---: | ---: | --- |
| `mmap` | 759.94 MB | 184.59 MB | 696.36 ms | 16 IDs, top-8 e hash FNV64 dos logits idênticos |
| `none` | 759.90 MB | 818.10 MB | 870.63 ms | referência |

Esta é inferência neural real pela API C, não uma simulação. Ainda assim,
`mmap` é funcionalidade upstream: reduz commit privado ao referenciar os pesos
no arquivo, mas não reduz o working set enquanto o Qwen denso acessa todos os
pesos a cada token. Não compare diretamente esses 759.94 MB com o baseline
histórico de 955 MB sem igualar versão, contexto e parâmetros.

O probe também aceita `--lazy-mode off|auto|on`, que é passado diretamente à
API upstream. A fonte fixada só marca `per_layer_token_embd` de Gemma4 e PLE
de Qwen4 experimental como `TENSOR_READ_LAZY`; os tensores densos do Qwen3
0.6B não são marcados. Portanto `--lazy-mode on` no Qwen3 é um controle
negativo: não é um cache de pesos Brain-SSD e não pode liberar as matrizes
obrigatórias. Ele é medido separadamente antes de qualquer afirmação.

Na mesma máquina, com `mmap`, contexto 512, quatro threads e 16 tokens,
`lazy-mode off` e `on` geraram os mesmos IDs e o mesmo hash FNV64
`2a893aa7b7834147`. Os picos de working set foram, respectivamente,
759,98 MB e 759,97 MB; o commit privado ficou em 184,61 MB e 184,62 MB.
Essa diferença está dentro da variação de amostragem e **não é economia de
memória**. O resultado confirma que habilitar a opção upstream não introduz
streaming dos pesos densos do Qwen3.
