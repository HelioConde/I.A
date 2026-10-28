<div align="center">
  <h1>🧠 Brain-SSD — Laboratório de IA Local</h1>
  <p><strong>Pesquisa aplicada sobre memória persistente, recuperação de contexto e execução de modelos locais em computadores pessoais.</strong></p>
  <p><img alt="Python" src="https://img.shields.io/badge/Python-Experimentos-3776AB?logo=python&logoColor=white"> <img alt="Windows" src="https://img.shields.io/badge/Windows-Launcher-2563eb"> <img alt="Status" src="https://img.shields.io/badge/status-pesquisa%20experimental-64748b"></p>
</div>

## A pergunta de pesquisa

**É possível manter um grande conjunto de conhecimentos em armazenamento persistente e recuperar apenas o contexto necessário para cada pergunta?**

O Brain-SSD explora componentes de memória, seleção de contexto e integração com modelos locais. A proposta é estudar **eficiência de memória, qualidade da recuperação e custo de execução**, não afirmar que um SSD substitui integralmente RAM ou que a arquitetura reproduz o cérebro humano.

> **Status científico:** hipótese experimental. Não há comprovação geral de superioridade em qualidade, velocidade ou consumo de memória sobre um modelo local convencional. Resultados dependem do hardware, modelo, dados e metodologia.

## O que existe no repositório

| Área | Conteúdo |
| --- | --- |
| `chat/` | Componentes da experiência de conversa local |
| `brain_data/` | Estruturas e dados de laboratório |
| `src/` | Núcleo dos experimentos |
| `launcher/` / `hud/` | Inicialização e interface Windows |
| `benchmarks/` / `results/` | Avaliações e resultados experimentais |
| `tests/` | Testes automatizados |
| `docs/` | Arquitetura, hipóteses e pesquisas |

Há scripts de preparação, diagnóstico e execução para **Windows** na raiz. Eles são meios de experimentar a aplicação, e podem exigir runtime de IA, modelo local e dependências adicionais.

## Começar no Windows

1. Clone o repositório e leia o [guia de configuração](docs/AUTO_SETUP_WINDOWS.md).
2. Use o script `PREPARAR-CHAT-WINDOWS.bat` para iniciar a preparação do ambiente conforme sua configuração.
3. Para experimentar o chat, há entradas como `INICIAR-CHAT-WINDOWS.bat` e `INICIAR-CHAT-MEMORIA-WINDOWS.bat`.
4. Se algo falhar, use o [guia de diagnóstico](docs/LOGS_DIAGNOSTICOS.md) e os scripts de logs/diagnóstico incluídos na raiz.

**Não há garantia de que qualquer máquina consiga executar o modelo escolhido**: memória, CPU, disco, permissões e runtime precisam ser compatíveis. Antes de executar arquivos `.bat`, revise seu conteúdo e mantenha backups de dados de teste.

## Arquitetura em alto nível

```text
Pergunta do usuário
        ↓
Preparação e seleção de contexto
        ↓
Recuperação de conhecimento/memórias relevantes
        ↓
Inferência por modelo local configurado
        ↓
Resposta e métricas de avaliação
```

Memória explícita, cache cognitivo, busca web e organização de fatos aparecem como **módulos e pesquisas** em diferentes estágios. Nem todos devem ser interpretados como funcionalidades prontas ou ativadas por padrão.

## Como avaliar com rigor

- Compare o resultado com uma **linha de base** sem o mecanismo experimental.
- Meça **RAM, latência, uso de disco e qualidade da resposta** sob as mesmas condições.
- Use conjuntos de testes reproduzíveis e registre parâmetros do modelo.
- Distinga recuperação de contexto de **treinamento de pesos**; o projeto não deve sugerir que consultas modificam automaticamente o modelo.
- Documente falhas e exemplos negativos, não apenas demonstrações bem-sucedidas.

## Documentação

[Arquitetura](docs/ARCHITECTURE.md) · [Hipóteses](docs/HYPOTHESIS_REGISTRY.md) · [Benchmarks](docs/BENCHMARKS.md) · [Roadmap](docs/ROADMAP.md) · [Guia de Windows](docs/CHAT_WINDOWS.md) · [Histórico técnico anterior](docs/README_HISTORY_2026-10-25.md)

