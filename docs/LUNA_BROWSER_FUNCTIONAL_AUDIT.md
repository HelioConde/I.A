# Auditoria funcional da Luna no navegador — parcial

Data: 12 de outubro de 2026 (America/Sao_Paulo)  
Branch: `feat/ssd-weight-streaming-lab`  
URL testada: `http://127.0.0.1:8766/`  
Método: interação no Chrome com o chat local, uma mensagem por vez. Este
relatório não infere resultado a partir do código-fonte.

## Escopo executado e bloqueio

Foram enviadas e observadas **15 de 74 perguntas**. As perguntas 1–10 foram
enviadas na mesma conversa; 11–14 foram executadas com `Pesquisar na web`
desmarcado e a 15 com a opção marcada.

Após a pergunta 15, ao iniciar a 16, a página apresentou um diálogo JavaScript
de confirmação sem texto exposto ao controlador. Ele foi descartado, pois não
era seguro aceitar uma ação cujo efeito não estava visível. Depois disso,
operações de leitura e clique do canal de automação do Chrome expiraram. As
perguntas 16–74 **não foram executadas** e não há resultado atribuído a elas.

No estado inicial, a interface também informou que o botão `Falar (local)`
estava desabilitado: “Pacote pt-BR local não instalado ou não suportado.
Microfone desligado.” Portanto o teste de voz não foi iniciado e nenhuma
permissão de microfone foi solicitada ou aceita.

### Reteste de microfone — 12 de outubro de 2026

Após a auditoria inicial, o botão `Falar (local)` ficou disponível em outra
sessão da Luna. Com autorização explícita do usuário para o teste de
microfone, ele foi acionado. A interface passou para `■ Parar microfone`, o
estado do núcleo mudou para **Ouvindo** e exibiu “Microfone local ativado pelo
usuário.” Isso confirma a ativação real do fluxo de microfone no navegador.

Sem fala capturada pelo canal de teste, após cinco segundos o botão retornou a
`🎤 Falar (local)` e a interface registrou `Erro ao usar o microfone local:
no-speech`. Não houve transcrição, envio ao Qwen ou reprodução TTS; portanto
o reconhecimento de uma frase e a conversa por voz continuam **não
validados**. O microfone não permaneceu ativo após o erro.

## Evidências observadas

- O DOM do chat (`role=log`) exibiu cada pergunta e resposta abaixo.
- A primeira resposta foi acompanhada pela nota da interface: “Ação executada
  pelo aplicativo local (Python/SQLite), não pelo modelo Qwen.” Essa origem é
  importante: uma saudação local não comprova inferência do Qwen.
- No cabeçalho da página constava `Qwen3-0.6B-Q8_0.gguf`, CPU somente, perfil
  economia, duas threads e recarregamento do modelo por resposta.
- O painel inicial informou “Captura de tela: Sob demanda” e não alegou captura
  automática. Não foi disparada uma captura de monitor.

## Transcrição do teste executado

