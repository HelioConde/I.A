# Aprendizado por correções e notícias atuais — Brain-SSD

O Brain-SSD agora separa dois recursos:

1. **Exemplos ensinados por você**, armazenados no SQLite local e usados em conversas futuras.
2. **Pesquisa de atualidades**, com notícias datadas e links, somente quando você autorizar enviar aquela pergunta à internet.

**Não é treinamento dos pesos do Qwen.** O modelo continua usando o GGUF instalado. Os exemplos ensinados são memória de respostas revisável e apagável, não aprendizado autônomo sem supervisão.

## Ensinar uma saudação ou corrigir uma resposta

Inicie o Brain-SSD com memória habilitada, pelo **INICIAR-BRAIN-SSD.bat**.

Digite no chat:

    /ensinar Olá => Olá!

Depois envie apenas:

    Olá

A resposta será **Olá!**, recuperada de um exemplo persistido no SQLite. O aplicativo indica que ela não foi gerada pelo Qwen. O comportamento continua em novas conversas e após reiniciar o computador.

Para corrigir, use o mesmo comando com outra resposta:

    /ensinar Olá => Olá! Como vai você?

Para revisar ou desfazer:

    /aprendizados
    /desaprender Olá

Também é aceito:

    Quando eu disser "boa noite", responda "Boa noite!"

As conversas normais **não são aprendidas automaticamente**. Só as correções explícitas são guardadas. O limite é de 120 exemplos simples. A base fica em
`%LOCALAPPDATA%\BrainSSD\learned-responses.sqlite3` no Windows e não sobrescreve o histórico nem os dados do SSD.

## Perguntar sobre o Brasil agora

Por exemplo:

    Como está a situação do Brasil hoje?

Se a pesquisa estiver habilitada e a caixa **Pesquisar na web** estiver desmarcada, o navegador pede autorização para consultar fontes atualizadas **apenas para essa pergunta**.

No modo `auto` (disponível sem chave externa), o Brain-SSD tenta os feeds RSS oficiais da **Agência Brasil** para economia, política e últimas notícias. Só considera artigos datados dos sete dias anteriores e mostra os links e a data nas fontes. Perguntas que não tratam de atualidades continuam usando a pesquisa enciclopédica da Wikipédia.

O Qwen resume os trechos encontrados, mas **manchetes são uma amostra parcial do país** e não permitem concluir sozinhas se a situação geral está boa ou ruim. O feed não é substituto de indicadores consolidados ou comparação de veículos com perspectivas diferentes.

Se não receber notícias verificáveis (sem conexão, feed indisponível, informações antigas), o chat informa a falta de fontes **em vez de inventar dados atuais**. Sem autorização de pesquisa, nenhuma pergunta é enviada à rede.

## Como iniciar

Atualize o GitHub e abra `INICIAR-BRAIN-SSD.bat`. Escolha um modelo e responda **S** quando o menu perguntar se deseja habilitar a pesquisa opcional. O Qwen continua local. Cada envio que envolva web exige autorização da pergunta.

Também é possível executar no PowerShell:

    py -3 .\tools\run_chat.py --profile economia --episodic-memory --web-search --web-provider auto

Para instalar modelos e iniciar sem editar configuração:

    .\INICIAR-BRAIN-SSD.bat

## Validação offline

Os testes usam SQLite temporário e RSS simulado; não enviam perguntas reais para a internet:

    py -3 -m unittest discover -s tests -p "test_chat_learning_news.py" -v

A inferência real e a disponibilidade do feed precisam ser conferidas no seu computador. O Brain-SSD **não ficou mais inteligente apenas por memorizar uma saudação**: respostas abertas continuam dependendo da capacidade do Qwen e da qualidade das fontes.


## Estudar um assunto diretamente, sem depender do Qwen

O comando `/estudar [assunto]` pesquisa, verifica a relação temática dos
resultados e salva trechos públicos no SQLite **antes de qualquer tentativa de
geração**. É útil quando um modelo pequeno não consegue responder.

Exemplo:

```text
/estudar astronomia e estrelas
/conhecimento
Explique astronomia e estrelas
```

