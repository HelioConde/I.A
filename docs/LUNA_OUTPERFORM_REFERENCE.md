# Luna deve superar o Luna Arcade S1 — contrato de evolução

## Autorização e separação de autoria

O **Luna Arcade S1 publicado** é o jogo de referência implementado pelo assistente. O usuário autorizou que a Luna use seu **código, controles, HUD e testes** como ponto de partida. Mas a Luna só pode receber crédito por alterações **geradas pela inferência real de seu modelo**, armazenadas com registro de execução, hash, revisão e testes.

**Não basta criar uma cópia idêntica, trocar cores, renomear classes ou aumentar a pontuação do benchmark.** A meta é um jogo melhor do que essa referência em jogabilidade, qualidade, design e experiência do jogador.

## Critério de "melhor que a referência"

A referência original conta com **11 testes Chromium Playwright** aprovados, três classes que chegam até a vitória, controle touch, três regiões e um chefe. O próximo release Luna só recebe o selo **MELHOR QUE A REFERÊNCIA** se satisfizer simultaneamente:

- **Sem regressões:** os 11 testes originais e seus novos testes de segurança continuam passando em desktop e mobile.
- **Ganho real mensurável:** pelo menos três melhorias de jogabilidade distintas não existentes na referência, com seus próprios testes antes/depois (ex.: resposta e cancelamento do salto, combo real com janela de input, comportamento de inimigos).
- **Conteúdo superior:** ao menos uma fase ou encontro original adicional testável, com propósito de gameplay, sem copiar recursos comerciais.
- **Qualidade visual melhor:** revisão humana comparando capturas de vários estados nas mesmas resoluções (390×844, 768×1024, 1366×768, 1600×900), arte e animações coerentes, legibilidade dos personagens e usabilidade.
- **Confiabilidade:** sem exceções de navegador durante sessões de teclado e toque, aprovação do usuário no playtest e sem defeitos bloqueantes conhecidos.
- **Autoria comprovada:** cada melhoria atribuída à Luna tem o texto gerado pelo Qwen e sua sessão de avaliação armazenados como artefato auditável e passa por revisão humana antes de entrar em `main`.

Somente cumprir os testes automáticos **não** equivale a qualidade visual superior. A aprovação de quem joga é condição necessária, mas não substitui os testes.

## Primeiro defeito real detectado

No jogo de referência, o handler de soltura do controle mobile contém `touchDown=false`, apesar de não haver essa variável declarada no módulo. Em strict mode, o evento `pointerup` gera `ReferenceError`. A suíte original 11/11 não capturava esse erro (testava movimento/ataque sem inspecionar exceções do evento específico).

Foi adicionado o teste regressivo `outperform baseline: releasing mobile controls has no uncaught ReferenceError`. **Antes de corrigir o jogo, esse novo teste deve falhar**, demonstrando que a avaliação é capaz de distinguir uma versão pior de uma melhor.

## Processo do primeiro avanço atribuído à Luna

1. A ferramenta `tools/run_game_outperform_windows.py` fornece o trecho real com falha ao Qwen3-4B GGUF local. Nenhuma solução pronta é retornada pelo código de teste.
2. O Qwen deve propor **uma linha JavaScript** substituta. A geração real é obrigatória; simulações não contam.
3. O pipeline verifica o contrato estrito do patch e a sintaxe com `node --check`, **sem executar código gerado**.
4. Depois de inspecionar o texto real da IA, um revisor autoriza a aplicação da única linha no branch do jogo; nunca em arquivo privado ou na pesquisa congelada.
5. O Chromium testa o controle mobile real, confirmando ausência do ReferenceError, e reexecuta os testes originais.
6. Relatório identifica claramente **“patch proposto por Qwen”** e **“integração, testes e revisão conduzidos pelo ChatGPT”**. Esse primeiro bugfix demonstra colaboração verificável, **não autonomia completa**.

## Primeiro patch realmente produzido pela Luna — Qwen3-4B

- **Baseline do ChatGPT:** [run Chromium 40632444557](https://github.com/HelioConde/I.A/actions/runs/40632444557): **11 testes passaram e o 12º falhou**. Erro reproduzido em duas tentativas: `touchDown is not defined` no `pointerup` mobile.
- **Primeiro teste da IA:** [run 40632459539](https://github.com/HelioConde/I.A/actions/runs/40632459539): duas propostas reais rejeitadas por ainda mencionar a variável sem declaração. Resultado INCOMPLETE, preservado.
- **Segunda instrução, nova avaliação v1.1:** [run Qwen3-4B 40632642743](https://github.com/HelioConde/I.A/actions/runs/40632642743): **uma geração real aprovada na revisão de sintaxe/contrato**, sem executar código. O texto do modelo foi exatamente `const end=e=>{e.preventDefault();keys.delete(code)};`.
- **Aplicação:** ChatGPT revisou a linha gerada, substituiu apenas o handler do evento e acrescentou regressão unitária exigindo coincidência exata com a linha proposta. O conteúdo dessa linha é atribuído ao **Qwen3-4B da Luna**; toda integração, testes e infraestrutura são do ChatGPT.
- **Resultado do navegador após patch:** consultar o último workflow `Luna Arcade S1 — Playable Game QA` deste PR. Não declarar correção comprovada até que os 12 testes passem.

Esse patch é apenas **um avanço pequeno demonstrável**, não o cumprimento da meta de ser melhor que o jogo de referência em todas as dimensões. Ainda faltam as melhorias de jogabilidade, novas fases, qualidade visual comparativa e autoria contínua do modelo.

## Próximos desafios, sempre com teste antes/depois

- F1: melhorar movimentação com entrada de salto antecipada e tolerância de pulo depois de sair da plataforma. A Luna precisa alterar a física, com testes reproduzíveis dos tempos.
- F2: criar inimigos que reconheçam distância/ataques e possam ser esquivados, com testes que excluam ataques instantâneos falsos.
- F3: produzir uma nova arena original e finalizar com transição para o chefe, preservando os três arquétipos.
- F4: melhorar seleção de personagem, animações e leitura visual, com captura Playwright e aprovação humana.
- F5: criar versões próprias exportáveis e reproduzíveis para Web 2D e, depois, Godot 4.

**Critério de falha:** código inválido, falso relato de sucesso, conteúdo copiado, resultado não reproduzível ou regressão. A melhoria volta ao agente para reparo; não é publicada silenciosamente.

## Como jogar e avaliar

[**Luna Arcade S1 no GitHub Pages**](https://helioconde.github.io/I.A/arcade/) possui um formulário `Avaliar o jogo`. O jogador descreve o que acertou, errou e o comportamento esperado; o relato pode ser copiado ao ChatGPT ou enviado como issue. Esse feedback define prioridades reais de melhoria.

**Observação:** a classificação de autoria acima refere-se exclusivamente ao código gerado pelo modelo e verificado. O benchmark e a infraestrutura de testes são construídos pelo assistente.
