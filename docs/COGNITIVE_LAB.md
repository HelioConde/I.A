# Laboratório cognitivo do Brain-SSD — Etapa experimental 2026-10-10

**Ambiente:** Windows/Linux, Python 3.11+, biblioteca-padrão. Sem GPU, download,
internet, modelo GGUF ou ações fora da simulação. Independente do baseline das
Fases 1–4E e dos algoritmos canônicos de retrieval/SSD.

## Executar
```powershell
python tools/run_cognitive_lab.py
python -m unittest discover -s tests -p 'test_cognitive_lab.py' -v
```


Nenhum banco de dados do usuário é lido: a demonstração usa diretório temporário
e notas sintéticas. O resultado JSON é identificado como
`OFFLINE_SYNTHETIC_SHADOW_ONLY`. Não é prova de redução de RAM nem
de que a IA funciona como um cérebro.

## Mecanismos e lacunas
| Objetivo | Implementação desta fase | Restrição e teste necessário |
| --- | --- | --- |
| Atenção seletiva | Ranking por cobertura lexical, até N candidatos, orçamento em bytes, abstenção | Shadow: não descarta evidência do Core. Medir recall e falsos negativos contra roteador original |
| Memória de trabalho | Metadados curtos de tópicos e últimos turnos, memória temporária | Não substitui janela de contexto do Core; A/B antes de ativar compressão |
| Memória episódica | SQLite explícito já existente, episódios confirmados separados | Sem aprendizagem automática de dados pessoais |
| Associação | Propostas de links por interseção de termos, IDs separados | Shadow, sem inferir causalidade nem navegar ligações automaticamente |
| Consolidação offline | Replay de IDs associados confirmado, somente leitura | Não promove notas para fatos nem treina pesos |
| Plasticidade | Ledger SQLite explícito +1/-1, suporte mínimo de 3, decaimento, revogação | Somente viés de ranking shadow [-0,15,+0,15]; não implica verdade e não altera modelo |
| Erro de previsão | Probabilidade + resultado verdadeiro explícito, erro e Brier | Sem observação verificada não pode aprender; não é dopamina sintética |
| Percepção e ação | GridWorld local, percepção dos quatro vizinhos e ações discretas seguras | Sem câmera, microfone, navegador, robótica ou controle de PC |
| Emulação neural / upload da mente | **Não implementados** | Não há capacidade demonstrada de copiar memória integral ou consciência humana |

## Protocolo de promoção

* Criar baseline sem o módulo e grupo de intervenção, mesma tarefa.
* Separar holdout e casos desconhecidos/contraditórios.
* Requerer precisão, recall, falsos reconhecimentos, risco de privacidade e
  recursos (RAM, CPU, TTFT, bytes ativos).
* Em caso de regressão de qualidade, não permitir que o componente afete
  retrieval/inferência: manter em shadow ou rejeitar.
* Para qualquer aprendizagem persistente, fornecer aprovação explícita, log,
  limite, rollback e limpeza de dados.
* Nenhuma ação simulada dá acesso ao sistema operacional.

**Cuidado:** o comando de demonstração não é um chatbot cognitivo novo. É um
conjunto limitado de hipóteses testáveis. O funcionamento com Qwen exige
outra matriz de qualidade, no Windows real.

## Integração opcional no chat

Para obter diagnósticos somente shadow, execute:

    python tools/run_chat.py --profile economia --episodic-memory --cognitive-shadow

A janela Diagnóstico local mostra bytes do estado compacto e número de
candidatos de atenção. Isso não altera o prompt, não descarta fontes do Core
nem atualiza os pesos do modelo. Sem a flag, não há processamento extra.
O BAT INICIAR-CHAT-MEMORIA-WINDOWS.bat ativa explicitamente os experimentos;
o BAT comum continua usando o chat básico.

## Reforço tabular no mundo fechado

`TabularActionLearner` usa Q-learning simples com estado formado apenas
pela posição observada pelo agente, ações up/down/left/right, recompensa
do ambiente e atualização por diferença entre valor esperado e observado.
O treino tem limite de 500 episódios de até 100 ações cada. A avaliação
executa uma política gulosa nova sem novas atualizações e registra sucessos,
ações e quantos parâmetros tabulares mudaram. Isso é aprendizagem real,
mas **somente dentro do mundo sintético**, sem acesso a programas, rede,
sensores reais ou pesos do Qwen. Não é simulação de cérebro humano.

## Consolidação revisada manualmente (sem treinar pesos)

