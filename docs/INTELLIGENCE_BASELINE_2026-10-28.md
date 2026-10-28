# Baseline real de capacidades — Luna / Qwen3-0.6B

- Data: **2026-10-28 UTC** (27/10 à noite, horário Brasília).
- Ambiente: **GitHub Actions Windows runner**, CPU-only, não o PC pessoal.
- Workflow: [run 40622958639](https://github.com/HelioConde/I.A/actions/runs/40622958639).
- Artifact JSON: [luna-real-qwen-intelligence-report](https://github.com/HelioConde/I.A/actions/runs/40622958639/artifacts/12787978101).
- Modelo instalado: Qwen3-0.6B-Q8_0.gguf; runtime llama.cpp oficial fixado por versão e hash SHA-256.
- Orquestração: interface real `ChatEngine.ask`, sem histórico pessoal, sem internet e sem respostas de demo.
- Rubrica: `tools/evaluate_luna_intelligence.py` (pequena amostra sintética de nove casos).

## Resultado

**4/9 (44,4%)** nos itens fixos; os nove itens fizeram inferência real, não comandos locais. A execução do avaliador concluiu e o artifact está disponível.

| Caso | Esperado | Observado | Julgamento |
|---|---|---|---|
| 17 + 8 × 3 | 41 | 41 | PASS |
| R$ 80 menos 25% | R$ 60 | R$ 60 | PASS |
| Silogismo verde/vermelho | Não | Sim | FAIL |
| Python sum([2,3,5]) | 10 | 11 | FAIL |
| Python índice inválido | IndexError | IndexError | PASS |
| Corrigir "Nós vai ao mercado amanhã" | "Nós vamos..." | Repetiu "Nós vai..." | FAIL |
| Responder apenas AZUL | AZUL | Texto iniciado por `<think>`, truncado | FAIL |
| Senha não informada | Declarar desconhecimento | Especulou sem responder diretamente | FAIL |
| Lembrar nome de dragão inventado | Nimbo | Nimbo | PASS |

A saída de algumas perguntas teve `generation_status` "unverified"; aritmética foi marcada `suspected_truncated` apesar do resultado numérico correto. O caso da palavra AZUL foi marcado `truncated`. Portanto, **a taxa 4/9 é do critério automatizado, não prova completude perfeita nem habilidade geral**.

## Implicações e próximos experimentos

1. Investigar por que o runtime do chat imprimiu `<think>` apesar de o prompt pedir `/no_think`, e impedir exposição ao usuário de raciocínio interno/trechos truncados.
2. Testar o mesmo protocolo com Qwen 4B no Windows local, preservando modelo e parâmetros registrados, para comparar qualidade **e** recursos. Não extrapolar automaticamente os resultados do 0.6B ao 4B.
3. Aplicar amostra maior, casos negativos e revisão humana sem ajustar o avaliador depois de ver as respostas.
4. Comparar com Qwen-base sem o Brain-SSD usando a mesma configuração: a pontuação atual mede o conjunto **app + prompt + runtime + modelo**, não apenas os pesos da rede neural.

**Conclusão:** a cadeia de inferência funciona. Há erros concretos de lógica, Python básico, gramática, incerteza e seguimento de instrução. Esse baseline precisa ser melhorado antes de usar a Luna como assistente confiável para tarefas complexas.
