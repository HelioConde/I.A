# Treinamento experimental da Luna com Lua local — **apenas com autorização**

A pasta usada pelo usuário é `C:\Users\helio\Documents\grand chase files`. Auditorias já mostraram aproximadamente 5.902 arquivos de extensão `.lua`, dos quais 5.789 aparentavam ser texto UTF-8 na amostra. A presença desses arquivos no computador **não estabelece titularidade, licença para treinamento ou autorização de redistribuição**. Arquivos do cliente Grand Chase podem estar protegidos. Use a opção abaixo **somente se você tiver verificado os direitos e as permissões necessárias**. Caso contrário, treine com os exemplos originais e projetos MIT já aprovados.

## O que foi implementado

`train_private_lua.py` é um treinador experimental **somente local**, diferente das opções do Qwen:
- recebe a pasta e exige `--acknowledge-rights` (no menu, confirmar duas vezes);
- percorre arquivos **regulares** `.lua` (sem executar, extrair, decompilar ou enviar arquivos);
- ignora pastas como `Elsword`, `HShield`, `database`, `backup`, `billing`, `accounts`, `auth` e outras possivelmente sensíveis;
- rejeita links simbólicos/junctions, Lua compilado, arquivos não UTF-8, vazios, e amostras com indícios óbvios de credenciais;
- limita a leitura do **conteúdo por arquivo a 64 KiB** e o conjunto total amostrado a **64 MiB por padrão** (máximo de 96 MiB). Portanto, **não utiliza necessariamente os 5.902 arquivos** em uma rodada;
- reserva arquivos completos exclusivamente para avaliação (holdout): nenhum deles participa das atualizações de gradiente;
- parte do **checkpoint local MiniCoder existente**, já verificado por SHA-256; não usa pesos Qwen/Ollama;
- faz 300 passos por padrão, em CPU, com recursos limitados;
- mantém os pesos novos em `experiments/luna-forge-zero/private_lua_training/private-lua-*`, pasta ignorada pelo Git e **não publicada**;
- salva apenas estatísticas e pesos no diretório de saída, sem salvar/transmitir texto-fonte ou nomes de arquivos;
- não modifica os checkpoints anteriores, não executa Lua do usuário e não promove automaticamente a nova IA.

### Limitações relevantes

O MiniCoder possui **116.480 parâmetros**, janela de **128 caracteres** e tokenização ASCII. O treinamento é um experimento de **previsão de caracteres Lua**, não instrução/solução de gameplay. Mesmo com perda menor no holdout, a GameCoder pode continuar emitindo texto inválido. Os pesos podem memorizar trechos do material original: não os publique. O filtro de possíveis segredos é heurístico e pode deixar passar conteúdo privado; faça inspeção e autorização dos scripts antes.

Não há como garantir uma clonagem exata de Grand Chase nem código jogável a partir de um MiniCoder desse tamanho. Como o código dos arquivos não é necessariamente seu, o treinamento deve respeitar direitos autorais e outras obrigações aplicáveis.

## Executar no Windows

Primeiro atualize a branch local:

```powershell
$repo = "$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Atualizacao falhou" }
$lab = Join-Path $repo "experiments\luna-forge-zero"
& "$lab\ABRIR-LUNA-FORGE.cmd"
```

**Menu 10 — Treinar Lua local privado:** confirmar direitos com `TENHO DIREITOS`, analisar previamente o resumo do dry-run e confirmar `TREINAR`. A operação será executada somente na sua máquina. **Menu 11** oferece a prévia do código gerado pelo novo MiniCoder privado, sem executar os scripts.

Alternativa direta, para quem já revisou os direitos:

```powershell
$py = Join-Path $lab ".venv\Scripts\python.exe"
$src = "$env:USERPROFILE\Documents\grand chase files"
& $py "$lab\train_private_lua.py" dry-run --source "$src" --acknowledge-rights
# Confira contagens e restricoes antes de rodar:
& $py "$lab\train_private_lua.py" train --source "$src" --acknowledge-rights --max-mib 64 --steps 300
```

O comando gera novos pesos locais sem sobrescrever modelos. É necessário que um checkpoint `external_data/local-candidate-*` tenha sido treinado antes (a instalação existente do usuário já incluiu um). Se houver erro ou falta de permissão para os arquivos, interrompa o treinamento e não ignore os alertas.

### Testar a geração da Luna própria

```powershell
& $py "$lab\preview_private_lua.py" list
& $py "$lab\preview_private_lua.py" generate --task "Crie uma funcao original de movimento horizontal em Lua"
```

O resultado ainda **não foi validado sintaticamente nem funcionalmente**. É um teste dos pesos da MiniCoder treinada no seu computador, não do Qwen.

## Como interpretar o relatório

- `source_lua_files_discovered`: arquivos Lua encontrados no escopo de pastas permitido.
- `sampled_files`: arquivos realmente utilizados na rodada, limitado pela memória e amostragem.
- `train_files` / `heldout_files`: divisão por arquivos, separada para reduzir vazamento na avaliação.
- `heldout_lua_loss_before` / `heldout_lua_loss_after`: métrica de previsão de caracteres do MiniCoder. **Não mede qualidade de jogos**.
- `status`: `private_experimental_checkpoint_not_promoted`.
- `source_files_exported`, `backups_and_archives_opened`, `network_requests`: todos zero pelo desenho do script.

Não publique nem suba para GitHub as pastas de checkpoints ou o conteúdo original.


## Diagnostico da falha: Poucos arquivos Lua elegiveis (28/10/2026)

O dry-run do usuario abortou antes de treinar, mas isto nao significa que a pasta esteja vazia. O inventario incluiu 5.902 arquivos .lua em toda a arvore. O treinador ignora subpastas protegidas e filtra arquivos pequenos, credenciais, binarios e amostras nao UTF-8. A divisao aleatoria anterior tambem podia produzir menos de dois arquivos holdout.

A versao corrigida informa os campos abaixo **sem nomes de arquivos, caminhos ou conteudo** mesmo quando nao ha corpus suficiente:

- training_ready: somente true quando existem 8 amostras para treino e 2 para holdout;
- source_lua_files_discovered: conta apenas arquivos sob diretorios permitidos, pode ser menor que 5902;
- excluded_entry_counts.protected_directory_skipped: quantas subpastas foram totalmente ignoradas;
- excluded_entry_counts.files_under_256_bytes: arquivos pequenos ignorados;
- eligible_regular_lua_files_before_content_filter: arquivos candidatos apos filtrar diretorios e tamanho;
- skipped_by_reason: tipos de rejeicao apos a leitura limitada de amostras;
- sampled_files/train_files/heldout_files: divisao de arquivos aptos;
- sample_budget_reached: limite agregado da amostra foi atingido.

A nova divisao deterministica garante **pelo menos 2 arquivos holdout** quando existem pelo menos 10 arquivos aptos, sem enfraquecer exclusoes de privacidade.

Para inspecionar APENAS o relatorio, apos atualizar o repo, execute no PowerShell:

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\train_private_lua.py" dry-run --source "$env:USERPROFILE\Documents\grand chase files" --acknowledge-rights
~~~

O dry-run nao altera pesos e termina com status 3 quando nao ha dados suficientes. Nao compartilhe arquivos de jogo ou credenciais, apenas o JSON agregado. Se as amostras estiverem em pastas excluidas, nao desabilite filtros nem mova conteudo para contornar a protecao; revise a origem e os direitos primeiro. A autorizacao continua sendo pre-requisito.
