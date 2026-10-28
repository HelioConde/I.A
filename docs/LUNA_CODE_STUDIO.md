# Luna Code Studio — benchmark Arcade S1

## Objetivo

Fazer a Luna sair de respostas isoladas e construir, por etapas, um **jogo original de plataforma/ação lateral inspirado nos sistemas de Grand Chase Season 1**. O jogo histórico tinha combate lateral, três estilos iniciais de personagem (guerreiro, arqueiro e mago), missões com monstros e chefe, lobby e PvP. São referências para mecânicas e UX, **não autorização para copiar código, sprites, sons, personagens, mapas ou marca comercial**.

O documento de requisitos executáveis está em [brief.json](../benchmarks/arcade_s1/brief.json). Ele é o alvo de aceitação, não uma alegação de que a Luna já criou o jogo.

### Metas de evolução

| Etapa | Entrega esperada |
|---|---|
| S0 | Arquitetura e interface inicial |
| S1 | Movimento, gravidade, colisão, salto e dash |
| S2 | Combos, hitboxes, HP/MP, inimigo de treino |
| S3 | Fases PvE, portas, IA de monstros e chefe |
| S4 | Três classes originais com habilidades distintas |
| S5 | Lobby, interface, efeitos, arte original e responsividade |
| S6 | PvP local; online só com backend autoritativo separado |
| S7 | Entrega ponta a ponta, Playwright e revisão manual |

A meta de 90/100 e os hard gates são usados somente após executar o jogo. A Luna não pode se atribuir nota sem build jogável, logs de teste, vídeo ou capturas reais e revisão humana.

### Como criar um primeiro projeto (versão experimental)

O Code Studio é uma ferramenta de **propostas e revisão**, não um agente autônomo completo. Execute no repositório Brain-SSD:

~~~powershell
python tools/code_studio.py prompt --stage s0-plan
~~~

O comando produz uma instrução para o modelo de programação gerar arquivos em **JSON** com a estrutura:

~~~json
{
  "version": 1,
  "goal": "Jogo original de plataforma - protótipo inicial",
  "files": [
    {"path": "index.html", "content": "<!doctype html>..."},
    {"path": "styles.css", "content": "..."},
    {"path": "src/game.js", "content": "..."}
  ]
}
~~~

Copie a resposta completa do modelo para `proposal.json`. Depois:

~~~powershell
python tools/code_studio.py review proposal.json
python tools/code_studio.py apply proposal.json --workspace "C:\projetos\luna-arcade-s1" --approve
~~~

**Crie o workspace manualmente antes de aplicar**. A aplicação só cria arquivos ainda inexistentes; não sobrescreve código ou executa scripts. `--approve` exige ação explícita do usuário. Cada proposta admite até 20 arquivos, 48 KB por arquivo e 250 KB ao todo, e exige JSON válido. Saídas truncadas são rejeitadas. O JSON não pode inventar ferramentas ou resultados de testes.

A saída do chat atual tem limite curto e o Qwen3-0.6B teve apenas 4/9 acertos no primeiro teste de inteligência. Portanto, no estágio atual **não é realista prometer que ele construa sozinho uma réplica completa**. Evolução necessária: conectar um modelo de código mais competente, planejar e gerar pequenos arquivos por iteração, recuperar contexto do projeto, compilar, testar, revisar e só aplicar sob permissão.

### Como validar uma versão de jogo com Playwright

Existem testes para **uma versão candidata existente** em [site-tests/tests/game-benchmark.spec.js](../site-tests/tests/game-benchmark.spec.js). Eles exigem menus e uma API diagnóstica de somente leitura:

- Identificadores DOM: `character-melee`, `character-ranged`, `character-magic` e `start-game` via `data-testid`.
- `window.__LUNA_GAME_QA__.snapshot()` retorna snapshot do **motor real**: `mode` (dungeon/pause/etc.), `player` com `archetype`, `x` e `y`, e `enemies` com `id`, `hp` e `training`.
- Um inimigo de treino próximo ao personagem é necessário para medir dano com a tecla Z. O QA não pode inventar estado independente do motor.

Inicie **um servidor estático local** apontando para o diretório com o jogo, por exemplo em outro terminal:

~~~powershell
cd C:\projetos\luna-arcade-s1
py -3 -m http.server 4799 --bind 127.0.0.1
~~~

E execute os testes, na pasta `site-tests` do Brain-SSD:

~~~powershell
npm install
npx playwright install chromium
$env:LUNA_GAME_URL = "http://127.0.0.1:4799"
npx playwright test --config playwright.game.config.cjs
~~~

Se nenhum jogo estiver rodando, esses testes **falham**, não retornam falso PASS. Eles ainda não verificam automaticamente fidelidade visual nem ciclo inteiro até o chefe: esses hard gates exigem evolução da automação e revisão humana.

### Critérios de qualidade

- 40 pontos: jogabilidade completa e funcional.
- 20 pontos: combate e diferenciação entre classes.
- 15 pontos: acabamento visual, UX e menus.
- 15 pontos: arquitetura, testes e manutenção.
- 10 pontos: performance e acessibilidade.

O GitHub Actions nesta rodada valida **segurança da ferramenta, sintaxe das propostas e consistência do benchmark**. Não substitui o Playwright do jogo candidato, que ainda não existe.

## Separação de projetos

Este capstone serve como prova de capacidade de programação da **Luna / Brain-SSD**. O jogo gerado deve morar em um **workspace de demonstração separado**, sem misturar o código original de outros jogos e sem reescrever a pesquisa experimental 4D/4E. É uma aplicação de engenharia, não prova de substituição de RAM por SSD.