**Criado por [Hélio Conde](https://github.com/HelioConde).** Projeto de pesquisa independente, sem alegações de equivalência biológica ou validação clínica.


## Demonstração web — Luna (GitHub Pages)

A nova experiência em [`site/`](site/) é uma **demonstração estática** do Brain-SSD/Luna, sem servidor ou banco de dados. Inclui layout responsivo, conversa com **respostas educativas pré-definidas**, histórico e busca no LocalStorage, importação/exportação JSON e painel conceitual. **Não executa Qwen nem simula métricas reais como resultados experimentais.**

- [Abrir a demonstração no Pages](https://helioconde.github.io/I.A/) — publicado via **GitHub Actions**, com HTTP 200 confirmado.
- [Arquitetura, diferenças entre modos e instruções de publicação](docs/GITHUB_PAGES.md).
- [Design System e critérios de acessibilidade](docs/DESIGN_SYSTEM.md).
- [Testes Playwright e screenshots](site-tests/tests/pages.spec.js).

O workflow [Luna Pages — Visual QA](.github/workflows/pages.yml) executa testes com Playwright; a publicação é realizada pelo workflow [Luna Pages — Publish (GitHub Actions)](.github/workflows/pages-manual-publish.yml), que envia **somente `site/`**. Para testar localmente, rode `python -m http.server 4173` na raiz e acesse `http://localhost:4173/site/`. Para testes de navegador, entre em `site-tests/`, rode `npm install`, `npx playwright install chromium` e `npm test` (Python deve estar disponível como `python3` no ambiente de teste).

**Histórico de publicação:** a branch [`gh-pages`](https://github.com/HelioConde/I.A/tree/gh-pages) permanece como snapshot estático, mas **não é mais a fonte ativa**. Settings → Pages deve continuar configurado em **GitHub Actions**.

**Privacidade:** o repositório foi identificado como público em 27/10/2026: revise os arquivos e histórico Git, mesmo que o Pages publique apenas arquivos estáticos. O modo Windows com Python, SQLite, experimentos e inferência real permanece separado.


### Melhorias V2

- Componentes realmente ocultos ao mudar de estado; alvos de toque e navegação mobile aprimorados.
- Importação JSON com confirmação antes de substituir conversas existentes e correções de sincronização entre abas.
- PWA offline para o **shell estático** (manifest + service worker); nenhuma mensagem pessoal entra no cache do service worker.
- CSP de origem única, banner de conexão e verificações estáticas sem dependências.
- QA: `node site-tests/static-smoke.cjs` na raiz e capturas Playwright em cinco resoluções via `site-tests/`.
- O deploy oficial é automático por GitHub Actions quando `site/`, `site-tests/` ou o workflow de publicação muda na `main`. A branch `gh-pages` não precisa ser atualizada para o Pages.


### Publicação verificada — 27/10/2026

- **Deploy:** [Actions run 40482973325](https://github.com/HelioConde/I.A/actions/runs/40482973325) — sucesso.
- **Verificação pública:** [Publication Health run 40481044717](https://github.com/HelioConde/I.A/actions/runs/40481044717), tentativa 3 — cinco respostas HTTP 200 (HTML, JS, CSS, manifest e service worker).
- **Site:** https://helioconde.github.io/I.A/
- **Fonte em Settings → Pages:** GitHub Actions, não `gh-pages`.

## Luna Code Studio — desafio de programação

O próximo alvo de capacidade é criar um **jogo original de ação em plataformas, inspirado nas mecânicas da Season 1 de Grand Chase**: movimento, combos, classes, inimigos, chefe e interface. Este é um **benchmark a atingir**, não um jogo já construído pela Luna. O código deverá ser criado por etapas com aprovação explícita e validado por Playwright e revisão visual. Os assets, a marca e o código original do jogo comercial não serão copiados.

- [Etapas e QA do Code Studio](docs/LUNA_CODE_STUDIO.md)
- [Benchmark de aceitação](benchmarks/arcade_s1/brief.json)
- [Testes Playwright para jogo candidato](site-tests/tests/game-benchmark.spec.js)
