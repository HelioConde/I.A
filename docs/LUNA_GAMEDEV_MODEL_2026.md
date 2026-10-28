# Luna GameDev V4 — seleção de modelo por teste real de jogo (28/10/2026)

## Objetivo

O usuário pediu para **trocar o modelo de programação por um modelo atual que consiga criar jogos superiores**, sem crédito falso para Luna. **Não** é suficiente que o JavaScript passe no parser: o código precisa funcionar **com input real no Chromium**. O jogo inicial da própria Luna está publicado em https://helioconde.github.io/I.A/luna-created/, mas tem apresentação e profundidade inferiores ao objetivo final.

## Pesquisa e decisão

| Categoria | Modelo | Evidência | Decisão |
|---|---|---|---|
| Modelo de referência já testado | Qwen3-4B-Q4_K_M (2,5 GB) | Gerou jogo básico do zero; testes Chromium passaram depois de 12 patches reais | Manter, não desinstalar |
| **Principal candidato LOCAL de programação** | **Ornith-1.5-9B Q4_K_M (~5,78 GB)** | Ornith publica benchmarks SWE-bench Verified 70,6%, Terminal-Bench 2.1 46,2%, versus Qwen3.5-9B 53,2%/21,3%. Resultados **publicados pelo fornecedor**, não comprovam jogo bom. | **Testar agora; promover só após teste** |
| Candidato de geração recente | Qwen3.8-9B-Distill Q4 (~5,78 GB) | Destilação do Qwen3.8; benchmarks divulgados pelo fornecedor limitados; sem evidência equivalente de Godot/GameDevBench | Alternativa se Ornith falhar |
| Modelos mais capazes remotos | Claude Opus 5.5 / GPT-6.1 Sol | GameDevBench: 70,6% e 70,0% em 333 tarefas Godot com agentes/multimodalidade | **Não rodam offline em 16 GB** |

Fontes primárias:
- Ornith e benchmark: https://huggingface.co/ornith-ai/Ornith-1.5-9B e https://huggingface.co/ornith-ai/Ornith-1.5-9B-GGUF
- SHA-256 GGUF: https://huggingface.co/ornith-ai/Ornith-1.5-9B-GGUF/blob/main/Ornith-1.5-9B-Q4_K_M.gguf
- Qwen3.8 distill: https://huggingface.co/empero-ai/Qwen3.8-9B-Distill-GGUF
- GameDevBench: https://github.com/waynchi/gamedevbench

**Cautela:** nenhum benchmark de jogo publicado compara diretamente Ornith-1.5-9B com Qwen3-4B nas condições de Luna (CPU, 16 GB RAM e jogo Web Canvas). A decisão real exige o benchmark próprio. Código escrito pelo ChatGPT só pode fazer parte da infraestrutura/testes, **não do jogo candidato atribuído ao modelo**.

## Hardware e runtime

Computador: Windows 11, Intel i5-12400, 16 GB RAM, Radeon RX 580. Ornith Q4 pesa aproximadamente **5,78 GB somente os pesos**; contexto e runtime consomem mais memória. Configuração experimental: CPU, **4096 tokens** de contexto, **4 threads**. Não iniciar simultaneamente com modelos grandes, IDEs pesadas ou jogos exigentes. RX 580 não tem VRAM suficiente para manter o modelo Q4 inteiro.

O Ornith usa arquitetura baseada em Qwen3.5; precisa de **llama.cpp com suporte a Qwen3.5**. Benchmark CI usa um llama.cpp recente fixado por SHA de commit, sem modificar o runtime congelado das pesquisas Brain-SSD. No Windows, atualizar/instalar llama.cpp separadamente (por exemplo, `winget install llama.cpp`), e verificar `llama-cli --version`.

## Instalação explícita no Windows

No repositório I.A:

    py tools/install_ornith_game_model.py

Acima apenas imprime origem, hash e tamanho, sem download. Para autorizar aproximadamente 5,78 GB:

    py tools/install_ornith_game_model.py --confirm-download

Arquivo em `models/Ornith-1.5-9B-Q4_K_M.gguf`, com SHA-256 oficial, sem substituir qualquer modelo anterior.

## Benchmark comparativo de código de jogo

Workflow: [Luna GameDev — Ornith 9B vs Qwen 4B Real Coding Trial](../.github/workflows/luna-ornith-game-benchmark.yml). Usa o **mesmo prompt** e critérios nos dois modelos GGUF reais:

