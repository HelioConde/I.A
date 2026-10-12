# Luna — comparação local Qwen3-0.6B vs Qwen3-4B (Q8_0)

## Instalar, selecionar e iniciar o Qwen3-4B com um comando

Existe agora um iniciador Windows que une download, verificação SHA-256,
preflight do CPU runtime, atualização localizada do `LUNA.ini` e abertura da Luna.

Feche qualquer sessão anterior da Luna e execute **no PowerShell**:

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
git pull --ff-only origin feat/ssd-weight-streaming-lab
.\INSTALAR-QWEN4B-LUNA.bat
```

Na primeira execução, baixa o GGUF oficial Q8_0 (~4,28 GB) por HTTPS,
exigindo ao menos 6 GiB livres no SSD. Se o arquivo já estiver presente,
confere sua assinatura e SHA-256; **não sobrescreve arquivos existentes**.
O download só começa após executar explicitamente o comando. Se o download
ou a verificação falhar, não altera o `LUNA.ini`. O modelo 0.6B permanece disponível.

Após download, o comando confirma que o runtime CPU está instalado antes
de ativar `model_file = Qwen3-4B-Q8_0.gguf`, `profile = equilibrado`,
`core_mode = auto`, preservando todas as outras permissões e caminhos
do `LUNA.ini`. Isso **não** comprova ainda a qualidade/velocidade da
inferência real do Qwen3-4B; esse teste acontece quando a Luna iniciar.

Também é possível executar as etapas separadamente:

```powershell
py -3 .\tools\usar_qwen4b_luna.py --status
py -3 .\tools\usar_qwen4b_luna.py --install-activate
.\INICIAR-COPILOTO-WINDOWS.bat
```

Para reverter para o Qwen3-0.6B **sem apagar os pesos do 4B**:

```powershell
py -3 .\tools\usar_qwen4b_luna.py --restore-06b
.\INICIAR-COPILOTO-WINDOWS.bat
```

Teste offline das alterações do INI (não baixa o modelo):

```powershell
py -3 -m unittest discover -s tests -p "test_usar_qwen4b_luna.py" -v
```

**Importante sobre voz:** o Qwen3-4B é o **modelo de texto** que responde
às perguntas. Ele não contém motor de reconhecimento de microfone nem
gerador de áudio. O modo ligação existente ainda usa STT local via navegador
e TTS local do navegador; mudar Qwen pode aumentar a demora entre
pergunta e resposta em computadores com CPU limitada.

---
## Objetivo

Testar um Qwen maior na mesma instalação Windows, sem desinstalar, diminuir a
quantização ou substituir os pesos do Qwen3-0.6B-Q8_0 existente. Os dois
arquivos são Q8_0 e usam o backend local do Brain-SSD.

**Importante:** 4B tem mais parâmetros, mas NÃO é automaticamente melhor em
todas as tarefas, e é esperado que seja mais lento em CPU. Particularmente
no modo de ligação, a demora entre escutar e falar pode aumentar.

Arquivo oficial do candidato: Qwen/Qwen3-4B-GGUF, revisão
`bc640142c66e1fdd12af0bd68f40445458f3869b`;
nome `Qwen3-4B-Q8_0.gguf`, aproximadamente 4,28 GB.
SHA-256 oficial:
`8c2f07f26af9747e41988551106f149b03eb9b5cb6df636027b6bf6278473300`.

Origem: https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/main/Qwen3-4B-Q8_0.gguf

## Uso no PowerShell

Na raiz do projeto atualizado:

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
git pull --ff-only origin feat/ssd-weight-streaming-lab
py -3 .\tools\test_luna_models.py
```

Sem flags, o comando consulta **somente arquivos locais**; não inicia o
Qwen nem faz solicitações à Internet.

### Download opcional, com consentimento explícito

```powershell
py -3 .\tools\test_luna_models.py --download
```

Este comando solicita um único modelo oficial de ~4,28 GB via HTTPS,
em `models/Qwen3-4B-Q8_0.gguf`. Requer pelo menos 6 GiB livres em disco.
O arquivo é recebido primeiro com nome `.download-incomplete`, e só recebe
o nome definitivo após conferir SHA-256, tamanho e assinatura GGUF.
O GGUF do 0.6B não é modificado. Se o destino já existir, o comando recusa
sobrescrever. Downloads incompletos precisam ser resolvidos manualmente.

Também é possível baixar manualmente o GGUF pela página oficial e salvá-lo
como `models/Qwen3-4B-Q8_0.gguf`. O comparador valida o hash antes do teste.

### Comparar de verdade

```powershell
py -3 .\tools\test_luna_models.py --compare --profile equilibrado
```

Esse comando exige ambos os modelos instalados, Q8_0 oficial verificado e
um mínimo conservador de 6 GiB de RAM **disponível**. Se houver menos RAM
disponível, feche programas; a flag `--allow-low-ram` só deve ser usada por
quem compreender o risco de paginação e travamento do Windows.

O teste usa `subprocess`, carrega **um modelo por vez**, 4 perguntas fixas
em português, sem web e com até 96 tokens em cada resposta. Salva:

`results/model_comparison/qwen3-ab.json`

Informações registradas: modelo, SHA-256, resposta, duração, tokens/s, TTFT
(se o runtime medir), pico de working set, memória privada e status de
completude. O teste não alega correção automaticamente; as respostas devem
ser comparadas por uma pessoa. O estado do cache de arquivos do Windows
não é controlado; a temperatura do modelo é 0.7, portanto a comparação
não comprova identidade determinística ou ranking estatístico.

Os relatórios ficam somente no disco local e estão no `.gitignore`.

### Ativar o 4B na Luna após comparar

Abra seu `LUNA.ini` (o arquivo privado existente **não** será sobrescrito):

```powershell
notepad .\LUNA.ini
```

Em `[luna]`, configure:

```ini
profile = equilibrado
core_mode = auto
model_file = Qwen3-4B-Q8_0.gguf
```

Salve e reinicie `INICIAR-COPILOTO-WINDOWS.bat`. O iniciador verifica agora
o **modelo selecionado** antes de abrir o Qwen. Não suporta troca de
modelo quente durante uma ligação; encerre a ligação e reinicie o processo.

### Reverter sem perder nada

Em `[luna]`, volte para:

```ini
profile = economia
core_mode =
model_file =
```

Reinicie a Luna. O arquivo do 4B continua instalado, mas não é carregado
e não altera o modelo anterior.

## Limites

- Não é um teste do streaming experimental SSD -> RAM; usa llama.cpp normal.
- Não instala pacotes TTS/STT e não altera o modo de ligação.
- Não usa GPU obrigatória e não executa dois modelos simultaneamente.
- Não mede qualidade humana automaticamente; a experiência de voz depende
  também da latência de STT e TTS do navegador.
- Testar em hardware real no Windows é necessário para conhecer a latência.