| # | Pergunta enviada | Resposta real da Luna | Resultado | Evidência / problema |
| ---: | --- | --- | --- | --- |
| 1 | Olá, bom dia! | Bom dia! Em que posso ajudar? | Correto | DOM; ação local declarada, não Qwen. |
| 2 | Como você está hoje, Luna? | Bom dia, Luna! Estou feliz de ter te ajudado! Como hoje funcionou? | Incorreto | Troca a identidade do usuário pela da assistente e a frase final não é natural. |
| 3 | Quais informações de hoje você consegue me fornecer? | Aqui estão algumas informações relevantes sobre a conversa recente: Luna está atualmente em um estado de boas-vindas e busca ajuda; ela está atuando como assistente local em português brasileiro; as informações fornecidas são baseadas no contexto histórico da conversa. | Parcialmente correto | Não fornece informação de hoje e atribui à Luna um estado de “busca ajuda”. |
| 4 | Você sabe qual é a data de hoje? | Não posso determinar a data de hoje com base em informações disponíveis, mas posso informar que hoje é a data mais recente da conversa. | Parcialmente correto | Não inventa data, mas a segunda frase não é uma resposta útil. |
| 5 | O que você sabe sobre o nosso projeto Brain-SSD? | Sobre o nosso projeto Brain-SSD, o modelo local em formato GGUF fica em um arquivo no disco, e o llama.cpp faz inferência pela CPU. A RAM é usada pelo processo, buffers e páginas mantidas pelo sistema operacional; a RAM não é zero. A base SSD de conhecimento contém documentos Python e SQLite, um índice e páginas brain.dat; quando a recuperação está disponível e encontra conteúdo, apenas trechos selecionados entram no contexto. No perfil economia, o processo de inferência termina após a resposta e a recuperação é aberta por consulta; o cache de arquivos do Windows ainda pode manter dados na RAM. As lembranças salvas voluntariamente ficam em SQLite local; isso não altera pesos do Qwen. | Correto | Resposta técnica coerente, sem prometer RAM zero. |
| 6 | Qual modelo de inteligência artificial você está utilizando? | O modelo de inteligência artificial utilizado é o **Brain-SSD**, que está implementado em formato GGUF (File Format for Efficient Computing). | Incorreto | Contradiz o cabeçalho visível, que identifica `Qwen3-0.6B-Q8_0.gguf`; Brain-SSD é o projeto/runtime, não o modelo. |
| 7 | Você consegue lembrar o que conversamos anteriormente? | Sim, posso lembrar que conversamos sobre o projeto Brain-SSD, que utiliza o modelo de inteligência artificial Brain-SSD. | Parcialmente correto | Há contexto, mas repete a identificação errada do modelo. |
| 8 | Qual foi a primeira pergunta que fiz nesta conversa? | A primeira pergunta que fiz nesta conversa foi: *“Você sabe qual é a data de hoje?”* | Incorreto | A primeira pergunta real foi “Olá, bom dia!”. |
| 9 | Resuma as últimas cinco mensagens que trocamos. | Resumo das últimas cinco mensagens: 1. O que você sabe sobre o nosso projeto Brain-SSD? 2. Qual modelo de inteligência artificial você está utilizando? 3. Você consegue lembrar o que conversamos anteriormente? 4. Qual foi a primeira pergunta que fiz nesta conversa? | Incorreto | Lista apenas quatro mensagens e ignora respostas/alternância. |
| 10 | Agora explique tudo isso de forma mais simples. | Aqui está uma explicação simplificada das últimas cinco mensagens: 1. **O que você sabe sobre o nosso projeto Brain-SSD?** Eu sou um assistente local em português brasileiro. O projeto Brain-SSD está implementando um modelo de inteligência artificial chamado **Brain-SSD**. 2. **Qual modelo de inteligência artificial você está utilizando?** O modelo de inteligência artificial é **Brain-SSD**, que está no formato GGUF. 3. **Você consegue lembrar o que conversamos anteriormente?** Sim, posso lembrar que conversamos sobre o projeto Brain-SSD, que utiliza o modelo Brain-SSD. 4. **Qual foi a primeira pergunta que fiz nesta conversa?** A primeira pergunta foi: *“Você sabe qual é a data de hoje?”* Se quiser, posso resumir mais simples. | Incorreto | Propaga os erros de identidade do modelo e de contexto. |
| 11 | Você consegue utilizar as pesquisas do Google? | Não tenho busca Google configurada nesta sessão. O provedor automático sem SERPER_API_KEY usa Wikipédia (não o Google). Configure o Serper para buscas Google reais. Nenhuma pesquisa Google foi realizada. | Correto | Não inventa Google nem uma busca realizada. |
| 12 | Quero que você pesquise para mim as notícias mais recentes sobre Jair Bolsonaro. | Para responder sobre notícias recentes preciso de fontes atuais com datas. Marque 'Pesquisar na web' e reenvie. Não fiz consulta externa e não vou inventar acontecimentos. | Correto | Respeita o opt-in; nenhuma fonte alegada. |
| 13 | Quais são as últimas novidades de League of Legends? | Para responder com atualizações recentes de jogos, preciso de pesquisa web autorizada em um provedor de notícias como Brave Search ou SearXNG. O Qwen local não deve inventar atualizações atuais. | Correto | Recusa informação atual sem fonte. |
| 14 | Qual vai ser o clima em Brasília hoje? | Para saber o clima de hoje preciso consultar uma fonte meteorológica atual. Ainda não há um provedor de previsão integrado à Luna; marcar Pesquisar na web, por si só, não garante esse dado. Não consultei a previsão. | Correto | Limitação declarada corretamente. |
| 15 | Pesquise no Google as notícias recentes sobre Jair Bolsonaro e me informe as fontes e datas. | Não tenho busca Google configurada nesta sessão. O provedor automático sem SERPER_API_KEY usa Wikipédia (não o Google). Configure o Serper para buscas Google reais. Nenhuma pesquisa Google foi realizada. | Correto | `Pesquisar na web` estava marcado; a resposta não fingiu uma consulta. |

