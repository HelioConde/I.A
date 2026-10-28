# Luna Action Lab — testes controlados no GitHub Actions

O [Luna Action Lab](../.github/workflows/action-lab.yml) disponibiliza três modos de validação para Brain-SSD. O sistema de testes fica no GitHub Actions e não depende de um serviço web ou de dados pessoais.

| Modo | Plataforma | Conteúdo | Modelo real |
|---|---|---|---|
| `smoke` | Linux | Chat, memória, segurança, armazenamento mmap, roteamento e streaming com fixtures sintéticas | Não |
| `extended` | Linux + Windows | Suítes adicionais de histórico, integridade, cache e recuperação, com compatibilidade Windows | Não |
| `real-qwen` | Windows | Instalação com SHA-256 verificado, diagnóstico e uma resposta real do Qwen CPU-only | Sim, Qwen3 0.6B |

**Não confundir:** testes sintéticos não demonstram economia física de RAM ou SSD-first. O teste `real-qwen` confirma uma única inferência real, não a qualidade geral nem a economia de memória.

## Executar

No GitHub: **Actions → Luna Action Lab — Regression and Real Qwen → Run workflow → escolher suite**. O botão de execução manual está disponível na branch padrão depois do merge da workflow.

Para executar localmente com Python 3.11 ou posterior (sem instalar o GGUF):

~~~powershell
python tools/action_lab.py --suite smoke --report results/action_lab/local.json
python tools/action_lab.py --suite extended --report results/action_lab/extended-local.json
~~~

Cada módulo de testes roda em um processo isolado, com timeout. O teste completo gera:
- **GitHub Job Summary:** tabela por módulo, contagem de testes e tempo;
- **Artifact JSON:** status, tempo, contagem e identidade do módulo, sem prompts pessoais;
- **Conclusão do job:** falha se qualquer módulo falhar, travar ou não executar testes.

Artifacts são retidos por 14 dias no modo sintético e por 7 dias no Qwen real. Não gravar prompts pessoais nos testes CI.

## Como pedir uma nova verificação pelo ChatGPT

O conector GitHub usado nesta conversa permite criar branches, commits, PRs e ler execuções/relatórios, mas não disponibiliza um comando de `workflow_dispatch`. Por isso o assistente pode acionar uma verificação **smoke** criando uma branch nova `lab/luna-<identificador>` baseada na `main` e um arquivo marcador inofensivo em `.github/lab-requests/<identificador>.md`. O `push` dessa branch ativa o workflow; o assistente então lê o status e os artefatos da execução. Isso não exige modificar o código de produção nem inserir secrets.

Para um teste ampliado solicitado no chat, a branch pode ter o prefixo `lab/luna-extended-` e o mesmo arquivo marcador. O workflow executa então `extended` no Linux e a validação `smoke` no Windows; ambos produzem relatórios. Os modos `extended` e `real-qwen` também podem ser selecionados pelo botão **Run workflow** na página Actions. Não executar download de GGUF em `push` ou `pull_request`: `real-qwen` é sempre opt-in manual.

## Política de segurança e limites

- GitHub Actions executa testes em runners temporários, não no computador local do usuário.
- Os bancos SQLite pessoais e os arquivos GGUF locais não são enviados ao GitHub; `.gitignore` continua protegendo dados locais gerados pelo projeto.
- A tarefa opt-in `real-qwen` baixa apenas as versões fixadas em `tools/install_windows_chat.py` e usa verificações SHA-256.
- Nenhum cache de pesos, SSD-first, ganho de RAM ou qualidade geral é alegado pelo smoke.
- PRs de terceiros podem executar código não confiável no runner; não conceder permissões de escrita/secrets aos testes.
- Para a validação de consumo de RAM no PC Windows físico, executar os benchmarks nativos e comparar com o baseline da Fase 4E-W. Runners de CI não substituem essa medição.

O código do executor é [`tools/action_lab.py`](../tools/action_lab.py). Os relatórios locais ficam em `results/action_lab/` (ignorados pelo Git).
