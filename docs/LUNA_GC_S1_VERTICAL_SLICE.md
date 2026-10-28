# Luna — meta de qualidade: combate de plataforma no estilo GC Season 1

## Objetivo do usuário

A Luna deve construir um **jogo autoral com a sensação de jogabilidade e profundidade de Grand Chase Season 1**, e não um site com três retângulos que "passa nos testes". O resultado permanece com personagens, animações, cenários, nomes, música e arte **originais**. Não copiar arquivos, personagens, ilustrações ou áudio protegidos de GC.

A página atual `/I.A/luna-created/` fica publicada como *v0.1 de referência* até que as novas mecânicas sejam escritas pela **Luna real (GGUF)**, revisadas e aprovadas. Nenhuma alteração de combate feita pelo ChatGPT pode ser creditada à Luna.

## Auditoria real de `site/luna-created/game.js` (28/10/2026)

| Área | v0.1 | Alvo inicial |
|---|---|---|
| Movimento | seta muda `vx` para ±5; soltura interrompe imediatamente | corrida, **dash com duplo toque**, direção, aceleração e animações |
| Plataformas | um único chão fixo em y=440 | plataformas com aterrissagem por cima, atravessar para baixo, queda e recuperação |
| Combate | Z escolhe primeiro inimigo vivo; dano repetido por frame enquanto ataque ativo | **combo de três golpes reais**, cooldown, janela de input, hitbox na direção, hitstun e knockback |
| Recursos | vida numérica; sem MP | **barra de MP**, carregar habilidade segurando Z e especiais por nível |
| Inimigos | um inimigo por onda, vermelho e sempre avança em direção ao jogador | IA com perseguição, antecipação, recuperação, diferenças por tipo, miniboss |
| Chefe | apenas HP maior e uma forma decorativa que aparece em wave=2 | boss de tamanho real, telegráficos, fases, padrões evitáveis, recompensa |
| Visual | retângulos sem animação | sprites autorais com idle/walk/run/jump/fall/attack/hit, parallax, efeitos e HUD |
| Fases | 3 ondas na mesma arena | 3 mapas/biomas com plataformas, câmera, progresso, sala de chefe |
| QA | seis verificações de fluxo | métricas de dash/combos/MP/hitbox, QA visual comparativo, vitória sem pular etapas |

Referências mecânicas: controles e MP https://grandchase.fandom.com/wiki/Game_Controls ; comandos e dash https://grandchasecreator.conradosaud.com.br/mecanicas ; combo e especiais https://grandchase.fandom.com/wiki/Knight_Skill_Tree ; visão geral https://steamcommunity.com/sharedfiles/filedetails/?id=2580603421

## Milestones incrementais, feitos pela IA

1. **S1.1 — controle e dash.** A própria Luna gera três trechos JS pequenos para o sistema de duplo toque (variáveis do dash, seta direita e esquerda). Proibido alterar código não relacionado. Repetir tecla pressionada não deve disparar dash. O navegador mede deslocamento em dash vs caminhada e reexecuta toda a suíte do jogo.
2. **S1.2 — combo e direção.** A Luna implementa três golpes com janelas distintas, hits uma única vez por golpe, direção da hitbox e feedback; teste demonstra que o terceiro golpe é diferente e que ataque fora de alcance não causa dano.
3. **S1.3 — MP e especiais.** Carregar barra segurando Z, habilidade 1/2/3 gasta MP, tempo de carregamento e feedback; testes para consumo, cooldown e situações sem MP.
4. **S1.4 — plataforma vertical.** Pelo menos três níveis de altura, colisão por cima, queda, dash aéreo e câmera; testes de pulo entre plataformas, não atravessar indevidamente e recuperação.
5. **S1.5 — inimigos e boss.** IA com sinais antecipados, padrões distintos, hitstun, penalidades de dano e boss original em várias fases; testes que provam o perigo e as aberturas para atacar.
6. **S1.6 — apresentação.** Produção de sprites, animações, efeitos, fundos e HUD com assets originais; aprovação humana baseada em capturas e comparações de referência, sem atribuir arte de outras fontes à Luna.
7. **S1.7 — missões, seleção de fases e progressão.** Mapa, objetivos, recompensas, desbloqueios e inventário local exportável; sem reivindicar conteúdo ou arte de GC.
8. **S1.8 — salas e cooperação/PvP.** Lobby, escolha de sala e partidas com estado sincronizado; GitHub Pages continua como frontend estático, mas partidas online **exigem um backend WebSocket**. Não simular multiplayer usando apenas localStorage.
9. **S1.9 — polimento e qualidade.** Sons originais, opções gráficas, configurações de teclado, 60 FPS quando possível, acessibilidade, controle mobile opcional e sessões longas de playtest humano.

## Resultado mínimo para usar a palavra "semelhante ao GC S1"

Dash, combo, habilidade de MP, múltiplas plataformas, pelo menos três inimigos diferentes, chefe com padrão e animações de todos os estados **devem funcionar ao jogar**, não apenas existir como textos no código. Rodar no desktop, com teclado personalizável e taxa de quadros estável. A qualidade visual exige revisão humana, separada da automação.

## Estado honesto dos modelos

No trial comparativo `40653494692`, Ornith 1.5 9B e Qwen3-4B **ambos falharam** em gerar um jogo JS inteiro válido (2 tentativas por modelo); os testes do navegador foram ignorados. Um run "success" do GitHub Actions **não significa modelo aprovado**. A estratégia viável já comprovada na Luna é **patch pequeno por inferência**, acompanhado de compilação, Playwright e feedback de erro. O novo estágio S1.1 segue esse método. Conservamos a versão v0.1 até ser superada.

## Autoria auditável

Cada modelo GGUF e arquivo original possui hash; texto exato dos patches é arquivado. A execução e validação são conduzidas pelo ChatGPT, mas os trechos JS creditados à Luna devem vir de inferência real do modelo. Não usar substituições feitas pelo assistente para "passar" no teste; se o modelo falhar, resultado INCOMPLETE. Os patches aceitos serão integrados somente após inspeção do Chromium e revisão do PR.
