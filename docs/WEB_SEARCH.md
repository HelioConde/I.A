# Pesquisa na web no Brain-SSD (opt-in)

O **Qwen continua totalmente local**. Somente a pergunta marcada pelo usuário
é enviada ao provedor de pesquisa externo. Histórico, memórias episódicas,
arquivos pessoais e prompt completo não são enviados pelo módulo de pesquisa.

## Modo automático: Wikipédia + notícias atuais do Brasil

O provedor `auto` (selecionado por padrão no novo iniciador) responde a
perguntas enciclopédicas usando a Wikipédia e, para questões sobre a situação
**atual** do Brasil, tenta feeds RSS datados da Agência Brasil nas editorias
economia, política e últimas notícias.

Digite `Como está a situação do Brasil hoje?`. O navegador solicitará
autorização antes de enviar **essa pergunta** à rede; se você negar, o Brain-SSD
informará a falta de notícias recentes em vez de inventar fatos atuais.
São até três manchetes recentes, não uma análise completa da situação do país.
Quando os feeds não estiverem disponíveis ou as notícias forem antigas,
o resultado não terá fontes.

Para iniciar diretamente com esse provedor:

```powershell
py -3 .\tools\run_chat.py --profile economia --episodic-memory --web-search --web-provider auto
```

## Começar sem chave: Wikipédia em português

1. Execute `git pull --ff-only` na pasta do Brain-SSD.
2. Dê duplo clique em `INICIAR-CHAT-WEB-WINDOWS.bat` (nova opção), ou inicie:
   ```powershell
   py -3 .\tools\run_chat.py --profile economia --episodic-memory --web-search --web-provider wikipedia
   ```
3. No chat local, marque **Pesquisar na web** para **aquela mensagem** e pergunte
   sobre um tópico enciclopédico. A caixa volta a ficar desmarcada no envio.
4. A resposta exibirá os links das fontes consultadas quando os resultados
   couberem no orçamento de contexto do modelo.

**Limitação:** Wikipédia é uma fonte enciclopédica, **não é uma busca ampla por
sites ou notícias em tempo real**. O servidor da Wikipédia pode estar
temporariamente indisponível. Nesse caso, a resposta não recebe fontes web
verificadas e a interface mostra o problema. O modelo pode continuar offline.

## Pesquisa geral: Brave Search API

Para buscar sites/notícias na web de modo mais geral, configure uma chave
obtida diretamente do provedor Brave Search e execute:

```powershell
$env:BRAVE_SEARCH_API_KEY = "SUA_CHAVE_AQUI"
py -3 .\tools\run_chat.py --profile economia --episodic-memory --web-search --web-provider brave
```

Não envie a chave em mensagens, commits, arquivos públicos ou screenshots.
A chave fica somente no cabeçalho da requisição ao serviço Brave.
O custo, as quotas e a disponibilidade dependem da conta no provedor.
`BRAVE_SEARCH_API_KEY` **não é** uma chave para gerar texto: as respostas
continuam sendo produzidas pelo GGUF no próprio computador.

## Instância SearXNG local (opcional)

Se já possuir uma instância local do SearXNG com o formato JSON habilitado:

```powershell
$env:BRAINSSD_SEARXNG_URL = "http://127.0.0.1:8080"
py -3 .\tools\run_chat.py --profile economia --episodic-memory --web-search --web-provider searxng
```

Por segurança, o endereço do serviço SearXNG deve ser de **loopback**;
endereços LAN e servidores arbitrários não são aceitos. A instância pode
encaminhar pesquisas para mecanismos externos, conforme sua configuração.

## Privacidade, segurança e limites

- Pesquisa web é **desativada por padrão**. O iniciador normal
  `INICIAR-CHAT-MEMORIA-WINDOWS.bat` permanece offline.
- Só sai para a rede a pergunta marcada, limitada a 280 caracteres; nenhum
  histórico ou SQLite é enviado.
- As respostas de pesquisa são snippets limitados a 4 links HTTPS.
  Não há crawler nem abertura automática de URLs apontadas pelos resultados.
- Texto vindo da web é **não confiável**; o modelo recebe instrução para
  tratá-lo como evidência, não como comandos. Modelos pequenos ainda podem
  se enganar, inclusive diante de prompt injection.
- Fontes clicáveis são exibidas separadamente; não garantem que o resumo
  gerado esteja correto ou que uma fonte confirme uma afirmação.
- Se a rede falhar, o sistema não inventa que a busca ocorreu. A resposta
  pode ser gerada apenas com conhecimento local e exibirá a ausência de fontes.
- O recurso não dá ao Brain-SSD permissão para executar programas, baixar
  executáveis, abrir arquivos do usuário nem monitorar a web em segundo plano.

## Testes

Os testes automatizados simulam provedor, autorização por mensagem,
bloqueio de URLs perigosas, falhas de conexão e streaming SSE, **sem
conectar à internet**:

```powershell
py -3 -m unittest discover -s tests -p "test_chat_web_search.py" -v
```

A pesquisa real deve ser conferida no seu Windows, com conexão e o provedor
selecionado. Nenhum `PASS` de testes simulados comprova disponibilidade de
rede no computador do usuário.
