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
