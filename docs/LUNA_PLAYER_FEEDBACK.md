# Como avaliar o Luna Arcade S1 — teste com jogadores

O jogo está publicado em [**Luna Arcade S1 no GitHub Pages**](https://helioconde.github.io/I.A/arcade/). Não precisa instalar nada nem entrar no GitHub para jogar.

## Como participar

1. Abra o jogo, escolha entre **Kael (espadachim)**, **Lyra (arqueira)** e **Orin (mago)** e use os controles informados abaixo da tela.
2. Teste o que conseguir: pulo, movimento, ataque Z, especial X, investida Shift, pausa, mudança de região e chefe.
3. Na mesma página, clique em **Avaliar o jogo** no menu superior. Preencha **O que o jogo acertou?**, **O que está errado ou precisa melhorar?** e, se possível, **Como deveria funcionar?**.
4. Se o erro ainda estiver acontecendo numa partida, clique em **Capturar estado da partida** para anexar dados do próprio motor (modo, região, classe, posição, HP, inimigos restantes e pontuação). Não coleta nome, conta, IP nem histórico.
5. Escolha uma forma de compartilhar: **Copiar para enviar no ChatGPT** e colar nesta conversa; **Abrir issue no GitHub** com título e corpo preenchidos (exige sua conta GitHub); ou **Salvar relatório TXT** para anexar aqui.
6. Para demonstrar um defeito visual, use **Salvar cena PNG** (exporta apenas o Canvas, sem menus) ou faça um print do navegador pelo sistema e envie neste chat.

**Privacidade e honestidade:** este formulário roda 100% no navegador; não salva relatos em servidor ou banco de dados, não cria issues automaticamente e não envia informações ao ChatGPT por conta própria. O link do GitHub abre uma nova página onde o usuário escolhe se deseja publicar. Dados da partida só entram no relato depois do botão de captura ser acionado. O relatório só inclui os campos escritos pelo jogador e os dados explicitamente capturados.

## Como organizar o retorno

Ao analisar feedback recebido, priorizar:

- **P0**: travamento, erro que impossibilita jogar ou perda de progresso;
- **P1**: controles, colisão, combate, inteligência de inimigos ou derrota/vitória com comportamento incorreto;
- **P2**: clareza, equilíbrio de classes, visual, efeitos e responsividade;
- **P3**: novos personagens, fases, modos, estética e ideias futuras.

Corrigir um problema de cada vez com teste reproduzível e demonstrar o resultado em uma revisão da página. O GameDev Agent Qwen não recebe automaticamente issues do GitHub; todo feedback precisa ser analisado e transformado em tarefa por um agente autorizado.

## Distinguir os dois tipos de teste

O **jogo de referência** foi implementado pelo assistente e passou 8 testes Playwright (três classes chegando ao final e controle touch funcionando). O **objetivo da Luna** continua ser criar jogos por conta própria. Feedback humano valida o jogo de referência, mas **não** é prova de que o modelo Qwen gerou o código. As duas trilhas de evidência devem permanecer separadas.

## Limitações

- Abrir issue com texto preenchido depende de login GitHub e do tamanho aceito pela URL.
- Captura de PNG usa o Canvas e não inclui menus HTML.
- Sem serviço externo, a página não pode publicar relatos diretamente nesta conversa nem recebê-los automaticamente.
- A classificação de prioridade é triagem, não substitui o relato do jogador nem testes de reprodução.
