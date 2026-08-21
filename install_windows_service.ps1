# Instala a AnaliseFundoCVM como servico do Windows usando NSSM.
# Execute este script em um PowerShell como Administrador.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ServiceName = "AnaliseFundoCVM"
$ServiceDesc = "Analise de Fundos CVM - Waitress"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$Host_ = "0.0.0.0"
$Port_ = "6767"

$NssmCandidates = @(
    $env:NSSM_PATH,
    "C:\nssm\nssm-2.24\win64\nssm.exe",
    "C:\nssm\nssm\nssm-2.24\win64\nssm.exe"
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
$NssmPath = $NssmCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  AnaliseFundoCVM - Instalacao como Windows Service" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Error "Execute este script em um PowerShell como Administrador."
    exit 1
}

if (-not $NssmPath) {
    Write-Error "NSSM nao encontrado. Defina NSSM_PATH ou coloque nssm.exe em C:\nssm\nssm-2.24\win64\."
    exit 1
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-Error "Python do ambiente virtual nao encontrado em '$PythonExe'. Execute primeiro: py -m venv .venv e .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path -LiteralPath $LogDir -PathType Container)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Removendo a configuracao anterior de '$ServiceName'..." -ForegroundColor Yellow
    & $NssmPath stop $ServiceName | Out-Null
    & $NssmPath remove $ServiceName confirm | Out-Null
}

Write-Host "Instalando '$ServiceName' com Waitress em $Host_`:$Port_..." -ForegroundColor Cyan
& $NssmPath install $ServiceName $PythonExe "-m" "waitress" "--host=$Host_" "--port=$Port_" "app:app"
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName DisplayName $ServiceName
& $NssmPath set $ServiceName Description $ServiceDesc
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 5000
& $NssmPath set $ServiceName AppStdout (Join-Path $LogDir "analise_fundo_cvm_stdout.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $LogDir "analise_fundo_cvm_stderr.log")
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760

Write-Host "Iniciando servico..." -ForegroundColor Cyan
& $NssmPath start $ServiceName | Out-Null
Start-Sleep -Seconds 3

$service = Get-Service -Name $ServiceName
if ($service.Status -eq "Running") {
    Write-Host "Servico '$ServiceName' em execucao." -ForegroundColor Green
    Write-Host "Acesse: http://IP_PUBLICO_DA_VM:$Port_" -ForegroundColor Green
    Write-Host "Logs: $LogDir" -ForegroundColor Green
} else {
    Write-Error "O servico nao iniciou. Consulte os logs em '$LogDir'."
    exit 1
}
