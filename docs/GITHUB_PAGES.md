# GitHub Pages — modo de demonstração Luna

## Separação de responsabilidades

O núcleo Brain-SSD mantém o servidor Python em `src/brain_ssd/chat/server.py`, runtime de IA local e persistência própria. A experiência **GitHub Pages** vive isoladamente em `site/` (HTML/CSS/JavaScript/SVG), sem importações do Python e sem acesso aos endpoints `/api/*`.

| Capacidade | Windows (chat local) | GitHub Pages |
| --- | --- | --- |
| Inferência Qwen | Disponível quando runtime/modelo configurados | **Não** |
| Streaming de tokens | Com servidor local ativo | **Não** |
| Recuperação experimental SSD | Conforme módulos e configuração | **Não** |
| Histórico | Persistência local do servidor | LocalStorage do navegador |
| Importação/exportação | Fluxo do aplicativo local | JSON versionado |
| Respostas | Modelo real no Windows configurado | **Somente roteiros demonstrativos** |
| Banco de dados no servidor | Pode usar SQLite local | **Não** |
| Indicadores | Conforme telemetria real | Apenas contagens locais e diagrama conceitual |

## Infraestrutura

O workflow `.github/workflows/pages.yml` publica exclusivamente o diretório `site/` com `upload-pages-artifact` e `deploy-pages`. Nenhum `brain_data/`, `results/`, modelo, log, script ou SQLite integra o artefato do Pages.

O site usa caminhos relativos `./styles.css`, `./app.js` e `./favicon.svg`. Assim funciona em um projeto Pages localizado em `/I.A/`, não apenas na raiz de um domínio.

**Ativação padrão:** no GitHub, Settings → Pages → Build and deployment → Source: **GitHub Actions**. Em repositórios privados, a elegibilidade do Pages depende do plano/conta. Caso não esteja disponível, o código estático pode ser disponibilizado em um repositório público separado sem expor o núcleo experimental.

**Fallback sem runner GitHub Actions:** foi criada a branch `gh-pages` com SOMENTE quatro arquivos na raiz (`index.html`, `styles.css`, `app.js`, `favicon.svg`). Em Settings → Pages, escolha **Deploy from a branch → gh-pages → /(root) → Save**. Esse método usa o publicador de Pages e não requer rodar Playwright para servir arquivos estáticos. A publicação ainda depende da elegibilidade do Pages; essa branch é um snapshot manual e não se sincroniza automaticamente com `site/` após novas alterações.

**Validação em 27/10/2026:** uma execução do workflow de Playwright falhou antes do início dos steps, com `runner_id=0`. O motivo detalhado não estava disponível pelo log retornado; não há screenshots reais nem status verde de testes. Antes de marcar QA como concluído, consulte a página do run no GitHub, corrija a indisponibilidade dos runners e execute novamente.

## Modelo de dados

Chave LocalStorage: `brain-ssd-luna-demo-v1`.
Formato: `{version: 1, conversations: [...], activeId: string|null}`.

Cada conversa possui `id`, `title`, `createdAt`, `updatedAt` e `messages`, com papéis `user` e `assistant`. Importações JSON são validadas (até 2 MB, 150 conversas, 250 mensagens por conversa, texto individual limitado); a interface não usa `innerHTML` para mostrar entradas.

LocalStorage não é criptografado: evite dados sensíveis, especialmente em máquinas compartilhadas. Não há sincronização entre dispositivos; exporte antes de limpar os dados do navegador. A falha de armazenamento gera alerta para exportação.

## Design, acessibilidade e testes

Consulte [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).
O workflow `.github/workflows/pages-qa.yml` executa Playwright e salva capturas/screenshots como artefatos. A navegação de teste parte de `/site/` para reproduzir a publicação com prefixo de diretório. O job Pages executa os mesmos testes antes de publicar.

Testes requeridos: navegação, semântica, histórico, renomeação, exclusão, importação/exportação, interrupção, ausência de chamadas `/api`, screenshots responsivos, overflow, teclado e tratamento de erros de console.

## Revisão de segurança

O repositório contém artefatos de pesquisa, resultados grandes e dados de referência. Antes de alterar a visibilidade do repositório, revisar **separadamente todo o histórico Git**, além dos arquivos atuais, procurando credenciais, logs e informações pessoais. Tornar o repositório público só para ativar Pages pode expor o histórico inteiro; preferir hospedar apenas os artefatos estáticos em repositório próprio quando necessário.