No primeiro envio, habilite **Pesquisar na web** e deixe marcado
**Aprender com as fontes**. Se uma das opções não estiver autorizada, o
comando não realiza acesso à internet nem altera o banco. A pesquisa é
pontual, não um agente em segundo plano. A primeira resposta informa
quantos resultados foram encontrados e armazenados; a pergunta seguinte
usa os trechos arquivados como contexto para o modelo local.

Para evitar falsas associações, o Brain-SSD só indexa termos presentes no
**título ou trecho da fonte**, e não palavras copiadas artificialmente da
pergunta. Fontes sem nenhuma correspondência com o assunto não são guardadas.
A recuperação reconhece alguns plurais simples, como `estrela` e
`estrelas`, mas não é uma busca semântica completa.

O comando `/conhecimento` mostra URL, tópico e data da consulta, incluindo
se cada fonte ainda pode ser reutilizada. Para apagar um tópico, use
`/esquecer-pesquisa [tópico exato]`.

**Importante:** os trechos vêm de provedores externos e ainda podem conter
erros, desinformação ou informações incompletas. Guardá-los significa
criar uma referência consultável, e não transformar seus conteúdos em
verdades permanentes ou alterar os pesos do Qwen.

## Aprendizado a partir de fontes públicas (pesquisa persistente)

Agora há uma segunda memória, separada dos exemplos ensinados manualmente:
`%LOCALAPPDATA%\BrainSSD\web-knowledge.sqlite3` (Windows).

O fluxo é:

1. Você escreve uma pergunta e marca **Pesquisar na web** (ou aceita a
   confirmação mostrada para notícias atuais do Brasil).
2. A opção **Aprender com as fontes** indica se você também quer conservar
   localmente os trechos públicos dessa pesquisa.
3. O aplicativo busca até quatro resultados e passa os trechos com URLs ao
   Qwen para gerar uma resposta na CPU.
4. Em uma pesquisa normal, após uma geração bem-sucedida, os **trechos realmente
   inseridos no contexto do modelo** podem ser salvos no SQLite. No comando
   `/estudar`, os resultados podem ser salvos sem depender de geração.
   A resposta gerada, o histórico privado e as notas pessoais não viram
   fontes do banco automaticamente.
5. Em perguntas semelhantes, o aplicativo busca os trechos por palavras
   relevantes e volta a enviá-los ao Qwen com fonte e data da pesquisa.
   Recuperar conhecimento antigo não requer nova consulta à internet.

**O que é aprendido:** títulos, URLs e trechos de fontes públicas. Isso
funciona como uma memória de pesquisa com recuperação lexical, e **não**
como reeducação dos pesos do GGUF nem prova de que todo conteúdo da fonte
seja verdadeiro. A IA não deve tratar trechos de páginas como comandos.

A retenção tem prazo de validade:

- Notícias atuais sobre o Brasil: até **12 horas** para reutilização como
  memória recente; depois é necessária outra pesquisa.
- Conteúdo geral: até **30 dias**, depois deixa de ser fornecido automaticamente.
- O banco conserva os registros até você apagá-los; expiração não apaga
  automaticamente os arquivos do usuário. O limite é de 800 registros.

Comandos de controle:

```text
/conhecimento
/esquecer-pesquisa Explique astronomia e estrelas
```

O primeiro mostra até oito fontes pesquisadas. O segundo apaga as fontes
associadas ao tópico exato informado.

**Limitações atuais:** o Brain-SSD arquiva principalmente **trechos de
resultados de pesquisa**, não lê e compreende livros ou sites inteiros.
A recuperação usa palavras compartilhadas; não é busca semântica vetorial.
A Wikipédia sem chave é útil para conhecimento enciclopédico, mas não
substitui pesquisa geral sobre toda a internet. Para sites diversos,
o provedor Brave Search exige chave própria e pode ter custos.
**Não existe aprendizado autônomo em segundo plano.** Cada consulta
externa exige autorização.

Os testes usam SQLite temporário e resultados simulados:

```powershell
py -3 -m unittest discover -s tests -p "test_web_knowledge.py" -v
```

Um teste `PASS` não comprova disponibilidade real dos provedores ou qualidade
das respostas no seu Windows; é preciso testar o Qwen instalado e os links.
