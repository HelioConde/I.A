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


## Proxima etapa: verificar formato dos 5880 Lua na pasta Elsword

O relatorio de 28/10/2026 identificou 5880 extensoes .lua na pasta Elsword. A contagem por metadados nao confirma que os arquivos sao codigo Lua legivel, valido ou autorizado para treinamento. Nao presuma que o nome Elsword indique scripts do Grand Chase.

**Opcao 14 — Verificar formatos de Lua na pasta Elsword**.
- exige a selecao de uma pasta chamada Elsword;
- le somente os primeiros 4096 bytes de cada arquivo regular .lua;
- ignora subpastas de backups, contas, dados privados e anti-cheat, e nao segue links;
- classifica formatacao aparente (texto UTF-8, bytecode, UTF-16 ou desconhecido) sem testar sintaxe;
- retorna apenas contagens, jamais texto-fonte, caminhos ou nomes de arquivos;
- nao executa, extrai, envia, copia ou treina scripts e nao altera pesos.

PowerShell (apos atualizar o projeto):

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Falha no git pull" }
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\audit_elsword_lua_headers.py" --source "$env:USERPROFILE\Documents\grand chase files\Elsword"
~~~

A saida deve ser compartilhada somente como JSON de totais, com os campos lua_files_sampled, classification_counts, excluded_sensitive_subdirectories, errors e partial. Texto UTF-8 detectado na amostra nao e comprovacao de sintaxe nem de licenca. Os arquivos comerciais continuam excluidos do treino automatico.


## Etapa 16 - Perfil de 64 KiB e benchmark da Luna propria

O usuario executou o perfil Lua de Elsword em 28/10/2026:
- 5880 amostras, sendo 5786 candidatas a texto UTF-8 e 94 de formato desconhecido;
- 129202591 bytes de amostra lidos, 399 arquivos ainda maiores que 65536 bytes;
- com funcoes ou controle: 1520 + 94 + 78 = **1692**;
- com limite de 4 KiB: 145 + 47 + 47 = **239**; acrescimo de **1453** amostras com estruturas;
- 4094 amostras sem estruturas detectadas, mas isso nao significa ausencia de codigo;
- 18531 ocorrencias de function, 29485 de if, 13961 de local, 5350 de return e 48694 de end;
- 0 erros, 0 scripts treinados. Nenhuma permissao de treinamento foi inferida.

**O codigo comercial nao foi incorporado ao treino.** Como proximo passo, criar um teste do modelo realmente treinado com fontes originais/permissivas em vez de expandir indefinidamente a leitura de codigo comercial.

### Opcao 15 - Benchmark Lua da MiniCoder propria, sem execucao de scripts

Nova ferramenta benchmark_original_lua.py. Carrega um checkpoint MiniCoder local verificado por SHA-256 sob external_data/local-candidate-*, e gera respostas para tres desafios originais sem resposta no conjunto de treinamento supervisionado: chefe com fases, inimigo com campo de visao e plataforma atravessavel.

Mostra a saida gerada no terminal; oferece --no-output para nao mostrar texto. Apresenta apenas sinais lexicais fracos como function, end, return e presenca de assinatura de funcao. Indica explicitamente lua_syntax NOT_TESTED e gameplay_behavior NOT_TESTED. Nao usa Qwen, nao le Elsword, nao altera pesos nem executa o codigo gerado.

PowerShell:

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Falha no git pull" }
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\benchmark_original_lua.py"
~~~

Alternativa: opcao 15 do menu. A MiniCoder continua um modelo pequeno, de apenas 116480 parametros e janela de 128 caracteres. Estruturas lexicais nao comprovam sintaxe Lua valida nem gameplay. As tarefas sem resposta servem apenas para acompanhar a qualidade das amostras ao longo do tempo; nao substituem benchmark funcional. O treino futuro deve usar somente codigo original ou licenciado.


## Resultado real de codigo gerado pela MiniCoder V0: 0/3 (28/10/2026)

O usuario executou o benchmark das 3 tarefas originais nao treinadas com o checkpoint local-candidate-20261028-163736-598275, SHA256 7fe42029097858e599be160f60f3fa5212dc24037c767b23242872eafa5fa3fb:
- boss_attack_phases: texto incoerente, sem function, end ou return;
- enemy_line_of_sight: texto incoerente, sem assinatura de funcao;
- one_way_platform: texto incoerente, sem assinatura de funcao;
- function_signature_heuristic_count 0/3;
- Lua syntax e gameplay NOT_TESTED; nenhuma prova de codigo valido; modelo nao promovido.

A causa provavel e uma combinacao: **apenas ~116 mil parametros e 128 caracteres de contexto**, apenas 180 passos de treino misturando codigos JS/Godot/Lua e poucos exemplos originais Lua. O teste nao mede uma taxa de sucesso real de jogos; ele demonstra apenas que os 3 resultados nao continham estrutura minima de funcao Lua.