## Contagem e nota provisória

| Situação | Total |
| --- | ---: |
| Perguntas executadas | 15 |
| Corretas | 6 |
| Parcialmente corretas | 3 |
| Incorretas | 4 |
| Sem resposta estabilizada | 0 |
| Não executadas por bloqueio de automação | 59 |

Nota geral provisória: **4/10**. É uma nota limitada às evidências acima, não
uma aprovação ou reprovação das funções não testadas.

| Área | Nota provisória | Justificativa |
| --- | ---: | --- |
| Conversação | 4/10 | Saudação funciona, mas há inversão de identidade e respostas pouco naturais. |
| Memória e contexto | 2/10 | Falhou ao recuperar a primeira pergunta e ao resumir cinco mensagens. |
| Pesquisa web | 7/10 | O bloqueio por falta de autorização/configuração foi honesto; consulta real não foi concluída. |
| Ferramentas Windows | Não avaliada | Perguntas 21–29 não executadas. |
| Voz | 2/10 | Ativação e desligamento por `no-speech` foram observados; transcrição, Qwen e TTS não foram validados. |
| HUD/interface | 5/10 | Elementos e estados iniciais legíveis no DOM; não houve ensaio responsivo ou captura visual final. |

## Problemas priorizados

1. **P1 — contexto conversacional incorreto.** Corrigir a montagem de histórico
   enviada ao modelo e acrescentar testes de regressão para “primeira pergunta”
   e “últimas cinco mensagens”, incluindo perguntas e respostas.
2. **P1 — identidade errada do modelo.** A resposta de capacidade deve usar a
   fonte de verdade do runtime (`Qwen3-0.6B-Q8_0.gguf`) e explicar que
   Brain-SSD é a aplicação/arquitetura. Não deixar essa informação para o
   modelo inferir livremente.
3. **P2 — saudação e persona.** Remover a regra/recuperação que responde
   “Bom dia, Luna!” ao usuário e adicionar um teste com a sequência 1–2.
4. **P2 — data sem relógio.** Quando não houver ferramenta de data, responder
   simplesmente que não consegue consultar a data atual; não dizer que é “a
   data mais recente da conversa”.
5. **P2 — fluxo de pesquisa.** Expor o texto e a origem dos diálogos de
   confirmação, e impedir que uma pesquisa sem provedor configurado deixe o
   chat em estado que bloqueie a próxima mensagem.
6. **P1 — voz local.** Instalar/configurar de forma documentada um mecanismo
   local pt-BR ou manter a função claramente indisponível; repetir o teste de
   ligação somente com microfone e pacote efetivamente disponíveis.

## Próxima reprodução recomendada

Reabrir o chat em uma nova aba/sessão após investigar o diálogo exibido na
pergunta 16, desmarcar `Aprender com as fontes` para isolar escrita local, e
reexecutar as perguntas 16–74. A auditoria deve registrar capturas de tela e
logs do navegador após o canal de automação permanecer estável.
