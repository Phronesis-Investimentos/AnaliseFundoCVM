$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    Write-Error "Ambiente virtual não encontrado em '$projectRoot\.venv'. Crie-o com 'py -m venv .venv' e consulte README_VM.md para preparar as dependências."
    exit 1
}

$port = if ([string]::IsNullOrWhiteSpace($env:PORT)) { "6767" } else { $env:PORT }

Write-Host "Iniciando AnaliseFundoCVM com Waitress em 0.0.0.0:$port"
& $venvPython -m waitress --listen="0.0.0.0:$port" app:app
exit $LASTEXITCODE
