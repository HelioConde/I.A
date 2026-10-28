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


## Resultado real: 5902 Lua no inventario, apenas 2 aptos para treino

Em 28/10/2026, o usuario informou no dry-run v2:
- 22 arquivos Lua nos diretorios permitidos;
- 2 diretorios inteiros protegidos e omitidos do treinador;
- 3 Lua menores que 256 bytes;
- 19 arquivos regulares candidatos, sendo 17 Lua compilados e apenas 2 elegiveis;
- 1641 bytes amostrados; train 2, holdout 0; training_ready false;
- nenhum peso alterado e nenhuma transferencia.

A diferenca entre 5902 e 22 nao prova que todos os restantes sejam legiveis nem licenciados. O codigo foi projetado para nunca tentar treinar com material nos diretorios excluidos.

### Nova opcao 12 — auditoria por categoria de pastas, sem ler scripts

A opcao 12 chama audit_excluded_lua_metadata.py, que conta extensoes, tamanhos e subpastas. Nao abre o conteudo, executa, copia ou envia arquivos. O resultado mostra contagens agregadas, sem nomes de arquivos ou caminhos:

- permitted: .lua fora das arvores protegidas;
- game_or_client_excluded: arquivos dentro de arvores excluidas ligadas a cliente/jogo;
- sensitive_or_backup_excluded: arquivos dentro de arvores de banco, backup, contas e dados sensiveis;
- repository_metadata_excluded: metadados internos de repositorios;
- lua_files_counted / lua_files_under_protected_directories: distribuicao geral.

No PowerShell, apos atualizar:

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\audit_excluded_lua_metadata.py" "$env:USERPROFILE\Documents\grand chase files"
~~~

A auditoria nao indica permissao para treinar, nao altera os filtros nem os checkpoints. Compartilhe apenas o relatorio agregado. Nao mova scripts para contornar exclusoes; selecione apenas material cuja utilizacao para treinamento foi autorizada.


## Auditoria local final: 5880 scripts em apenas 2 raizes de cliente/jogo

O relatorio local fornecido pelo usuario em 28/10/2026 confirmou exatamente 5902 arquivos Lua:
- permitted: 22 arquivos Lua, 83.418 bytes em metadados;
- game_or_client_excluded: **5880 arquivos Lua**, 873.318.829 bytes, 147 subdiretorios percorridos;
- sensitive_or_backup_excluded: 0, repository_metadata_excluded: 0;
- 2 diretorios-raiz excluidos pela categoria game_or_client;
- nenhum conteudo lido, nenhuma transferencia, erro ou treinamento.

A diferenca entre os arquivos inventariados e os poucos aprovados esta explicada pela selecao deliberadamente restritiva. Os 5.880 scripts **nao se tornaram automaticamente um corpus licenciado** e podem incluir bytecode/dados privados.

### Opcao 13 — identificar raizes no computador, sem publicar nomes

Para permitir revisao humana da origem dos scripts, a opcao 13 chama review_local_lua_scopes.py. Somente no terminal local, mostra o caminho completo de cada raiz game_client e anti_cheat, com contagem de arquivos Lua e soma dos tamanhos **por metadados**. Nao abre arquivos, nem treina ou autoriza automaticamente seu uso. A arvore anti_cheat/HShield permanece excluida.

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\review_local_lua_scopes.py" --source "$env:USERPROFILE\Documents\grand chase files"
~~~

Nao envie caminhos de instalacoes, nomes de usuarios ou arquivos privados; e suficiente informar a **categoria e a contagem**. A partir da revisao dos direitos, use exclusivamente uma subpasta sobre a qual haja autorizacao real para treinamento; nao remova controles que bloqueiam backups, credenciais, executaveis ou codigo anti-cheat.

O uso posterior de uma subpasta como fonte do treinador exige confirmar permissao e passar pelo dry-run novamente. Nao encaminhar ao GitHub nem publicar checkpoints de scripts comerciais.
