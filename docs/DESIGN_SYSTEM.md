# Luna / Brain-SSD — Design System (GitHub Pages)

> Versão 1 — 27/10/2026. Escopo: demonstração estática em `site/`. A identidade do Brain-SSD Windows permanece intacta.

## Objetivo visual

Uma estação de trabalho de IA local: atmosfera de laboratório noturno, linguagem transparente sobre capacidades e interface de conversa serena. A identidade Luna combina um astro de quatro pontas com círculos orbitais; não imita indicadores de processamento reais no GitHub Pages.

## Tokens CSS (fonte de verdade: `site/styles.css`)

| Token | Valor | Utilização |
| --- | --- | --- |
| `--bg` | `#0b101b` | plano de fundo |
| `--canvas` | `#0d1220` | área de trabalho |
| `--surface` | `#111827` | superfícies |
| `--surface-hi` | `#161f31` | camadas elevadas |
| `--edge` | `#26324b` | divisores |
| `--text` | `#f0f4ff` | títulos e conteúdo |
| `--muted` | `#9aa8c3` | textos secundários |
| `--brand` | `#a5a4fc` | acentos Luna |
| `--teal` | `#72d4c6` | privacidade |
| `--danger` | `#ffa5ae` | exclusão |
| `--focus` | `#b9d7ff` | foco visível |

Escala de espaçamento `--space-1/2/3/4/5/6/8`: 4, 8, 12, 16, 20, 24 e 32 px. Raios `--radius-sm` 9 px, `--radius` 14 px, `--radius-lg` 20 px e `--radius-xl` 28 px.

Tipografia: stack de sistema (`Inter` se estiver instalada, seguida por `ui-sans-serif` e `system-ui`); títulos com tracking discreto negativo; corpo 12–14 px na área principal e 10–12 px nas legendas. Nenhum font/CDN é requisitado.

## Estrutura

- **Sidebar:** marca e nova conversa, busca, lista navegável, ações importar/exportar/limpar e privacidade.
- **Cabeçalho:** título da conversa, indicador inequívoco de DEMONSTRAÇÃO e ajuda.
- **Boas-vindas:** identidade Luna e quatro sugestões funcionais, não cards decorativos.
- **Conversa:** elementos semânticos, textos inseridos via `textContent`, identificador visível de resposta guiada e cópia.
- **Composer:** `Enter` envia; `Shift+Enter` insere quebra; `Ctrl/Cmd+K` inicia conversa; limite 2.000 caracteres.
- **Painel direito:** fluxo CONCEITUAL e contadores locais; nunca métricas inventadas de CPU/RAM/SSD.
- **Diálogos:** `<dialog>` nativo para informações, renomear e confirmações destrutivas.

## Estados

- Normal, hover, `:focus-visible` com contorno de 2 px, disabled e ação em andamento.
- Toast com `role=status` para importação, exclusão, armazenamento bloqueado e ação interrompida.
- Confirmar destruição em diálogo antes da mutação; importação JSON substitui histórico somente após validação.
- Tratamento de `QuotaExceededError` ou bloqueio de LocalStorage com aviso de possível não persistência.
- `prefers-reduced-motion: reduce` desliga transições e animações. Os controles devem ser acessíveis sem efeitos visuais.
- Mobile: barra lateral em overlay, backdrop e botão com `aria-expanded`; painel de diagnóstico oculto em telas estreitas.

## Image to Code — interpretação de referências

Referência: layout legado `chat/index.html` e `chat/styles.css`; informações do `hud/`. Mantemos chat, sugestão de perguntas, histórico, identificação local e painel de etapas. O redesenho troca layout rígido por componentes responsivos, reforça contraste/estados/foco e separa o modo demonstrativo do backend. Nenhuma captura externa foi utilizada como evidência de resultado.

## Regras editoriais e limites

- Nunca usar "IA conectada", "Qwen ativo" ou métricas de hardware no modo Pages.
- Explicar que o histórico reside neste navegador e pode ser perdido após limpar dados.
- Links externos devem usar `rel="noopener noreferrer"`.
- Nunca inserir entrada do usuário via `innerHTML` ou `eval`.
- Não publicar `brain_data/`, `results/`, logs, modelos, SQLite, scripts Windows ou arquivos privados no artefato Pages.
- Validar design com Playwright nas resoluções 320×568, 390×844, 768×1024, 1366×768 e 1600×900, incluindo teclado e movimento reduzido.

## Revisão

O modo real Windows continua com a interface `chat/` e servidor Python existentes. Sua migração completa para os tokens visuais é um trabalho separado, para preservar compatibilidade e não misturar demonstração e inferência real.

## V2 — Acessibilidade, rede e PWA

- O seletor CSS global `[hidden]{display:none!important}` protege o contrato semântico de ocultação mesmo quando a classe define `display`.
- Alvos de toque mobile reforçados (botões essenciais com tamanho mínimo de 44 px); avisos de conectividade acessíveis via `role=status`.
- Manifest e service worker armazenam apenas HTML, CSS, JavaScript e ícones estáticos; histórico do usuário permanece exclusivamente no armazenamento do navegador.
- Política de segurança de conteúdo restringe scripts, conexão e workers à mesma origem. Evitar novos scripts embutidos ou dependências CDN.
- Importação JSON destrutiva é confirmada em diálogo nativo e não altera o histórico ao cancelar.
- Componentes demonstrativos nunca exibem métricas de CPU, RAM ou SSD fingindo dados reais.
- Testar os cenários offline, `localStorage.clear()` em outra aba e elementos com `hidden` via Playwright, não apenas por inspeção do código.