1. Gerar um JavaScript Canvas original; o modelo escreve todo o arquivo, sem código pronto do assistente.
2. Registrar modelo, hash dos pesos, hash do prompt, código e tentativas.
3. Verificar sintaxe usando `node --check` e bloquear APIs de rede ou execução dinâmica.
4. Abrir no Chromium isolado, testar Canvas, movimento real, pulo Space e dano ao inimigo com Z, guardando screenshots.
5. Falha de geração ou teste significa **INCOMPLETE**, sem publicação falsa.
6. Se os testes passarem, comparar tempo, robustez e qualidade visual. Sucesso neste exercício **não equivale a um jogo completo**: depois testar fase, chefe, animações e Godot.

A infraestrutura/testes foram feitos pelo ChatGPT. O arquivo `game.js` do desafio será **100% saída do modelo**. O HTML de teste é suporte explicitamente atribuído ao avaliador.

## Integração opcional com Luna GameDev local

O comando de desafio GameDev agora usa `auto`, **somente quando o GGUF estiver instalado e SHA-256 verificado**. Com Ornith9B presente, escolhe Ornith; caso contrário, volta ao Qwen3-4B se estiver íntegro. O chat comum, o backend de pesquisa e a autoria do jogo já publicado **não são alterados**:

    py tools/run_game_agent_v3_windows.py --model-file auto --attempts 2 --save-draft

Para testar explicitamente o modelo antigo:

    py tools/run_game_agent_v3_windows.py --model-file qwen3-4b --attempts 2

Para forçar o novo (requer instalação local e runtime compatível com Qwen3.5):

    py tools/run_game_agent_v3_windows.py --model-file ornith-1.5-9b --attempts 2

Os códigos gerados pelo modelo só viram jogos publicados após revisão e testes reais. O modo `auto` não baixa arquivos, não altera perfil de chat e não muda as versões existentes.

## Gate para alterar o padrão

O default do script específico §run_game_agent_v3_windows.py§ é §auto§: Ornith é escolhido apenas se instalado e validado por hash; caso contrário Qwen3-4B. A preferência não implica que o novo modelo já seja superior em jogos. Nenhum modelo de chat comum foi substituído. Quando o Ornith demonstrar geração real e jogo testado com vantagem sobre Qwen3-4B, ativar seu perfil GameDev, mantendo Qwen como fallback e sem alterar chat comum nem dados locais. A publicação de um jogo superior também exige QA visual e avaliação do usuário.


## Resultado medido do primeiro desafio completo (28/10/2026)

[Run real 40653494692](https://github.com/HelioConde/I.A/actions/runs/40653494692): **ambos INCOMPLETE** apesar de execução de inferência nativa e verificações SHA dos GGUF.

| Modelo | Tentativa 1 | Tentativa 2 | Jogabilidade |
|---|---|---|---|
| Ornith-1.5-9B | unsafe_code | javascript_syntax_error | Não iniciada: saída inválida |
| Qwen3-4B | javascript_syntax_error | javascript_syntax_error | Não iniciada: saída inválida |

Ornith não ganhou nem perdeu a comparação em gameplay, porque **nenhum candidato compilou**. O Qwen4B já criou um jogo completo antes, por múltiplas tarefas e reparos menores; não comparar esse resultado com uma geração única.

## Benchmark incremental mais próximo de trabalho real

[Workflow Luna GameDev — Actual Game Bug Repair](../.github/workflows/luna-attack-model-comparison.yml) e [PR #20](https://github.com/HelioConde/I.A/pull/20).

Os dois modelos recebem o MESMO bloco real de `site/luna-created/game.js`. Bug observado no código: `attackTarget.hp -= 10` ocorre **todo quadro**, enquanto isAttacking permanece verdadeiro, então um KeyZ pode zerar HP do inimigo em um único ataque. A IA deve gerar apenas a substituição do bloco e preservar o resto do jogo. O avaliador rejeita saída sem impedir acertos repetidos e exige Node syntax.

O Chromium de teste valida que o primeiro KeyZ tira **exatamente 10 HP**, roda novamente os seis testes completos de jogo e registra screenshots. O bloco aceito é escrito pela inferência real do respectivo modelo, sem reatribuir código do ChatGPT como modelo. Não atualiza jogo público automaticamente.

**Modelo GameDev local:** o mecanismo `auto` prefere Ornith apenas quando instalado e com hash íntegro. Isso é uma opção experimental, **não uma alegação de que já venceu em qualidade**. Se o novo GGUF não abrir no runtime Windows, atualizar o llama.cpp usado pelo GameDev separadamente; não mexer no Core de pesquisa.
