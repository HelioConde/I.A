# Comparação GameDev da Luna — Qwen3 0.6B contra 4B

## Por quê?

O primeiro teste real de geração multi-arquivos da Luna foi concluído com Qwen3-0.6B-Q8_0 no Windows GitHub Actions:

- [Run v2 / Qwen 0.6B](https://github.com/HelioConde/I.A/actions/runs/40627615482)
- Primeira tarefa: criar `index.html` com um menu de jogo acessível.
- Duas tentativas reais, ambas insuficientes: ausência de `lang=` e `viewport`. A etapa seguinte `styles.css` não foi iniciada.
- **0/2 arquivos aprovados**; nenhum código foi executado, nenhum jogo foi produzido pelo modelo.

O próximo passo é rodar **exatamente o mesmo protocolo** com o modelo oficial maior Qwen3-4B Q4_K_M, registrando custo e falhas. Isso mede avanço de qualidade e não declara equivalência com agentes de programação de ponta.

## Modelo e integridade

- Fonte oficial: [Qwen/Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF).
- Quantização: `Qwen3-4B-Q4_K_M.gguf`.
- Tamanho esperado: **2.497.280.256 bytes**.
- Revisão congelada: `bc640142c66e1fdd12af0bd68f40445458f3869b`.
- SHA-256 esperado: `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.

Os metadados do arquivo foram conferidos em [ossmodeldb](https://www.ossmodeldb.com/models/qwen3-4b/q4-k-m) e [arquivo de modelos revisados em 27/10/2026](https://sanjaaygowdats.ai/models). O instalador baixa **somente mediante `--confirm-download`**, confirma revisão, tamanho, SHA e assinatura GGUF antes de disponibilizar o arquivo; hash divergente causa falha, sem substituir arquivo preexistente.

## Comandos no Windows

Baixar somente o modelo 4B após aprovação explícita de download:

~~~powershell
python tools/install_game_coder_model.py --confirm-download
~~~

Executar a comparação com o mesmo Game Agent v2 do teste 0.6B:

~~~powershell
python tools/run_game_agent_v2_windows.py --stage s0-plan --model-file Qwen3-4B-Q4_K_M.gguf --profile equilibrado --attempts 2 --report results/game_agent/qwen3-4b.json
~~~

Também existe um workflow opt-in [Qwen3 4B Comparison](../.github/workflows/qwen4b-game-agent.yml) no GitHub Actions. Nele o modelo é baixado num runner temporário Windows, testado e descartado; nenhum GGUF do computador pessoal é enviado ao GitHub. A saída do Qwen não é executada e apenas metadados sanitizados são publicados. A pontuação permanece "INCOMPLETE" se faltar qualquer arquivo ou requisito.

## Limitações de interpretação

O 4B pode caber na RAM com 16GB totais, mas **o consumo físico, latência e temperatura do Windows pessoal não foram medidos pelo runner**. O teste atual cobre HTML/CSS estático, não um jogo completo. Mesmo um resultado verde não comprova autonomia até o jogo final; a próxima etapa requer teste visual e funcional de código produzido pelo próprio modelo em sandbox e posterior revisão humana.

## Resultado real Qwen3-4B — 2026-10-28

**[GitHub Actions run 40627940558](https://github.com/HelioConde/I.A/actions/runs/40627940558): 2/2 arquivos aceitos pelo validador estático.** Os jobs de integridade e de inferência nativa foram concluídos; o modelo carregado foi exatamente `Qwen3-4B-Q4_K_M.gguf`.

- Arquivo `index.html`: primeira saída foi rejeitada (`invalid_complete_json_or_file`); a **segunda tentativa corrigida** passou (`static_candidate_ready`).
- Arquivo `styles.css`: passou na primeira tentativa (`static_candidate_ready`).
- **Três gerações reais**, para dois arquivos aceitos; ambos os arquivos foram avaliados na mesma rubrica de `s0-plan` usada com o 0.6B.
- **Comparativo:** 0.6B = 0/2 arquivos aceitos; 4B = 2/2 arquivos aceitos **nesta execução**.
- O modelo **não executou o código**; `code_executed=false`, `gameplay_verified=false`, `workspace_modified=false`, `draft_saved=false`. Isso prova capacidade de proposta multiarquivo sob critérios estáticos, **não um jogo funcional feito pela IA**.
- O artifact `luna-game-coder-4b-40627940558` fornece métricas sanitizadas. O teste é uma amostra pequena e não comprova superioridade geral do 4B sem repetições e holdouts.

**Próximo marco:** executar candidatas geradas pelo 4B em sandbox isolada com testes reais de navegador; manter aprovação explícita antes de modificar projetos.

## Etapa seguinte: física e movimentação em JavaScript (S1)

O workflow do Qwen3-4B agora permite selecionar `stage=s1-movement` manualmente ou disparar uma branch `lab/luna-game-4b-movement-*`. Esse teste pede à Luna um arquivo `src/game.js` com canvas, estado do jogador, gravidade e teclado. A saída aceita pode ser arquivada como **rascunho sintético gerado pelo modelo**, mas jamais é aplicada ou executada automaticamente. O status de aceitação continua a medir apenas contrato JSON, palavras-chave, análise estática e `node --check`, **não movimento real**. Um teste posterior em navegador isolado será necessário para comprovar comportamento.

A opção `s0-plan` original continua funcionando, com os mesmos critérios e nome de relatório. Em CI, `--save-draft` faz gravação controlada somente em `results/game_agent/draft-<stage>.json`, que é parte do artifact de avaliação e não substitui arquivos do projeto.

## Resultado real da etapa S1 — movimento em JavaScript (2026-10-28)

[Run 40628359254](https://github.com/HelioConde/I.A/actions/runs/40628359254) com o Qwen3-4B oficial: **INCOMPLETE, 0/1 arquivo aceito**. O modelo realizou duas gerações reais para `src/game.js`: primeira saída rejeitada por `invalid_complete_json_or_file` e segunda por `javascript_syntax_error`. **Nenhum arquivo foi aceito, salvo como draft, executado ou aplicado ao jogo**. O workflow concluiu com sucesso como execução de diagnóstico, não como sucesso de programação.

**Conclusão técnica:** o 4B conseguiu duas propostas iniciais de HTML/CSS em S0, mas não superou a tarefa mais complexa S1 de JavaScript/física sob o protocolo JSON v2. A próxima avaliação deve separar claramente erros de codificação JSON aninhada, sintaxe JavaScript e semântica de gameplay; usar formato de código mais apropriado pode ajudar, mas qualquer mudança de protocolo será um benchmark novo (v3), sem alterar retroativamente esta falha.
