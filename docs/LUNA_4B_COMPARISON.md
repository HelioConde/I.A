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
