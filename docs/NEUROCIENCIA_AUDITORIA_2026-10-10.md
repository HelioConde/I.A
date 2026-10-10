# Brain-SSD × Neurociência: revisão fundamentada (10/10/2026)

> Esta revisão confronta literatura primária/revisões de neurociência com o estado do software. É uma pesquisa *orientada a hipóteses verificáveis*, não uma alegação de equivalência cérebro-humano ou transferência de consciência.

## Pergunta de pesquisa

**Quais princípios da cognição humana podem ser implementados e avaliados em um PC comum, especialmente Windows CPU-only e memória RAM limitada, sem simular biologia inexistente?**

## Evidências verificadas

| Tema | O que a literatura realmente sustenta | Implicação testável para Brain-SSD |
|---|---|---|
| Sistemas complementares (hipocampo–neocórtex) | Aprendizagem episódica rápida e integração cortical mais lenta; modelos procuram evitar interferência catastrófica. | Separar notas episódicas explícitas, memória de conversa de curto prazo, registros semânticos e pesos estáticos do Core. |
| Engramas, indexação, reconsolidação | Formação, reativação e atualização de engramas envolvem circuitos distribuídos; indexação hipocampal é modelo teórico influente, não algoritmo literal. | Episódios com IDs distintos, pistas parciais, proveniência, abstention, testes de colisão. Não confundir texto com engrama neuronal. |
| Replay durante sono | Reativação durante sono tem apoio experimental; modelos de replay cortico-hipocampal demonstram possível consolidação. | Planejamento de replay offline *somente leitura* antes de experimentar consolidação real; evitar sintetizar fatos e autoeditar pesos. |
| Prefrontal, gating e inibição | O sistema nervoso possui regulação seletiva da informação, inclusive supressão de recuperação. | Router/Gate atuais são bons precursores; falta teste de inibição aprendida e false-negative rate. |
| Predictive processing/dopamina | Predição e sinais de erro de recompensa ajudam a explicar aspectos do aprendizado, mas não toda cognição. | Instrumentar previsões calibradas e erro antes de adicionar aprendizagem online, sem 'dopamina artificial'. |
| Planejamento/replay | Modelos de simulação interna e córtex pré-frontal descrevem aspectos do planejamento. | Criar tarefas de planejamento comparáveis, teste de custo CPU versus acerto; não inventar 'pensamentos' ocultos. |
| Processamento sensório-motor | Conectomas e simulações de animais podem prever partes de comportamentos observáveis. | Futuro ciclo percepção–ação em ambiente simulado, feedback mensurável, sem misturar com produto chat. |
| Conectômica humana | Mesmo 1 mm³ de tecido exige mapeamento de quase 150 milhões de sinapses; mapeamento não fornece automaticamente estados nem lembranças individuais. | Não fabricar conectoma humano ou dizer que o chat reproduz consciência. |
| Interfaces cérebro–computador | Decodificação de fala imaginada/tentada e próteses de memória são pesquisas específicas, dependentes de eletrodos, calibração e tarefas. | Separar 'decodificação de sinal neural' de 'upload de personalidade/memória'. Não há um caminho de transferência de mente implementado aqui. |
| Simulação cerebral humana | Trabalhos de 2024 simularam aspectos de atividade com até 86 bilhões de neurônios em 14.012 GPUs; grande escala não comprova experiência subjetiva. | Um PC Windows CPU-only deve usar abstrações cognitivas funcionais pequenas, não emulação literal de cada sinapse. |

## Comparação com o código atual (10/10/2026)

| Componente | Estado real | Lacuna |
|---|---|---|
| Memória de trabalho | Últimos turnos no prompt com orçamento de bytes | Estado interno compacto independente de token context ainda limitado |
| Memória episódica | **Novo experimento opt-in**: notas manuais SQLite, IDs individuais, pistas lexicais parciais, exclusão e proveniência | Não é engrama neural, não recupera pistas semânticas não lexicais, não aprende sozinho |
| Memória semântica | Corpus SSD via manifest, index, mmap, registros | Corpus factual não é igual à aprendizagem cortical contínua |
| Router e gate | HYBRID/TF-IDF e gating por budget | Falta computação inibitória adaptativa e medição causal geral |
| Atenção | Context Builder, budgets e ativação seletiva | Precisa calibrar seleção com qualidade e custo por consulta |
| Aprendizado gradual | Experimentos de contexto e cache; pesos do Qwen estáticos | Sem continual learning estável, validação de plasticidade ou rollback de pesos |
| Replay/sono | `replay_candidates()` é apenas lista *read-only* para teste | Sem consolidação offline; não chamar de sono real |
| Predição/planejamento | Qwen gera respostas e alguns algoritmos fazem ranking | Não há previsão-error loop ou planejamento estruturado validado |
| Corpo e sensores | Chat textual local | Sem ambiente percepção–ação e correção motora por feedback |
| Consciência/transferência cerebral | **Não implementadas** | Não existe evidência para prometer uma cópia digital da pessoa |

## Mudança de engenharia aprovada nesta revisão — trilha experimental isolada

Foi criado o módulo `src/brain_ssd/chat/episodic.py`, usando biblioteca-padrão SQLite. Características:

