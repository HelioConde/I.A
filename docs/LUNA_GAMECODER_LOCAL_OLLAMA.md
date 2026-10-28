# Luna GameCoder prática (Ollama local + verificação JavaScript)

**Motivo:** em 28/10/2026, a GameCoder experimental do usuário (116.480 parâmetros, contexto de 128 caracteres) respondeu ao pedido de movimento 2D com uma sequência incoerente de caracteres (`ra.rerind imglet...`). O checkpoint foi corretamente carregado e a falha é de capacidade/arquitetura, não de instalação. O teste anterior de geração marcou **0/5 JavaScript válido e 0/5 Lua válido**.

## Solução: um novo motor separado, com pesos pré-treinados

A `luna_coder_ollama.py` usa um modelo de programação já pré-treinado localmente via servidor Ollama em **127.0.0.1:11434**. Este modelo **NÃO é o MiniCoder treinado do zero**; nenhum peso do Planner ou MiniCoder é alterado, não há fine-tuning e nenhum arquivo comercial é copiado. A interface:

- usa a lista fixa de modelos `qwen2.5-coder:3b`, `qwen2.5-coder:7b`, `qwen3:4b`;
- valida que o modelo está instalado antes de solicitar geração;
- pede uma função JavaScript ES2020 completa, com prompt de código original;
- extrai a saída sem executar o código;
- usa `node --check` somente para **análise sintática**, com arquivo temporário apagado;
- se o parser retornar erro, pede ao modelo no máximo **uma correção** e reavalia;
- entrega o código e o resultado da sintaxe em JSON. **Não escreve o projeto nem testa comportamento.**

O modelo recomendado inicialmente é `qwen2.5-coder:3b` (aproximadamente **1,9 GB** de download no Ollama). Em máquina Windows com 16 GB RAM, pode-se testar depois `qwen2.5-coder:7b` (aproximadamente 4,7 GB de modelo), observando RAM/velocidade; o 30B do Qwen3 Coder (19 GB de modelo) não é boa escolha para essa configuração.

