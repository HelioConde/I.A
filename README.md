# Brain-SSD

**Uma arquitetura experimental de IA local, inspirada em princípios de memória, atenção e aprendizagem do cérebro humano.**

O objetivo do Brain-SSD é investigar se uma IA pode **manter muito conhecimento persistente no SSD e ativar somente uma pequena parte por tarefa**, usando CPU comum, sem depender de GPU dedicada ou APIs de inferência externas.

> **Status — 10/10/2026:** pesquisa aplicada e protótipo Windows em desenvolvimento. O sistema **não é uma simulação biológica do cérebro**, não transfere memórias humanas e ainda **não demonstrou**, em uma validação completa no hardware-alvo, vantagem de RAM/qualidade sobre a execução convencional do Qwen.

[Começar no Windows](#começar-no-windows) · [Laboratório cognitivo](#laboratório-cognitivo) · [Estado do desenvolvimento](#estado-do-desenvolvimento) · [Próximos objetivos](#próximos-objetivos) · [Documentação](#documentação)

---

## A ideia

A inspiração é funcional, não anatômica: seres humanos não precisam ativar todas as lembranças simultaneamente para responder a uma pergunta. O Brain-SSD pesquisa a mesma **seletividade computacional** por meio de roteamento, memória episódica, contexto limitado, associação e avaliação de custo.

**Princípio de pesquisa:** capacidade persistente total muito maior que a quantidade de informação/processamento ativada em uma consulta.

O cérebro humano tem mecanismos muito mais complexos do que os implementados aqui. Palavras como *hipocampo*, *córtex*, *consolidação* e *plasticidade* são **analogias de engenharia**, não evidência de equivalência biológica.

### Arquitetura atual

```mermaid
flowchart TD
    A["Pergunta do usuário"] --> B["Chat local / contexto recente"]
    B --> C{"Recuperação necessária?"}
    C -->|Sim| D["Router / Gate / seleção SSD opcional"]
    C -->|Não| F["Prompt com orçamento de contexto"]
    D --> F
    E["Memórias episódicas explícitas — opt-in"] --> F
    F --> G["Qwen3-0.6B GGUF + llama.cpp / CPU"]
    G --> H["Resposta em streaming + histórico local"]
    B -.-> I["Laboratório cognitivo (shadow)"]
    E -.-> I
    I -.-> J["Atenção, estado compacto, associações e avaliações"]
```

As setas pontilhadas representam **experimentos de diagnóstico**, que **não alteram automaticamente** as respostas nem os pesos do modelo.

## Estado do desenvolvimento

| Área | O que existe | Limite atual |
| --- | --- | --- |
| **Inferência local** | Adaptador para `llama.cpp` CPU-only com Qwen3-0.6B Q8_0 | GGUF e binários precisam estar instalados localmente; teste E2E no PC do usuário pendente |
| **Chat Windows** | Interface, streaming, botão Parar, histórico SQLite e diagnósticos | Beta experimental; não há instalador autônomo completo |
| **SSD seletivo** | Páginas lógicas, índice, roteamento e recuperação de `KnowledgeRecords` | O `brain.dat` completo é opcional para o chat, mas necessário para recuperar a base SSD |
| **Atenção** | Seleção por pistas e orçamento de bytes | Mecanismo cognitivo em **shadow**; melhora de qualidade ainda não comprovada |
| **Memória de trabalho** | Tópicos recentes em estado compacto e histórico limitado | Não equivale à memória de trabalho biológica |
| **Memória episódica** | Notas explícitas, IDs separados, recuperação por pistas e exclusão | Opt-in; não aprende fatos automaticamente de toda conversa |
| **Associação** | Links candidatos entre episódios confirmados | Somente propostas; não implica causalidade |
| **Consolidação** | Fila offline com fontes, aprovação, rejeição e revogação | Não transfere automaticamente notas para o conhecimento do Qwen |
| **Plasticidade / feedback** | Metadados reversíveis com limite, suporte mínimo e decaimento | Não modifica pesos do Qwen ou a verdade factual |
| **Erro de previsão** | Probabilidade, resultado verificado, Brier score e rollback | Aprendizagem limitada a estimativas por tarefa |
| **Percepção e ação** | `GridWorld` isolado com Q-learning e recompensa | Apenas simulação; sem câmera, robótica ou controle do computador |
| **Emulação neural / consciência** | **Não implementadas** | Não há tecnologia comprovada de transferência integral da mente |

## Começar no Windows

Requisitos para **conversar realmente com o modelo**: Windows 10/11 x64, Python 3.11+, `llama.cpp` compatível e o arquivo `Qwen3-0.6B-Q8_0.gguf` local.

**O repositório não distribui o GGUF nem todos os executáveis e dados do runtime.** A aprovação da compilação no GitHub Actions **não significa** que o modelo já esteja incluído no launcher.

1. Clone ou atualize este repositório e siga o [guia de preparação do runtime Windows](docs/WINDOWS_NATIVE_RUNTIME.md).
2. Coloque o GGUF esperado na pasta `models/` e configure o `llama.cpp` CPU-only conforme o guia.
3. Abra `DIAGNOSTICAR-CHAT-WINDOWS.bat` para conferir os requisitos (ou execute `python tools/doctor_chat.py --profile economia`).
4. Abra `INICIAR-CHAT-WINDOWS.bat`. O chat será servido em **http://127.0.0.1:8766**.
5. Envie **“Olá!”** e, para conferir a geração real, execute o teste abaixo.

```powershell
python tools/validate_chat_windows.py --profile economia
```

O teste grava um relatório local em `results/chat_validation/latest-local-windows.json`. **Somente executá-lo com o modelo verdadeiro comprova inferência naquela máquina.** Veja instruções detalhadas em [CHAT_WINDOWS.md](docs/CHAT_WINDOWS.md).

### Perfis de execução

| Perfil | Threads | Contexto configurado | Estratégia |
| --- | ---: | ---: | --- |
| `economia` **(padrão)** | 2 | 2.048 | Processo de inferência descarregado após a consulta |
| `equilibrado` | 4 | 4.096 | Processo descarregado após a consulta |
| `rapido` | 4 | 4.096 | `llama-server` persistente; mantém o modelo carregado por mais tempo |

```powershell
python tools/run_chat.py --profile economia
python tools/run_chat.py --profile equilibrado
python tools/run_chat.py --profile rapido
```

**Nenhum perfil garante uma quantidade específica de RAM.** Um perfil persistente pode diminuir a latência, mas normalmente mantém mais memória ocupada.

### Memória explícita e modo cognitivo experimental

A memória episódica está **desativada por padrão**. Para salvar lembranças intencionalmente e observar métricas cognitivas sem alterar o prompt de inferência:

```powershell
python tools/run_chat.py --profile economia --episodic-memory --cognitive-shadow
```

No Windows também é possível abrir `INICIAR-CHAT-MEMORIA-WINDOWS.bat`. No painel lateral, **Guardar uma lembrança** registra apenas uma nota escolhida pelo usuário; é possível apagá-la. Não salve senhas ou dados confidenciais.

O modo `--cognitive-shadow` calcula diagnósticos de atenção/memória de trabalho, **sem substituir o mecanismo principal de recuperação ou retreinar o modelo**.

## Laboratório cognitivo

Os experimentos abaixo executam **sem modelo GGUF, GPU, internet ou acesso a conversas reais**, em diretórios temporários e com dados fictícios:

```powershell
python tools/run_cognitive_lab.py
python tools/bench_episodic_memory.py
python -m unittest discover -s tests -p "test_cognitive_lab.py" -v
python -m unittest discover -s tests -p "test_consolidation.py" -v
```

O laboratório inclui atenção sob limite de recursos, representação compacta, associação, `replay` de leitura, feedback reversível, erro de previsão e um agente que aprende por recompensa **dentro de um tabuleiro simulado**.

No experimento determinístico atual, o agente inicialmente não alcançava o destino no limite de 100 ações e, após 400 episódios sintéticos de treinamento, alcançou-o em oito ações na avaliação. **Isso não é um benchmark de inteligência geral nem uma melhora validada do Qwen.**

A consolidação de episódios tem um comando específico para **revisão manual**:

```powershell
# Visualizar candidatos já existentes, sem modificar nada:
python tools/review_cognitive_memory.py

# Exemplos de operações explícitas (IDs reais devem ser fornecidos):
python tools/review_cognitive_memory.py --propose EPISODE_ID_1 EPISODE_ID_2
python tools/review_cognitive_memory.py --approve DRAFT_ID --summary "Resumo revisado"
python tools/review_cognitive_memory.py --revoke REVIEWED_ID
```

Os resumos aprovados **não são inseridos automaticamente nos pesos do Qwen nem no corpus SSD**. Consulte [COGNITIVE_LAB.md](docs/COGNITIVE_LAB.md).

## Resultados e limites científicos

O projeto preserva experimentos históricos de armazenamento, `mmap`, cache, roteamento e custo de contexto. Estes resultados devem ser interpretados **somente nos cenários em que foram medidos**.

- O GitHub Actions executa testes do chat usando **backends simulados** e testes reais de término de processos, mas **não inclui o modelo GGUF**.
- Os testes do laboratório cognitivo verificam algoritmos e segurança de execução, **não equivalência ao cérebro humano**.
- Algumas técnicas de redução de contexto diminuíram o custo de processamento, mas mostraram perda de cobertura factual. Por isso, não se tornam padrão sem um **quality gate**.
- Ainda faltam comparações completas com `llama.cpp` puro, incluindo **qualidade em português, memória do processo e da aplicação, RAM do sistema, CPU, I/O físico, TTFT e tokens/s**.
- A validação física canônica em hardware Debian com alvo de **8 GB de RAM** permanece pendente.

Verifique o estado das automações: [Chat Linux](https://github.com/HelioConde/I.A/actions/workflows/chat-smoke.yml) · [Chat/launcher Windows](https://github.com/HelioConde/I.A/actions/workflows/windows-chat.yml) · [Regressão do núcleo](https://github.com/HelioConde/I.A/actions/workflows/core-regression.yml).

## Privacidade e segurança

- Chat HTTP vinculado a `127.0.0.1`, com checagem de origem para operações de escrita; **não exponha a porta por túnel**.
- Histórico persistente e notas episódicas armazenados em **SQLite local**, fora do repositório.
- Memórias de longo prazo são **opt-in**. Feedback e consolidação exigem ações explícitas; há mecanismos de revogação.
- A exclusão do SQLite não garante apagamento físico irrecuperável de blocos SSD/backups.
- Os módulos experimentais de ação operam apenas em ambiente simulado, sem permissão para controlar o computador.
- Respostas de modelos e memórias recuperadas podem conter erros ou informações desatualizadas.

## Logs e análise dos testes

O Brain-SSD registra **eventos estruturados locais**, sem salvar o texto das perguntas,
respostas ou lembranças. No Windows, execute `GERAR-LOGS-WINDOWS.bat` para rodar testes
e gerar um ZIP sanitizado que pode ser anexado à conversa para análise. O GitHub Actions
também publica pacotes de diagnóstico das suítes simuladas.

[Guia de coleta, privacidade e exportação](docs/LOGS_DIAGNOSTICOS.md).

## Qualidade e segurança de memória (experimento)

O chat com memória episódica agora sinaliza **possíveis datas divergentes**
entre notas confirmadas relacionadas ao mesmo assunto, sem escolher uma
como verdade automaticamente. O aviso é uma hipótese conservadora:
podem ser eventos diferentes, não lembranças incorretas.

Correções adicionais preservam pistas relevantes no final de perguntas longas,
normalizam o campo de confirmação vindo do SQLite para uso por associação
e replay, e impedem que feedback de uma memória excluída continue
influenciando o ranking experimental.

Execute `python tools/bench_memory_quality.py`: o conjunto sintético
e lexical contém **24 recuperações positivas, 20 negativas, 5 verificações
de ambiguidade e 1 de exclusão**. Os resultados não medem qualidade do Qwen,
generalização semântica nem memória humana. Veja [COGNITIVE_LAB.md](docs/COGNITIVE_LAB.md).
### Experimento de sinônimos (desativado por padrão)

A busca episódica pode testar uma **ponte restrita de sinônimos PT-BR**, sem
bibliotecas de embeddings nem conexão externa. É ativada exclusivamente
por `python tools/run_chat.py --episodic-memory --memory-aliases`.
O teste A/B `python tools/bench_semantic_bridge.py` mede recuperação e
falsas associações sobre dados inventados. Sinônimos não representam
compreensão semântica geral, e resultados sintéticos não comprovam melhoria
no Qwen. Consulte [COGNITIVE_LAB.md](docs/COGNITIVE_LAB.md).

## Próximos objetivos

1. **P0 — Inferência ponta a ponta no Windows:** confirmar “Olá!”, sessões com vários turnos, encerramento de processos e comportamento offline com GGUF real.
2. **P0 — Qualidade e custo:** comparar Qwen sozinho × Brain-SSD usando o mesmo conjunto de perguntas e medir RAM, CPU, SSD, latência e correção.
3. **P1 — Avaliação cognitiva:** criar conjunto amplo de testes de memória, pistas parciais, contradições, desconhecidos e retenção entre sessões.
4. **P1 — Integração condicionada:** promover módulos de atenção/associação/feedback do modo `shadow` somente se trouxerem ganhos reproduzíveis sem perda de qualidade.
5. **P1 — Consolidação segura:** revisão, proveniência, rollback e medição de esquecimento/interferência antes de qualquer aprendizagem automática.
6. **P2 — Experiência Windows:** empacotamento reproduzível, configuração simples, tratamento de erros, atualizações e instalador completo.
7. **Pesquisa futura:** avaliar percepção–ação em ambientes mais ricos e aprendizagem incremental, sempre com limites de recursos e controles.

**Meta de aceitação:** demonstrar que a arquitetura adiciona utilidade ou eficiência **mensurável** frente ao baseline convencional; não basta adicionar módulos com nomes inspirados no cérebro.

## Documentação

| Tema | Documento |
| --- | --- |
| Instalação e chat Windows | [CHAT_WINDOWS.md](docs/CHAT_WINDOWS.md) |
| Runtime Windows CPU-only | [WINDOWS_NATIVE_RUNTIME.md](docs/WINDOWS_NATIVE_RUNTIME.md) |
| Experimentos cognitivos | [COGNITIVE_LAB.md](docs/COGNITIVE_LAB.md) |
| Neurociência e transferência de memórias | [NEUROCIENCIA_AUDITORIA_2026-10-10.md](docs/NEUROCIENCIA_AUDITORIA_2026-10-10.md) |
| Princípios biológicos e seus limites | [BIOLOGICAL_PRINCIPLES.md](docs/BIOLOGICAL_PRINCIPLES.md) |
| Arquitetura de pesquisa V2 | [NEUROARCHITECTURE_V2.md](docs/NEUROARCHITECTURE_V2.md) |
| Hipóteses testáveis | [HYPOTHESIS_REGISTRY.md](docs/HYPOTHESIS_REGISTRY.md) |
| Auditoria e prioridades | [AUDITORIA_GERAL_2026-10-10.md](docs/AUDITORIA_GERAL_2026-10-10.md) |
| Windows 4E-W e contexto 4F-W | [PHASE_4EW_WINDOWS_VALIDATION.md](docs/PHASE_4EW_WINDOWS_VALIDATION.md) · [PHASE_4FW_CONTEXT_EFFICIENCY.md](docs/PHASE_4FW_CONTEXT_EFFICIENCY.md) |

---

**Brain-SSD é pesquisa de engenharia cognitivamente inspirada.** Não existe hoje, neste projeto, emulação neuronal humana, upload de consciência ou transferência integral de memórias pessoais para um computador.