### Luna Lua V2 - experimento de aprendizagem do ZERO com codigo original

O novo train_original_lua_v2.py usa somente as **6 funcoes Lua originais** de original_lua_gameplay.lua, ja presentes no repositorio. Nao le Elsword nem arquivos comerciais. Ele usa a classe LunaMiniCoder com nova configuracao, janela de 256 caracteres, largura 128, 4 camadas, 4 cabecas e inicializacao aleatoria. Treina 24 exemplos (6 mecanicas x 4 formulacoes), com perda aplicada somente a continuacao de codigo, em vez de gastar a maioria dos passos prevendo o texto dos prompts. Tambem alterna janelas alinhadas ao inicio da tarefa e segmentos internos das funcoes.

- O treino gera pesos NOVOS, em external_data/lua-v2-... ignorado pelo git, e nunca altera o checkpoint V0;
- O codigo e somente original Luna; modelos pretreinados Qwen/Ollama nao entram;
- A metrica de treino e previsao de caracteres em exemplos vistos: ela **nao prova generalizacao**;
- O benchmark_original_lua_v2.py repete os 3 desafios originais holdout, sem respostas no treino, mede apenas padroes lexicais, NUNCA executa o codigo gerado;
- O experimento pode continuar produzindo texto incoerente. Com so seis referencias, risco forte de memorizacao; e necessario corpus original maior e testes de sintaxe/funcionalidade para evoluir.

No Windows, atualizar a branch e usar menu **16** para iniciar 600 passos ou **17** para avaliar V2 depois do treino. Via PowerShell:

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Falha no git pull" }
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\train_original_lua_v2.py" --steps 600 --batch 4 --threads 4
if ($LASTEXITCODE -ne 0) { throw "Falha ao treinar a Luna V2" }
& $py "$lab\benchmark_original_lua_v2.py"
~~~

A avaliacao so deve ser interpretada comparativamente com a baseline V0 do usuario, de 0/3 assinaturas detectadas. O modelo V2 nao substitui a Luna atual automaticamente e nao pretende recriar um jogo comercial.


## Resultado V2 real: treino melhor, generalizacao ainda 0/3 (28/10/2026)

O usuario treinou a V2 scratch e executou o benchmark local:
- checkpoint lua-v2-20261028-185228-215159, SHA256 86acaa4755627bcb42f6e413138b8bea9da6b8307ded3c23721fb443522b11cf;
- loss em janelas de TREINO 72.9614 -> 0.96618 (melhora muito, MAS nao e validacao holdout);
- tarefas novas: boss_attack_phases, enemy_line_of_sight e one_way_platform;
- 0/3 assinaturas de funcao, fragmentos de texto incoerente;
- sintaxe e gameplay NOT_TESTED, modelo nao promovido, arquivos comerciais nao usados.

O diagnostico correto e: memorizar padroes de seis funcoes nao basta para criar jogos. A reducao de 98.7% na perda de TREINO nao prova transferencia. Nao aumentar steps aleatoriamente nem liberar pasta Elsword para compensar.

### Opcao 18 - Diagnosticar decoder, sobreajuste e sintaxe

A opcao 18 e nova e executa benchmark_original_lua_v2.py com as opcoes greedy, calibrate e syntax:
- decodificacao greedy (temperatura zero) para verificar se o problema decorre parcialmente da amostragem estocastica;
- training_prompt_calibration testa uma tarefa realmente presente no treino; se essa reproduz codigo e o holdout nao, evidencia adicional de memorizacao;
- lua_syntax usa luac -p se instalado para analisar o codigo gerado, sem executa-lo. Se ausente, retorna UNAVAILABLE_NO_LUAC;
- nenhuma nova etapa de treino; nenhum checkpoint modificado; nenhum arquivo comercial lido ou enviado;
- nenhuma garantia de Lua valido sem o parser, nenhum teste de gameplay e nenhuma promocao do modelo.

PowerShell, depois do git pull:

~~~powershell
$repo="$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Falha no git pull" }
$lab=Join-Path $repo "experiments\luna-forge-zero"
$py=Join-Path $lab ".venv\Scripts\python.exe"
& $py "$lab\benchmark_original_lua_v2.py" --decode greedy --calibrate --syntax --chars 240
~~~

Sem o parser luac, o modelo pode ser analisado, mas sintaxe fica indisponivel. Para treino posterior: desenvolver corpus proprio maior e diverso, holdout por mecanica e projeto, testes funcionais reais e contexto suficiente para uma funcao completa. Sinais lexicais e loss de treino nao justificam declarar a Luna pronta para programar.
