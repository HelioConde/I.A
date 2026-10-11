# Poke Idle Lab (Brain-SSD) — protótipo 1

Experimento independente que compara **Poke Idle World** e **Poke Idle IO** com testes locais e sem credenciais. Este código é original; não incorporamos código de terceiros sem revisão da licença. A ferramenta **ainda não joga** nos servidores, não realizou login e não comprovou nenhum saque.

## Regras conferidas em 11/10/2026

- IO: automação expressamente permitida pelos termos, inclusive mercado. Exploração, manipulação artificial de valor e transações fora do mercado são proibidas. Fonte: https://pokeidle.io/terms
- World: scripts, extensões e automações externas sem autorização da equipe são proibidos, assim como negociar com contas identificadas como bots. Fonte: https://poke.idleworld.online/rules
- Os números de resgate em USDT anunciados pelo IO não comprovam pagamentos efetivos. No World não existe uma cotação de saque oficial verificada no laboratório.

## Referências abertas analisadas

1. Poke Idle Companion: https://github.com/allmight-ai/poke-idle-companion — analytics XP/s, overkill, breeding e recomendação de hunts; licença MIT para código autoral, não para dados protegidos de criaturas. Autor declara autorização da equipe; não automatiza ações.
2. GameAgent AI: https://github.com/vineethsaivs/gameagent-ai — arquitetura observar, decidir, agir, aprender com Playwright e SQLite; licença MIT; modelo de visão GPT-4o requer chave e gera custos.
3. Idle Helper: https://github.com/undreiss/Idle-Helper — referência de fluxos. Licença personalizada restringe redistribuição de modificações e comercialização. NÃO copiamos seu código.

## Executar no Windows

Entre na pasta experiments/poke_idle_lab e execute os testes locais, sem instalar bibliotecas:

    py -3 -m unittest -v test_lab.py
    py -3 lab.py exemplo_sintetico.csv
    py -3 decision.py hunts_sinteticas.csv

Os dois CSVs de exemplo contêm valores **inteiramente fictícios**. Só troque por valores reais medidos quando tiver sessões registradas. Uma venda não realizada não é uma venda; gemas não são USDT sacados. O campo withdrawn_usd só registra dinheiro efetivamente recebido, e gems_received_net já precisa estar descontado de comissões.

Para observação passiva no PC (opcional):

    py -3 -m pip install -r requirements-browser.txt
    py -3 -m playwright install chromium
    py -3 browser_probe.py --game world --seconds 30
    py -3 browser_probe.py --game io --seconds 60

No World, o observador captura **somente a página pública**, sem login. No IO, o navegador abre com perfil local e eventual login é manual. Não há cliques automáticos, leitura de cookies, compras, vendas ou saques. Nunca suba as capturas ou perfil do navegador ao GitHub.

## Testar as tecnologias de terceiros separadamente

Para testar o núcleo matemático do Companion, faça clone do projeto **original**, vá até extension/tests e execute node teste.js e node breeding-teste.js. Isso não entra no World.

Para o GameAgent, clone o original e rode sua suíte de testes com Python e as dependências indicadas no README. Faça uma sessão no **2048** antes de tentar conectar o IO. Uma sessão com GPT-4o requer chave válida e pode ter custo.

## Próxima etapa

1. Coletar dados de 1h, 6h e 24h com a mesma metodologia.
2. Pedir autorização à staff do World antes de qualquer automação ou uso de extensão não autorizada.
3. Revisar o código da extensão oficial para IO anunciada no Discord e implementar um adaptador com ações limitadas, logs e botão de parar; sem automatizar pagamentos/saques.
4. Comparar dados observados, vendas concluídas, custos e saques recebidos; nunca tratar ganho fictício como renda comprovada.
