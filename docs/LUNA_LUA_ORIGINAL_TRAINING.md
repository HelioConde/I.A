# Luna GameCoder — resultados dos 5.902 arquivos Lua e currículo original testável

Atualizado em 2026-10-28. Os números abaixo foram fornecidos diretamente pelo usuário após as auditorias locais. Não houve acesso remoto ao conteúdo de nenhum script, nem download de seus arquivos privados.

## Auditoria realizada localmente

- 7.435 arquivos no diretório, 168 subpastas, aproximadamente 7,78 GB.
- 5.902 com extensão `.lua`. A amostragem de 4 KiB classificou **5.789 como candidatos a texto UTF-8**, 94 como codificação/desconhecido, 18 como bytecode Lua/KL e 1 vazio.
- A segunda amostragem de 64 KiB agregou estruturas lexicais: 1.520 com funções e controle de fluxo, 94 com funções apenas, 78 com controle apenas e **4.097 sem nenhuma das duas estruturas detectadas na amostra**.
- Contagens aproximadas: `function` 18.531, `if` 29.485, `return` 5.350. 399 arquivos ultrapassam 64 KiB e foram analisados parcialmente.
- Erros 0; arquivos extraídos, exportados e usados no treinamento **0**.

Importante: estas são contagens por palavras-chave e formato. Não comprovam sintaxe válida, relação com gameplay ou autorização para treinamento. Os scripts podem pertencer aos desenvolvedores originais do jogo. Arquivos .bak podem conter dados sensíveis; não devem ser carregados. Nenhum dos 5.902 arquivos é automaticamente permitido para treinamento.

## Mudança implementada no Luna Forge

Criado do zero, sem copiar qualquer código do cliente, o módulo `experiments/luna-forge-zero/original_lua_gameplay.lua` contém **seis mecânicas** de plataforma/combat:

1. `horizontal_motion`: movimento com aceleração e orientação;
2. `grounded_jump`: pulo, gravidade e aterrissagem;
3. `three_hit_combo`: sequências de três golpes com janela de combo;
4. `damage_and_invulnerability`: dano, recuo e invulnerabilidade;
5. `rectangle_hitbox`: colisão retangular;
6. `enemy_patrol`: patrulha com limites.

O código **escrito e testado pela equipe da Luna** é executado isoladamente por `test_original_lua_gameplay.lua` em Lua 5.4 no CI, com 32 asserções aprovadas. Não execute arquivos Lua retirados do cliente; o runner só executa o módulo novo de autoria do laboratório.

O arquivo `original_lua_lessons.py` verifica a proveniência interna e exporta somente esses seis exemplos para a GameCoder, deixando **três desafios sem respostas** separados (fases de chefe, percepção de inimigo e plataforma atravessável). Esses exercícios permitem melhorar nossa metodologia, mas ainda não demonstram aprendizado de programação robusto.

## Treinamento e avaliação

O script `train_github.py --lua-lessons` combina:
- 19 arquivos de código de jogos externos MIT fixados em commits, conforme `github_corpus.py`;
- oito exemplos de JavaScript/GDScript originais;
- seis exemplos de Lua originais;
- um repositório externo inteiramente reservado para avaliação de previsão de caracteres.

Os arquivos comerciais continuam **fora** do corpus. Os novos pesos são guardados em uma pasta de candidato isolado, sem promoção para a Luna principal. O novo avaliador `evaluate_lua_codegen.py` verifica a sintaxe dos trechos **gerados pela própria GameCoder** usando apenas o compilador `luac -p`, sem executar o código. Testes funcionais do modelo continuam pendentes.

### Rodada confirmada no GitHub

[Actions 40721068091](https://github.com/HelioConde/I.A/actions/runs/40721068091): 6 exemplos Lua em treinamento, 32 testes funcionais do módulo original aprovados, perda do holdout externa 35,617649 → 3,304493. O modelo gerou **0/5 JavaScript válido**. O código de referência passou, o modelo ainda não demonstrou competência de escrita de gameplay.

## Como usar no seu Windows

```powershell
$repo = "$env:USERPROFILE\Documents\Luna-Forge-Local"
git -C "$repo" pull --ff-only
$lab = Join-Path $repo "experiments\luna-forge-zero"
& "$lab\.venv\Scripts\python.exe" "$lab\original_lua_lessons.py" verify
& "$lab\ABRIR-LUNA-FORGE.cmd"
```

Selecione **opção 4** e confirme `SIM` para gerar um **novo candidato de pesos** usando os projetos MIT externos e os 14 exemplos originais. O menu não usa `C:\Users\helio\Documents\grand chase files`. Nenhuma transferência dos arquivos privados é necessária. Se o ambiente estiver instalado em `Luna-Forge-Local-2`, ajuste o prefixo `$repo`.

Para exportar os seis exemplos originais em um arquivo de treinamento separado:

```powershell
& "$lab\.venv\Scripts\python.exe" "$lab\original_lua_lessons.py" export --out "$lab\external_data\lua_aulas_originais.jsonl"
```

**Limitação:** mini-modelo de ~116 mil parâmetros, contexto de 128 caracteres e ausência de sintaxe/funcionalidade comprovada na geração. A prioridade técnica seguinte é modelo de código maior e avaliações executáveis isoladas, sem copiar um jogo comercial.
