# Luna — IA especializada em desenvolvimento de jogos

**Direção de produto definida em 2026-10-28.**

## Identidade e missão

- **Luna**: assistente local de desenvolvimento de jogos construída sobre as partes utilizáveis do Brain-SSD.
- **Luna Code Studio**: ferramenta que estrutura propostas multi-arquivo, planejamento por motor e revisão antes de aplicar modificações.
- **Luna Arcade S1**: o jogo-laboratório original de ação/plataforma, inspirado em princípios de jogabilidade de Grand Chase Season 1, usado como benchmark de engenharia, **não o nome da IA**.

**Visão:** transformar uma ideia em um projeto de jogo **editável, testável e jogável**, com arquivos acessíveis ao criador. Isso exige integração com motores, arte coerente, código, cenas, playtests e correções iterativas, em vez de simplesmente devolver snippets em um chat.

A trilha de pesquisa de eficiência Brain-SSD (Fases 4D/4E etc.) permanece separada e congelada conforme sua política científica. A Luna GameDev é uma **aplicação/produto** de pesquisa, não uma reivindicação de que um SSD substitui a RAM ou de que houve melhoria de pesos do Qwen.

## Diferencial pretendido

Já existem ofertas especializadas: [Unity AI](https://unity.com/features/ai), [Rosebud AI](https://www.play.rosebud.ai/tutorial) e [Ziva para Godot](https://ziva.sh/docs/). Não afirmar que não existem IAs para desenvolvimento de jogos.

O diferencial a **testar**, e não anunciar como concluído, será: execução local sempre que possível; propriedade dos arquivos e exportação; suporte a motores; memória de projeto; inspeção de cena e código; QA automatizado com evidência; rollback e aprovação humana; preferência por jogos funcionais em lugar de demos falsas.

## Ordem de construção

| Marco | Capacidade | Evidência obrigatória |
|---|---|---|
| G0 — Preparação | Perfis de motor Web 2D e Godot 4; plano de jogo e contrato de arquivos | Testes unitários, JSON válido, revisão estática |
| G1 — Vertical slice | Gerar movimento e colisão realmente jogáveis no Web 2D | Playwright: teclado, estado real, gravidade e colisão |
| G2 — Mecânicas | Ataque, hitboxes, inimigos, vida e reações | Testes de estado + observação da simulação |
| G3 — Jogo completo | Menu, três classes, fases, chefe, derrota e vitória | Playwright de ponta a ponta + revisão visual |
| G4 — Godot 4 | Ler projeto, gerar cenas e scripts com alterações revisáveis | Importação headless com Godot e playtest real |
| G5 — Agente iterativo | Observar erros, propor patch, testar novamente, solicitar aprovação | Logs, diff, testes repetidos, rollback |
| G6 — Design e assets | Sprites, animações, interface e identidade coerentes com o jogo | QA visual consistente e revisão humana |
| G7 — Comparação de modelos | Testar Qwen 0.6B e opções maiores aptas a código | Mesma tarefa, mesmo motor, taxa de sucesso, RAM e latência |

O marco G0 significa somente **ferramentas de preparação**, não gameplay gerado. Não confundir os estágios internos S0–S7 do Arcade com os marcos G0–G7 da IA.

## Motores suportados / planejados

**Web 2D (`web2d`):** primeiro alvo, HTML5 Canvas/JavaScript, offline sem backend, QA via Playwright e possível publicação no GitHub Pages. Status: perfil de prompts e testes de aceitação definidos; integração autônoma ainda pendente.

**Godot 4 (`godot4`):** GDScript 2.0, cenas `.tscn`, recursos `.tres`, `project.godot`, inspeção/importação com Godot instalado; nenhum editor conectado automaticamente neste marco. Status: perfil e revisão estática parcial definidos; execução e automação ainda pendentes.

**Roblox/Unreal/outros:** candidatos futuros. Não declarar suporte sem adaptador real, ambiente de testes e critérios de aceite.

## Como a Luna deverá trabalhar

1. **Game designer:** interpreta a ideia, gêneros, regras, câmera, classes e gameplay loop.
2. **Arquiteto:** define motor, cenas, estado, inputs, recursos e dependências.
3. **Programador:** entrega pequenos conjuntos de arquivos versionados, com explicação do impacto.
4. **Playtester:** roda o jogo real em sandbox autorizada e registra resultados reproduzíveis.
5. **Revisor visual:** compara arte, movimento, animações, UI, contraste e acessibilidade por screenshots.
6. **Depurador:** usa falhas reais para corrigir o código e repetir os testes.
7. **Publicador:** só exporta depois de aprovação explícita e com build testado.

Esses são **papéis desejados**. Hoje o Code Studio implementa parcialmente os passos de planejamento, propostas e revisão; **não** implementa automaticamente o playtester, depurador ou publicador.

## Critério de sucesso do primeiro grande desafio

O [Luna Arcade S1](../benchmarks/arcade_s1/brief.json) deve atingir **90/100 ou mais** e satisfazer todos os hard gates (menu até vitória, três classes reais, chefe, Playwright, avaliação visual e sem falhas bloqueantes). O jogo precisa usar arte e nomes originais; não copiar assets, marca, músicas, mapas ou código comercial.

O [Code Studio](LUNA_CODE_STUDIO.md) fornece propostas revisáveis, não uma execução automática. A nota inicial de 4/9 no [teste de inteligência real do Qwen 0.6B](INTELLIGENCE_BASELINE_2026-10-28.md) é o alerta de que ainda não se deve autorizar alterações autônomas de grandes projetos.

## Comandos disponíveis

No diretório do Brain-SSD:

~~~powershell
python tools/code_studio.py engines
python tools/code_studio.py plan --engine web2d
python tools/code_studio.py prompt --stage s1-movement --engine web2d
python tools/code_studio.py prompt --stage s0-plan --engine godot4
~~~

Estes comandos **não executam modelos** nem fazem alterações nos jogos. Eles permitem preparar um projeto bem especificado para um modelo de programação e para os testes posteriores.
