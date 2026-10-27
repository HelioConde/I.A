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

## Infraestrutura — configuração ativa (27/10/2026)

**Source: GitHub Actions** em Settings → Pages. A aplicação web reside em `site/` e é publicada pelo [workflow Luna Pages — Publish (GitHub Actions)](../.github/workflows/pages-manual-publish.yml) sempre que seus arquivos, os testes ou o próprio workflow são alterados na `main`. Também existe a execução manual pela aba Actions.

O workflow executa a validação estática `node site-tests/static-smoke.cjs` antes de enviar exclusivamente `site/` por `actions/upload-pages-artifact` e `actions/deploy-pages`. O workflow [Visual QA](../.github/workflows/pages.yml) executa Playwright separadamente. O Pages não requer PHP, Python, MySQL, SQLite, serviços de IA ou backend.

**Resultado confirmado:** o [deploy #40482973325](https://github.com/HelioConde/I.A/actions/runs/40482973325) terminou com sucesso. O [Publication Health #40481044717](https://github.com/HelioConde/I.A/actions/runs/40481044717), tentativa 3, confirmou HTTP 200 em `https://helioconde.github.io/I.A/` e em quatro arquivos essenciais (`app.js`, `styles.css`, `manifest.webmanifest`, `service-worker.js`).

Os arquivos usam caminhos relativos `./` para funcionar sob o prefixo `/I.A/`. O workflow não publica diretórios experimentais como `brain_data/`, `results/`, `src/`, executáveis ou bancos de dados.

**Atenção:** a branch `gh-pages` é apenas um snapshot histórico e não deve ser selecionada em Settings → Pages enquanto a publicação por GitHub Actions estiver ativa. A origem por branch causou confusão durante as tentativas iniciais. O 404 foi resolvido após a adoção do workflow oficial de publicação.

## Modelo de dados

Chave LocalStorage: `brain-ssd-luna-demo-v1`.
Formato: `{version: 1, conversations: [...], activeId: string|null}`.

Cada conversa possui `id`, `title`, `createdAt`, `updatedAt` e `messages`, com papéis `user` e `assistant`. Importações JSON são validadas (até 2 MB, 150 conversas, 250 mensagens por conversa, texto individual limitado); a interface não usa `innerHTML` para mostrar entradas.

LocalStorage não é criptografado: evite dados sensíveis, especialmente em máquinas compartilhadas. Não há sincronização entre dispositivos; exporte antes de limpar os dados do navegador. A falha de armazenamento gera alerta para exportação.

## Design, acessibilidade e testes

Consulte [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).
O workflow `.github/workflows/pages.yml` executa Playwright e salva capturas/screenshots como artefatos quando os runners estiverem disponíveis. A navegação de teste parte de `/site/` para reproduzir a publicação com prefixo de diretório. O workflow de publicação executa os testes estáticos; o Playwright é executado em um workflow de QA independente.

Testes requeridos: navegação, semântica, histórico, renomeação, exclusão, importação/exportação, interrupção, ausência de chamadas `/api`, screenshots responsivos, overflow, teclado e tratamento de erros de console.

## Revisão de segurança

O repositório contém artefatos de pesquisa, resultados grandes e dados de referência. Antes de alterar a visibilidade do repositório, revisar **separadamente todo o histórico Git**, além dos arquivos atuais, procurando credenciais, logs e informações pessoais. Tornar o repositório público só para ativar Pages pode expor o histórico inteiro; preferir hospedar apenas os artefatos estáticos em repositório próprio quando necessário.

## Melhoria V2 — 27/10/2026

- Corrigida a exibição de componentes com o atributo HTML `hidden`, garantindo que boas-vindas, botões e avisos respeitem os estados da interface.
- Importar um JSON exige confirmação antes de substituir conversas existentes; cancelar não apaga o histórico.
- Sincronização entre abas contempla a remoção da chave LocalStorage.
- Manifest e service worker para a versão estática: somente o shell público do aplicativo é cacheado, **nunca dados de conversas**. Respostas continuam demonstrativas também offline.
- Banner acessível em caso de indisponibilidade de conexão e controles maiores em telas móveis.
- Política CSP HTML restringe scripts, estilos e conexões à própria origem.
- `node site-tests/static-smoke.cjs` executa verificações sem dependências; `site-tests/` mantém Playwright e capturas reais quando disponível.
- **Atenção:** o repositório estava público na verificação desta atualização. Branches protegidas e artefato Pages não impedem leitura pública de outros arquivos e commits. Audite histórico e dados antes de considerar seguro para publicação.

## Diagnóstico adicional — GitHub Actions / HTTP 404 (27/10/2026)

Foi executado o workflow [Publication Health — run 40481044717](https://github.com/HelioConde/I.A/actions/runs/40481044717), com dois estágios independentes:

- **Verify gh-pages snapshot: SUCESSO.** Todos os arquivos de `site/` correspondem ao conteúdo da branch `gh-pages` (incluindo manifesto e service worker).
- **Verify public HTTP endpoints: FALHA.** O GitHub Actions alcançou o domínio, mas recebeu **HTTP 404** repetidamente em `https://helioconde.github.io/I.A/`, `app.js`, `styles.css`, `manifest.webmanifest` e `service-worker.js`. Uma segunda tentativa após atualização pela API de conteúdos também retornou 404.

O erro é de publicação/URL, não uma falha dos testes de UI. Confirmar no GitHub: **Settings → Pages → Build and deployment → Deploy from a branch → Branch: gh-pages → Folder: /(root) → Save**. Verificar se a seção GitHub Pages mostra **Visit site** e qual é o endereço publicado. Se o endereço for diferente, atualizar a URL dos testes em `.github/workflows/pages-health.yml`.

### Alternativa pronta: publicação por GitHub Actions

Existe o workflow [Luna Pages — Manual Publish (GitHub Actions)](../.github/workflows/pages-manual-publish.yml). Para utilizá-lo, selecionar **Settings → Pages → Build and deployment → Source: GitHub Actions**, e em **Actions → Luna Pages — Manual Publish (GitHub Actions) → Run workflow**. Ele valida o HTML/JS e publica somente `site/` com `actions/upload-pages-artifact` e `actions/deploy-pages`. Não roda automaticamente enquanto a configuração por branch estiver sendo utilizada.

**Não há necessidade de apagar a branch `gh-pages` ou publicar o backend Python.** O workflow alternativo não altera arquivos experimentais.

## Estado final — GitHub Actions confirmado

- Publicação: **sucesso** no run `40482973325`.
- Saúde HTTP: **sucesso** na terceira tentativa do run `40481044717`, incluindo resposta 200 do endereço principal e quatro recursos estáticos.
- Não alterar a fonte em Settings → Pages para `Deploy from a branch`, salvo se houver decisão consciente de migrar a arquitetura de publicação.
