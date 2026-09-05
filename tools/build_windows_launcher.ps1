param(
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcherProject = Join-Path $projectRoot "launcher\BrainSSD.Launcher\BrainSSD.Launcher.csproj"
$outputDirectory = Join-Path $projectRoot "dist\windows"

dotnet publish $launcherProject `
    --configuration Release `
    --runtime $Runtime `
    --self-contained false `
    -p:PublishSingleFile=true `
    -p:DebugType=None `
    -p:DebugSymbols=false `
    --output $outputDirectory

$executable = Join-Path $outputDirectory "BrainSSD.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Launcher build finished without BrainSSD-HUD.exe"
}
Write-Host "Launcher criado: $executable"
