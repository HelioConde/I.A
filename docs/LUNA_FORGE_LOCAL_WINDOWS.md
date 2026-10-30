# Luna Forge Zero — instalação local no Windows 11

**Atualizado em 28/10/2026:** os arquivos `INSTALAR-LUNA-FORGE.cmd`, `INSTALAR-LUNA-FORGE-WINDOWS.ps1`, `ABRIR-LUNA-FORGE.cmd` e `luna_local.py` já estão nesta branch GitHub. **Não é necessário baixar ou extrair qualquer ZIP.**

## Instalar preservando seu Brain-SSD atual

O erro `destination path already exists` indica que a pasta `Luna-Forge-Lab` já contém arquivos. Não a apague nem use `git clean` ou `reset --hard`. Abra PowerShell e execute:

```powershell
$base = Join-Path $env:USERPROFILE "Documents\Luna-Forge-Local"
$destino = $base
$n = 2
while (Test-Path -LiteralPath $destino) {
    $destino = "$base-$n"
    $n++
}
git clone --depth 1 --single-branch --branch feature/luna-forge-zero https://github.com/HelioConde/I.A.git "$destino"
if ($LASTEXITCODE -ne 0) { throw "O clone falhou; nada foi instalado." }
& "$destino\experiments\luna-forge-zero\INSTALAR-LUNA-FORGE.cmd"
```

O destino sempre será uma pasta nova; `C:\Users\helio\Documents\I.A` e a pasta `Luna-Forge-Lab` existente permanecem intactos.

## Abrir

```powershell
& "$destino\experiments\luna-forge-zero\ABRIR-LUNA-FORGE.cmd"
```

Caso abra um novo terminal e a variável `$destino` não esteja definida, use o Explorador e dê dois cliques no CMD da pasta clonada.

## Modos opcionais

Preparar dependências sem treinar os modelos iniciais:

```powershell
& "$destino\experiments\luna-forge-zero\INSTALAR-LUNA-FORGE.cmd" -SkipInitialTraining
```

Treinar um **novo candidato separado** usando apenas código externo MIT previamente aprovado e currículo original:

```powershell
& "$destino\experiments\luna-forge-zero\INSTALAR-LUNA-FORGE.cmd" -SkipInitialTraining -TrainGithub
```

O instalador cria uma `.venv` Python isolada, instala PyTorch CPU e psutil, treina os modelos iniciais quando solicitado, e cria páginas locais de conhecimento via `brain_ssd.storage`. Os checkpoints e datasets ficam em `experiments/luna-forge-zero/checkpoints` e `external_data`, ignorados pelo Git.

**Não são acessados, extraídos, enviados nem modificados** os arquivos em `C:\Users\helio\Documents\grand chase files`. Não há instalação global do Python, mudança na política global do PowerShell ou substituição automática da IA Brain-SSD atual.

## Caso dê erro

- Instale Python 3.12 x64 (o instalador aceita 3.10 a 3.13), Git e acesso à internet.
- O `.cmd` chama PowerShell com `-ExecutionPolicy Bypass` apenas naquele processo; nenhuma alteração global é feita.
- Se falhar na instalação do PyTorch, copie a mensagem de erro do terminal para análise.
- O MiniCoder V0 continua experimental e falhou em 5/5 testes de sintaxe JavaScript. Não execute código gerado sem validação e não confunda redução de loss com criação autônoma de jogos.


## Inspecionar arquivos Grand Chase existentes sem os copiar

**Novo menu 5:** "Inventariar pasta local (somente metadados; sem treinar)". A pasta padrao e:
`C:\Users\helio\Documents\grand chase files`.

Esse comando funciona mesmo sem pesos de modelo, porque usa apenas a biblioteca padrao Python:

```powershell
$pasta = "$env:USERPROFILE\Documents\Luna-Forge-Local\experiments\luna-forge-zero"
git -C "$env:USERPROFILE\Documents\Luna-Forge-Local" pull --ff-only
& "$pasta\.venv\Scripts\python.exe" "$pasta\inventory_local_data.py" "$env:USERPROFILE\Documents\grand chase files"
```

Se o clone estiver em outra pasta (por exemplo `Luna-Forge-Local-2`), ajuste o prefixo da variavel `$pasta`.

- A ferramenta percorre apenas os metadados do diretorio (nome/extensao/tamanho); nao abre nenhum arquivo nem calcula SHA dos conteudos.
- Nunca executa executaveis, extrai archives `.rar`/`.7z`, abre `.bak` de banco nem ingere arquivos `.kom`.
- Salva um relatorio em `reports/local_data_inventory.json` contendo **apenas agregados** por extensao/categoria, sem nomes de arquivos ou caminhos sensiveis.
- Nao envia dados e nao treina. Nao substitui o processo independente de revisao de licencas e autorizacao de uso.

`client.rar`, `s1-client-br-2008-03-04.7z`, `Account.bak`, `Game01.bak`, `ES_BILLING.bak`, `Statistics.bak`, `grandchase.exe` e `main.exe` nao sao considerados exemplos aprovados para treinar GameCoder.


## Resultado de uma instalação real no Windows — 28/10/2026

Registro local fornecido pelo usuário: instalação isolada em `C:\Users\helio\Documents\Luna-Forge-Local`, PyTorch CPU instalado, Planner treinado (4.500 prompts sintéticos), MiniCoder V0 treinado (350 passos), 4 páginas Brain-SSD criadas. O primeiro comando `sim` em minúsculas foi recusado porque o menu exigia `SIM`; o usuário repetiu em maiúsculas e a opção 4 treinou com sucesso um novo candidato em `external_data/local-candidate-20261028-163736-598275`.

Resultados informados pelo treinamento local:
- Corpus externo 25 arquivos MIT, dos quais 19 no treino e 6 no repositório holdout; 8 lições originais JS/GDScript e 6 lições originais Lua, sem scripts do cliente comercial.
- 180 passos, MiniCoder 116.480 parâmetros, perda holdout 35,617650 → 3,304493, 0/5 gerações JavaScript sintaticamente válidas.
- Candidato guardado isoladamente. **O menu antigo (opção 3) ainda carregava o checkpoint inicial**, não o recém-treinado.
- Avisos não fatais: NumPy ausente; conversão de tensor com gradiente para escalar.

Correções publicadas:
- A instalação da `.venv` agora inclui NumPy. Em uma instalação **já existente**, execute uma vez (não apaga modelos):

```powershell
$lab="$env:USERPROFILE\Documents\Luna-Forge-Local\experiments\luna-forge-zero"
& "$lab\.venv\Scripts\python.exe" -m pip install "numpy>=1.26,<3"
```

- A conversão de perda usa `loss.detach().item()`, evitando aviso relacionado ao autograd.
- Menu 4 aceita `sim`, `SIM` e variações de maiúsculas/minúsculas (ainda exige confirmação).
- **Menu 8 — testar candidato local mais recente**: somente visualização da geração, sem executar o código gerado ou promovê-lo para o modelo ativo. Faz verificação SHA-256 antes do carregamento e escolhe somente arquivos `local-candidate-*` dentro de `external_data`. O menu 3 permanece como teste do MiniCoder inicial, explicitamente identificado.

Após `git pull --ff-only`, execute `ABRIR-LUNA-FORGE.cmd` e escolha **8**. A qualidade do MiniCoder ainda não é suficiente para produzir jogos; a opção serve apenas como um teste honesto do checkpoint local.
