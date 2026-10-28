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
