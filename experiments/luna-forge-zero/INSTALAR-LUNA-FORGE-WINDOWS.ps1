# Luna Forge Zero / Brain-SSD — isolated Windows installer
# Does not read or upload personal Grand Chase archives.
[CmdletBinding()]
param([switch]$SkipInitialTraining, [switch]$TrainGithub)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Here = $PSScriptRoot
$Venv = Join-Path $Here ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Checkpoints = Join-Path $Here "checkpoints"

function Run-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha (codigo $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.12", "3.11", "3.13", "3.10")) {
            try {
                & py "-$v" -c 'import sys; assert sys.version_info.major == 3' 2>$null
                if ($LASTEXITCODE -eq 0) { return @{ Cmd="py"; Args=@("-$v") } }
            } catch {}
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            & python -c "import sys; assert (3, 10) <= sys.version_info[:2] <= (3, 13)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Cmd="python"; Args=@() } }
        } catch {}
    }
    throw "Python 3.10-3.13 x64 nao encontrado. Recomendamos Python 3.12."
}

Write-Host ""
Write-Host "==== LUNA FORGE LOCAL (Brain-SSD) ====" -ForegroundColor Cyan
Write-Host "Pasta: $Here"
Write-Host "Instalacao isolada: nao altera Python global, I.A existente ou modelos da Luna principal."
Write-Host "Arquivos pessoais .rar/.7z: NAO acessados."

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $selected = Find-Python
    Write-Host "Criando ambiente virtual em $Venv ..." -ForegroundColor Cyan
    Run-Checked -Executable $selected.Cmd -Arguments ($selected.Args + @("-m","venv",$Venv))
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Ambiente virtual nao foi criado."
}
Write-Host "Instalando PyTorch CPU e psutil na .venv..." -ForegroundColor Cyan
Run-Checked -Executable $Python -Arguments @("-m","pip","install","--disable-pip-version-check","--index-url","https://download.pytorch.org/whl/cpu","torch>=2.1,<3")
Run-Checked -Executable $Python -Arguments @("-m","pip","install","--disable-pip-version-check","psutil","numpy>=1.26,<3")
Run-Checked -Executable $Python -Arguments @("-c",'import torch, psutil; print(torch.__version__); print(torch.cuda.is_available())')

if (-not $SkipInitialTraining) {
    $planner = Join-Path $Checkpoints "luna-forge-zero-v0"
    $coder = Join-Path $Checkpoints "luna-minicoder-zero-v0"
    $pw = Join-Path $planner "weights.pt"
    $pr = Join-Path $planner "report.json"
    $cw = Join-Path $coder "weights.pt"
    $cr = Join-Path $coder "report.json"
    if ((Test-Path $pw) -xor (Test-Path $pr)) { throw "Planner incompleto; conferir checkpoint antes de continuar: $planner" }
    if ((Test-Path $cw) -xor (Test-Path $cr)) { throw "MiniCoder incompleto; conferir checkpoint antes de continuar: $coder" }
    if (-not (Test-Path -LiteralPath $pw)) {
        Write-Host "Treinando o Planner original desde pesos aleatorios..." -ForegroundColor Cyan
        Run-Checked -Executable $Python -Arguments @((Join-Path $Here "train.py"),"--out",$planner,"--train-size","4500","--val-size","300","--test-size","300","--epochs","15","--threads","4")
    } else { Write-Host "Planner existente preservado." }
    if (-not (Test-Path -LiteralPath $cw)) {
        Write-Host "Treinando MiniCoder original desde pesos aleatorios..." -ForegroundColor Cyan
        Run-Checked -Executable $Python -Arguments @((Join-Path $Here "train_codegen.py"),"--out",$coder,"--steps","350","--batch","12","--threads","4")
    } else { Write-Host "MiniCoder existente preservado." }
}

$Knowledge = Join-Path $Here "knowledge_pages"
if (-not (Test-Path -LiteralPath (Join-Path $Knowledge "manifest.json"))) {
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "brain_ssd_bridge.py"),"build-knowledge","--skills",$Knowledge)
}

if ($TrainGithub) {
    Write-Host "Treinamento EXPLICITO com fontes externas MIT, nao com os seus arquivos RAR/7z." -ForegroundColor Yellow
    $Data = Join-Path $Here "external_data"
    $Candidate = Join-Path $Data ("candidate-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "grandchase_reference_gate.py"),"audit")
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "original_lua_lessons.py"),"verify")
    if (-not (Test-Path -LiteralPath (Join-Path $Data "manifest.json"))) {
        Run-Checked -Executable $Python -Arguments @((Join-Path $Here "github_corpus.py"),"collect","--out",$Data)
    }
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "github_corpus.py"),"verify","--out",$Data)
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "train_github.py"),"--data",$Data,"--curriculum",(Join-Path $Here "action_platform_curriculum.json"),"--out",$Candidate,"--steps","180","--batch","12","--threads","4","--lua-lessons")
    Run-Checked -Executable $Python -Arguments @((Join-Path $Here "evaluate_github_codegen.py"),"--checkpoint",$Candidate,"--out",(Join-Path $Candidate "syntax_report.json"))
    Write-Host "Novo checkpoint experimental: $Candidate" -ForegroundColor Green
}
Run-Checked -Executable $Python -Arguments @((Join-Path $Here "brain_ssd_bridge.py"),"status","--checkpoints",$Checkpoints)
Write-Host ""
Write-Host "Instalacao pronta. Use ABRIR-LUNA-FORGE.cmd (menu local)." -ForegroundColor Green
Write-Host "Atencao: MiniCoder V0 ainda nao gera programas de jogos confiaveis."