O módulo consolidation.py recebe entre duas e seis notas episódicas já
confirmadas, exige duas pistas em comum, preserva IDs de origem e cria
apenas um rascunho. A revisão exige um resumo escrito pelo usuário.
Rejeição, revogação e exclusão podem ser feitas depois. O resumo aprovado
fica numa fila SQLite SEPARADA e não se torna conhecimento factual
do Qwen ou do corpus SSD automaticamente.

Com memórias já salvas no chat opt-in:

    python tools/review_cognitive_memory.py
    python tools/review_cognitive_memory.py --propose EPISODE_ID_1 EPISODE_ID_2
    python tools/review_cognitive_memory.py --approve DRAFT_ID --summary "Resumo revisado"
    python tools/review_cognitive_memory.py --revoke REVIEWED_ID

Sem flags de mutação, o comando apenas lista candidatos. Não é sono
biológico nem consolidação cortical; é um fluxo humano de revisão.

## Verificação de memórias potencialmente divergentes (2026-10-10)

O chat experimental agora sinaliza quando **duas notas episódicas
confirmadas** compartilham assunto, mas registram dias da semana
diferentes. O aviso diz apenas que podem ser eventos distintos;
não escolhe uma fonte por ser mais recente, não apaga nem reescreve notas
e pede esclarecimento caso a pergunta não identifique qual evento.

A verificação não identifica todas as contradições, mudanças de endereço,
valores monetários ou paráfrases sem termos comuns. Ela é deliberadamente
conservadora e não comprova que o Qwen obedecerá ao aviso.

Rode `python tools/bench_memory_quality.py` para executar o conjunto
**pequeno e sintético** de 24 consultas positivas, 20 perguntas negativas,
5 cenários de ambiguidade e 1 verificação de exclusão/reabertura.
O benchmark não usa modelos de linguagem nem mede raciocínio ou qualidade
de conversação. Não promover mudanças para sistemas canônicos apenas com
esse resultado.

Feedbacks guardados no laboratório de plasticidade passam a fornecer viés
**zero** se sua memória de origem tiver sido excluída. A exclusão lógica
não remove automaticamente backups nem registros históricos da fila de
revisão; esse tratamento exige auditoria específica de retenção.

## Ponte de sinônimos PT-BR — experimento opt-in

A camada `semantic_bridge.py` contém **10 grupos de sinônimos estreitos e
auditáveis** (por exemplo, *reunião/encontro* e *cachorro/cão*).
Ela amplia pistas sem transferir dados a serviços externos e exige, em casos
exclusivamente semânticos, pelo menos dois conceitos distintos em comum.
Não se trata de embeddings, compreensão semântica geral, aprendizagem dos
pesos ou decodificação cerebral.

**Padrão: DESATIVADO.** No chat:

```powershell
python tools/run_chat.py --profile economia --episodic-memory --memory-aliases
```

Use sem `--memory-aliases` para obter exatamente a recuperação lexical
original. A quantidade de notas trazidas apenas por sinônimos aparece nas
métricas da resposta e no JSONL local como contagem — sem conteúdo textual.
O recurso precisa de testes A/B e validação com o Qwen físico antes de uma
eventual promoção para padrão.

### Alertas adicionais de conflito (conservadores)

Além de dias da semana, o diagnóstico reconhece diferenças entre duas
memórias explicitamente confirmadas sobre o **mesmo assunto aparente** em
datas ISO/DD/MM/AAAA, horários (ex.: 14h30 × 15:30) e preços com prefixo
`R$` brasileiro. A regra exige pelo menos dois termos de assunto comuns
e exatamente um valor explícito de cada categoria por nota. Isso reduz
alertas incorretos, mas perde casos sem texto coincidente.
Não interpreta valores em moedas estrangeiras, não reconcilia eventos,
não prova inconsistência factual e não escolhe uma das notas como verdadeira.

### Proteção quando o contexto é insuficiente

Um orçamento reduzido pode permitir colocar **apenas uma** das duas notas
possivelmente divergentes no prompt. O chat agora evita escolher
silenciosamente uma delas: se não couberem as duas fontes **e o aviso**
de incerteza, retira as notas disputadas do prompt e informa no retorno
`episodic_ambiguities_withheld=true`. Esse mecanismo sacrifica cobertura
para não apresentar evidência parcial como verdade única.

### Exibição da proteção na interface

Quando o aviso de divergência e ambas as notas não cabem no orçamento de
prompt, a resposta HTTP inclui `episodic_ambiguities_withheld: true`.
A interface informa explicitamente que **nenhuma das fontes conflitantes
foi escolhida apenas para caber** e recomenda esclarecer o evento ou
aumentar o contexto. Isso não garante que o Qwen interprete corretamente
um conflito quando todas as notas couberem — essa qualidade precisa de
avaliação com o modelo verdadeiro.
