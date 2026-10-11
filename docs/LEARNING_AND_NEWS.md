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