- **Privacidade primeiro**: desativado por padrão; ative explicitamente com `python tools/run_chat.py --episodic-memory` ou pelo BAT próprio.
- **Aprendizagem de episódio por consentimento**: nenhuma conversa ou resposta da IA vira fato automaticamente; o usuário escreve a nota, de até 500 caracteres.
- **Separação de padrões mínima**: notas similares têm identificadores separados; não são sobrescritas nem fundidas silenciosamente.
- **Recuperação seletiva**: índice de termos e condição de duas pistas significativas (ou uma em perguntas de uma palavra); retorna no máximo três notas; pistas sem coincidência provocam abstention.
- **Proveniência e não-instrução**: notas explícitas entram no prompt sob rótulo separado do conhecimento SSD, com aviso de que são dados e podem estar desatualizadas.
- **Controle e esquecimento**: usuário vê e pode excluir qualquer nota; exclusão lógica SQLite não equivale a apagamento forense do SSD.
- **Replay seguro**: apenas candidatos para revisão offline; não há consolidação, reescrita de conhecimento semântico, treino de pesos ou habilidade automática.
- **Orçamento**: notas cabem no orçamento do chat *antes* de evidência SSD, sem cortar frases no meio; custo real de memória e recuperação ainda requer medições.
- **Integração limitada**: somente chat experimental, preservando os benchmarks V0/4E-W/4F-W e sem reclassificá-los como validados biologicamente.

## Próximos experimentos em ordem de rigor

1. **Memória episódica A/B**: habilitada vs desabilitada, 100+ perguntas sintéticas de pistas parciais, notas parecidas/contraditórias, perguntas fora de domínio; métricas precision, recall, false retrieval, hallucination e latência, RAM no Windows.
2. **Revisão/replay offline**: lista de candidatos com recência, novidade e confirmação, sem gerar fatos novos; somente promover resumos para 'semantic candidate' após checagem de consistência e aprovação explícita.
3. **Consolidação testada**: se o replay offline não aumentar erros, testar sínteses em sandbox com proveniência, rollback e avaliação contra transcript original; não atualizar pesos automaticamente.
4. **Plasticidade e controle inibitório**: metadados de links episódicos, suporte mínimo, decay reversível e negativa de recuperação; benchmark de falsos negativos vs brute-force lexical.
5. **Predição e feedback**: medir erro de previsão e utilidade computacional antes de permitir adaptação online.
6. **Ambiente fechado de percepção–ação**: simulação externa controlada (não conectoma) para tarefas observáveis, planejamento, recompensa e correção via feedback.
7. **Hardware real**: Windows CPU-only + testes Debian TARGET_8GB pendentes. Medir qualidade, memória total, I/O, TTFT, tokens/s e ganho vs Qwen sem Brain-SSD.

## O que não fazer

- Não prometer que a IA sente, tem consciência, sonha ou 'vive' como cérebro.
- Não afirmar que uma ressonância, EEG ou conectoma pode copiar a memória pessoal completa.
- Não criar bilhões de neurônios Python, ondas theta falsas, plasticidade sem avaliação ou camadas sempre ativas.
- Não armazenar informações pessoais automaticamente sob o pretexto de imitar a memória humana.
- Não mesclar as notas humanas confirmadas com saída alucinada do Qwen como se ambas fossem fatos confiáveis.

## Bibliografia central (URLs das fontes)

1. Norman (2010), Complementary Learning Systems: https://pmc.ncbi.nlm.nih.gov/articles/PMC3416886/
2. McClelland et al. (2020), Integration of new information in memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC7209926/
3. Engram neurons, encoding/retrieval/forgetting: https://pmc.ncbi.nlm.nih.gov/articles/10618102/
4. Chang et al. (2025), Sleep microstructure organizes memory replay: https://www.nature.com/articles/s41586-024-08340-w
5. Giri et al. (2024), Sleep loss diminishes hippocampal replay: https://www.nature.com/articles/s41586-024-07538-2
6. Anderson et al. (2025), Brain mechanisms of inhibitory control of thought: https://www.nature.com/articles/s41583-025-00929-y
7. Gershman et al. (2024), Explaining dopamine through prediction errors and beyond: https://www.nature.com/articles/s41593-024-01705-4
8. Jensen et al. (2024), A recurrent network model of planning and replay: https://www.nature.com/articles/s41593-024-01675-7
9. Dorkenwald et al. (2024), Adult Drosophila wiring diagram: https://www.nature.com/articles/s41586-024-07558-y
10. Shiu et al. (2024), Drosophila computational brain and behavior: https://www.nature.com/articles/s41586-024-07763-9
11. Human cortex 1 mm³ connectome: https://www.nature.com/articles/s41593-024-01688-2
12. Digital Brain simulation: https://www.nature.com/articles/s43588-024-00731-3
13. Inner speech BCI (Cell, 2025): https://pmc.ncbi.nlm.nih.gov/articles/PMC12360486/
14. Stanford Neuroscience (2025), brain implants can't read arbitrary thoughts: https://neuroscience.stanford.edu/news/could-brain-implants-read-our-thoughts-not-yet
15. Memory neuroprosthesis (2024): https://pmc.ncbi.nlm.nih.gov/articles/PMC10881797/

**Síntese:** a tese principal do Brain-SSD (grande capacidade no SSD, pequena ativação por tarefa) é uma abstração válida para experimentar, mas o gargalo fundamental é demonstrar aprendizado, recuperação confiável, qualidade e custo, não replicar a anatomia cerebral por aparência.
