# Luna Intelligence Lab — diagnóstico de capacidade real

Este experimento faz perguntas **ao Qwen real** pelo adaptador de chat Brain-SSD/Luna, sem usar respostas mock ou demo do Pages.

## Escopo e interpretação

- Nove itens sintéticos e verificáveis: cálculos, lógica, código Python, português, seguimento de instruções, incerteza e memória curta de dois turnos.
- Nenhum caso busca internet ou banco de conversas pessoal. O histórico criado no teste é inteiramente fictício.
- O score mede o desempenho **nesses itens fixos**, usando heurísticas estreitas. Não é QI nem um benchmark amplo de inteligência.
- O teste identifica se houve inferência pelo modelo ou se um comando local respondeu. Uma resposta local **não pontua**.
- As perguntas e respostas sintéticas são intencionalmente armazenadas no artifact público para revisão manual. Não usar prompts pessoais na CI.
- Resultado insuficiente em perguntas complexas não prova que todo modelo maior vai melhorar; testar 4B na mesma máquina com protocolo idêntico pode ajudar.

## Como executar

O workflow está em [intelligence-lab.yml](../.github/workflows/intelligence-lab.yml).

**No GitHub:** Actions → Luna Intelligence Lab → Run workflow. O job real Windows baixa o GGUF oficial Qwen3-0.6B Q8_0 e a versão de llama.cpp fixada no repositório com validação SHA-256.

**Pelo assistente conectado ao GitHub:** uma branch `lab/luna-intelligence-*` que contenha a implementação e um marcador em `.github/lab-requests/intelligence-*.md` dispara a avaliação real. Esse gatilho **somente** funciona para pedidos explícitos de testar a inteligência, porque inicia download e inferência em runners Windows; outras alterações não acionam o job custoso.

**Teste da rubrica sem modelo:**

~~~powershell
python tools/evaluate_luna_intelligence.py --self-test
~~~

**Avaliação local no Windows, com o modelo e o llama.cpp instalados:**

~~~powershell
python tools/evaluate_luna_intelligence.py --profile economia
~~~

O relatório vai para `results/chat_validation/intelligence.json`, que já está ignorado pelo Git. É publicado como artifact no job quando a execução real ocorre.

## Cuidados

O runner Github **não é o Windows físico do proprietário**, e o GGUF testado é o **0.6B**, não o 4B que pode estar instalado localmente. A base SSD opcional pode não estar disponível no runner. Avalia-se aqui a habilidade observada no chat com Core real, não a economia de RAM por streaming SSD.

A CI falha se não houver inferência real em todos os casos; uma pontuação baixa com inferência concluída é um **resultado científico válido**, não um erro de infraestrutura. Cada resposta deve ser examinada qualitativamente antes de escolher melhorias.
