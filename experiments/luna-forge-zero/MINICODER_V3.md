# Luna MiniCoder V3 — experimento de completação supervisionada

V3 é uma trilha independente: inicializa um Transformer pequeno do zero e não
carrega, converte ou sobrescreve pesos V0/V2. O fluxo V0/V2, `train_github.py`,
`luna_codegen_model.py` e seus formatos de checkpoint continuam separados.

## Dados e separação

`minicoder_v3_curriculum.json` contém exemplos JavaScript genéricos escritos
originalmente para Luna. Não consulta o coletor GitHub/MIT, arquivos KOM,
Elsword, Grand Chase ou scripts externos. As tarefas de treino cobrem
movimentação, pulo, gravidade, colisão, dano, patrulha, coletáveis, temporizadores
e transições de estado. Validação e teste usam projetos e famílias diferentes,
e nenhuma solução do split de teste está armazenada no arquivo. Os casos
funcionais do teste são especificações de entrada/saída, não exemplos de
treinamento. Uma pequena seleção de exemplos de treino é relatada separadamente
como diagnóstico de memorização.

O treinador verifica a separação de projetos/famílias, exige soluções completas
apenas em treino/validação e recusa sobrescrever o diretório de saída. Salva os
pesos do passo logado com menor perda de validação, em vez de assumir que o
último passo é melhor. Cada exemplo é serializado com tarefa estruturada e
`LANGUAGE: JavaScript`; a perda
causal ignora todos os tokens do prompt e todos os tokens de padding. O código
completo e o token especial EOS recebem supervisão. A geração interrompe no EOS
e informa se o término foi observado.

## Arquitetura e orçamento

- Tokenizador de caracteres ASCII, IDs 0–127, `PAD=128`, `EOS=129`.
- Contexto de 512 tokens, largura 32, quatro cabeças, uma camada causal.
- Inicialização aleatória; embeddings de token e saída são compartilhados.
- O relatório registra número de parâmetros e bytes de pesos FP32. O limite
  teórico da matriz de atenção em FP32 para batch 4 é aproximadamente 16 MiB
  (`4 × 4 cabeças × 512² × 4 bytes`); pesos e estados do otimizador são
  adicionais. É uma estimativa, não uma medição de RSS. Esse orçamento é pequeno
  para CPU/16 GB, mas desempenho e tempo dependem da máquina.

## Treinar e avaliar localmente no Windows

No PowerShell, a partir de `experiments\luna-forge-zero`:

```powershell
.\.venv\Scripts\python.exe -B .\train_minicoder_v3.py `
  --out .\checkpoints\luna-minicoder-v3-candidate `
  --steps 400 --batch 4 --threads 2 --seed 20261029

.\.venv\Scripts\python.exe -B .\gameplay_contracts.py `
  --checkpoint .\checkpoints\luna-minicoder-v3-candidate
```

O segundo comando só verifica sintaxe e hashes; não executa código candidato.
Execução funcional é explicitamente opt-in:

```powershell
.\.venv\Scripts\python.exe -B .\gameplay_contracts.py `
  --checkpoint .\checkpoints\luna-minicoder-v3-candidate --behavior
```

`--behavior` só usa a execução existente no Docker offline (`--network=none`,
container somente leitura, sem capabilities, usuário não privilegiado, limites
de CPU/memória/processos e timeout). Sem Docker ou imagem local preinstalada, o
resultado é indisponível, nunca um passe. Testes manuais da infraestrutura não
contam como pontuação do checkpoint.

O comparador `evaluate_github_codegen.py` mantém as cinco strings de prompt
originais e aceita checkpoint V3 ou MiniCoder anterior. Sintaxe não é gameplay:
registre hash do checkpoint, repetição, terminação, loss disponível e
resultados funcionais separadamente. A comparação V2 só é possível se o
checkpoint e sua arquitetura autorizados forem selecionados localmente; pesos
não são copiados ou incluídos no repositório.

## Limite da evidência

Uma redução de loss nos próprios exemplos diagnostica aprendizado da
distribuição vista; não demonstra generalização. Sintaxe válida não prova
funcionalidade. A promoção permanece bloqueada até resultados reproduzíveis em
projetos/famílias reservados, sintaxe, casos funcionais executados em isolamento
e revisão de regressões. O treinamento inicial pode não produzir nenhuma
solução útil; o relatório deve registrar falhas em vez de substituir a saída do
modelo por templates humanos.
