# Luna Game Agent v2 — geração nativa por arquivos, com revisão

## Escopo do marco

A Luna já possui jogo de referência jogável (criado pelo assistente): [Luna Arcade S1](../site/arcade/). O agente v2 cria uma **via separada** para medir se o próprio Qwen local consegue escrever pequenos arquivos relacionados a jogos.

O teste anterior v1 gerou 2/2 propostas JavaScript com estrutura e sintaxe válidas, mas nenhuma foi aprovada pela política original de completude. Por isso o v2 **não altera retrospectivamente a nota do v1**; é outro protocolo, com saída maior e uma tarefa nova de dois arquivos.

**Esta versão não demonstra um jogo produzido autonomamente**, nem correção visual/funcional. É uma etapa rumo a isso.

## O que já existe

- `src/brain_ssd/chat/game_agent_v2.py`: divisão da tarefa por arquivo, prompt especializado, contrato JSON, validação estática, feedback limitado e relatório; admite duas etapas piloto: `s0-plan` (HTML + CSS) e `s1-movement` (JS Canvas básico).
- `tools/run_game_agent_v2_windows.py`: usa **o núcleo CPU do llama.cpp diretamente** com Qwen GGUF real, em vez de cortar toda resposta em 256 tokens por pergunta do chat. Usa budget limitado por arquivo e só considera verdadeiro quando houve retorno do backend.
- A saída do modelo passa por `parse_proposal`, `review_proposal` e (para JS) `node --check`; isso **não executa código gerado**.
- Nenhuma alteração é aplicada ao jogo real; opcionalmente `--save-draft` salva um único JSON de rascunho **somente** em `results/game_agent`, depois de aprovação da rubrica estática, sem sobrescrever rascunhos existentes. Para aplicar ao workspace o usuário deve usar o Code Studio com `--approve`.
- `tests/test_game_agent_v2.py` protege contra respostas simuladas, schema inválido, caminhos errados, conteúdo proibido e falsas alegações de execução.
- Workflow [Game Agent v2](../.github/workflows/game-agent-v2.yml) é executável manualmente e por gatilho opt-in no GitHub Actions; publica apenas métricas sanitizadas, **não** código produzido pela IA.

## Executar no Windows real

Na pasta Brain-SSD, com modelo e llama.cpp instalados:

~~~powershell
python tools/run_game_agent_v2_windows.py --stage s0-plan --profile equilibrado
~~~

Para testar a criação de um pequeno código JavaScript Canvas:

~~~powershell
python tools/run_game_agent_v2_windows.py --stage s1-movement --profile equilibrado
~~~

Para usar o modelo 4B já instalado na pasta models, se disponível:

~~~powershell
python tools/run_game_agent_v2_windows.py --stage s0-plan --profile equilibrado --model-file Qwen3-4B-Q4_K_M.gguf
~~~

Para optar por salvar um rascunho válido (não o aplica em um jogo):

~~~powershell
python tools/run_game_agent_v2_windows.py --stage s0-plan --save-draft
python tools/code_studio.py review results/game_agent/draft-s0-plan.json
~~~

O teste grava relatório em `results/game_agent/v2-latest.json`. O relatório não contém conteúdo do código, somente nomes, status, tentativas e diagnósticos.

**Limites atuais:** o backend nativo ainda usa CLI por solicitação no perfil Equilibrado; carregar o modelo várias vezes custa CPU e tempo. O resultado não prova originalidade plena, segurança de execução, jogabilidade ou ganho de RAM por SSD. A rubrica estática não é substituto de Playwright.

## Primeira medição real v2 (2026-10-28)

- [Execução Qwen 0.6B no Windows](https://github.com/HelioConde/I.A/actions/runs/40627615482) — jobs de infraestrutura e contrato concluídos com sucesso.
- **Resultado do modelo: INCOMPLETE**. Duas tentativas reais de gerar `index.html`; as duas produziram propostas que falharam nos requisitos de `viewport` e `lang=`.
- Sem um `index.html` aprovado, a ferramenta deliberadamente não avançou para o segundo arquivo `styles.css`; nenhum arquivo foi escrito no jogo nem executado.
- Esta é uma **linha de base negativa válida**. O fato de o workflow ter status verde comprova execução/relatório, não competência de programação da Luna.
- O artifact `luna-game-agent-v2-40627615482` contém métricas sanitizadas.

A próxima comparação deve usar um modelo maior já existente localmente, com o mesmo protocolo e sem reajustar o teste depois de conhecer os resultados.

## Próxima evolução para atingir a meta

1. Gerar o projeto de jogo com contexto dos arquivos aceitos e contratos de módulo, não só HTML/CSS.
2. Salvar rascunhos sob versionamento em um workspace separado, sob autorização explícita.
3. Testar em sandbox sem rede, com Playwright/Game QA e relatórios factuais.
4. Receber falhas reais, pedir patches, repetir os testes e comparar melhoria contra baseline.
5. Validar mais de um modelo e diferentes projetos não vistos antes, evitando ajustar rubricas ao resultado.
6. Só declarar a meta cumprida quando **a Luna** gerar, corrigir e concluir um jogo jogável em tarefa nova, do prompt ao build final e aprovação humana.