Referências oficiais:
- [Ollama para Windows](https://ollama.com/download/windows)
- [Qwen2.5-Coder 3B / 7B](https://ollama.com/library/qwen2.5-coder)
- [API local Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md)

## Instalação — não precisa reinstalar a Luna ou treinar novamente

Abra PowerShell. Instale Ollama usando o instalador oficial de Windows do link acima. Confirme que os comandos `ollama` e `node` estão disponíveis em outro terminal PowerShell:

```powershell
ollama --version
node --version
ollama pull qwen2.5-coder:3b
```

O download do modelo é uma ação **explícita do usuário** e pode requerer internet. Após baixar, ele é atendido pelo servidor local Ollama. Com a branch experimental já instalada:

```powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel atualizar o codigo." }
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\luna_coder_ollama.py" status
& $lab\ABRIR-LUNA-FORGE.cmd
```

No menu selecione **9 — GameCoder prática**. Pedido sugerido:

```text
Crie uma funcao JavaScript moveHorizontal(player, axis, dt), com aceleracao,
atrito, velocidade maxima, orientacao esquerda/direita e retorno do estado.
```

Para usar outro modelo já instalado manualmente:

```powershell
& $py "$lab\luna_coder_ollama.py" generate --model qwen2.5-coder:7b --task "Crie uma funcao de salto e gravidade para um jogo de plataformas."
```

O backend não instala modelos automaticamente nem usa URLs fornecidas pelo usuário. Se o Ollama não estiver instalado, ele apresenta orientação de instalação e não modifica o sistema.

## Qual é a métrica de sucesso?

**Não** é perda de próximo caractere. O primeiro gate é o JavaScript passar no `node --check`, seguido por **testes de comportamento de jogo em execução isolada e revisão humana**, que ainda não estão implementados para código gerado. Um `syntax: pass` significa apenas JS analisável, não mecânica correta ou jogável. A geração é feita pelo **modelo pré-treinado selecionado**; não atribua esse código ao MiniCoder do zero.

## Privacidade e segurança

A requisição da ferramenta vai somente ao servidor no endereço 127.0.0.1. Nenhum script comercial de Grand Chase, arquivo .bak, DLL, EXE, RAR ou KOM é lido. `node --check` faz a análise de sintaxe, sem executar a saída gerada. O código é mostrado no terminal e não é salvo como projeto. Não copie código gerado automaticamente para jogos ou execute sem revisão.

O checkpoint local `external_data/local-candidate-20261028-163736-598275` continua acessível na **opção 8** como testemunho do modelo MiniCoder experimental.


## Luna Core — revisao de mecanica alem da sintaxe (28/10/2026)

Uma execucao real local do `qwen2.5-coder:3b` devolveu JavaScript que passou em `node --check`, mas seu movimento apresentava problemas: **sem controle esquerda/direita**, **atrito aplicado uma vez por quadro** (nao corrigido por deltaTime), **limite apenas para velocidade positiva** e **ausencia de tratamento de entrada neutra**.

Foi criado o verificador heuristico `luna_core_qa.py`. Ele inspeciona texto em memoria, sem executar o JS e sem guardar/copiar arquivos. Para tarefas de movimento horizontal, registra cinco **indicadores estaticos**, nao provas:
- existencia de entrada direcional `axis`/`direction` ou controles esquerda/direita;
- uso de deltaTime na integracao de posicao;
- indicio de limite de velocidade positivo **e negativo**;
- indicio de atrito escalonado por deltaTime (e alerta para `velocityX *= friction`);
- indicio de tratamento de entrada neutra para desacelerar.

O codigo observado no Windows atenderia somente o indicador de integracao de posicao por deltaTime (**1/5 indicadores**). O verificador e intencionalmente heuristico: tambem pode dar falsos positivos e falsos negativos; ate mesmo **5/5 nunca significa aprovacao funcional**.

A opcao 9 agora executa o seguinte processo, sem modificar o MiniCoder:
1. gerar JS usando o modelo pretreinado Ollama local;
2. testar **sintaxe**, via `node --check`, sem executar;
3. revisar os indicadores estaticos de mecanica via Luna Core;
4. se a sintaxe falhar, pedir uma tentativa de reparo; **se a sintaxe passar, mas faltarem indicadores**, pedir no maximo uma tentativa para melhorar a mecanica;
5. se a revisao piorar a pontuacao heuristica ou invalidar a sintaxe, preservar a primeira resposta sintaticamente valida;
6. exibir `core_quality_review` com pendencias e `behavior_verified: false`.

Proximo objetivo: um runner **realmente isolado** para testes comportamentais e validacao humana de jogos gerados, sem executar codigo arbitrario diretamente no PC do usuario. A Luna Core ainda nao deve promover pesos de candidatos do zero baseada nessa heuristica.


## Regressao real 2: gera JS valido, mas adiciona loop incorreto

Em 28/10/2026, a segunda execucao local do `qwen2.5-coder:3b` gerou JS sintaticamente valido e a Luna Core classificou **2/5 indicadores** apos a revisao. A funcao melhorou o limite simetrico, mas:
- nao recebe entrada esquerda/direita;
- atribui `accelerationX = acceleration * deltaTime`, mas nao aplica essa aceleracao a `velocityX`;
- utiliza `velocityX *= (1 - friction)`, friccao aplicada por quadro, dependente do FPS;
- nao controla o estado neutro;
- cria `gameLoop` e chama `requestAnimationFrame(gameLoop)` sem solicitacao. Este callback recebe **DOMHighResTimeStamp em milissegundos**, nao deltaTime em segundos. Por isso a posicao pode disparar se o timestamp for usado como `deltaTime`.

### Correcao de processo

- O prompt de movimento agora exige **somente uma funcao pura** `moveHorizontal(character, axis, deltaTime, options)`, com entrada assinada -1/0/+1, tempo em segundos, aceleracao/s e atrito escalados por deltaTime e clamp simetrico;
- o verificador Core adiciona `blocking_issues`: aceleracao nunca aplicada a velocidade, multiplicador de atrito por quadro, uso indevido de `requestAnimationFrame`/loop e console.log extra;
- um reparo proposto pelo modelo e escolhido quando reduz bloqueios sem perder substancialmente indicadores, ou melhora indicadores sem adicionar bloqueios;
- nao ha execucao de codigo gerado. `indicators_detected=5` e `blocking_issue_count=0` ainda **nao sao prova de correção funcional**; testes de gameplay nao foram executados;
- o menu 9 permite optar por `qwen3.5:4b`, que o usuario ja informou estar instalado, para **comparar resultados**; o padrao continua `qwen2.5-coder:3b`. Nao existe transferencia de conhecimento entre os pesos do Qwen e do MiniCoder.

### Teste local apos atualizacao

```powershell
$repo = "$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
& "$repo\experiments\luna-forge-zero\ABRIR-LUNA-FORGE.cmd"
```

Escolha `9`, confirme o modelo padrao com **Enter** ou escolha `2` para `qwen3.5:4b`. Repita exatamente o pedido de movimento para uma comparacao humana justa. Nenhuma alteracao de sistema ou treinamento adicional sera feita.
