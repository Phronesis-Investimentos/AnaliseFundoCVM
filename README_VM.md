# Execução na VM Windows

## Preparação única

Na pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O comando de instalação é executado apenas na preparação ou quando as dependências forem atualizadas, não a cada inicialização.

## Inicialização manual

Com o ambiente virtual preparado, qualquer uma destas opções inicia o Waitress na porta `6767`:

```powershell
.\.venv\Scripts\python.exe app.py
```

```powershell
.\start_production.ps1
```

O script pode ser executado a partir de qualquer diretório. Para outra porta, defina `PORT` antes de iniciar; sem essa variável, a porta é `6767`.

## Serviço do Windows via NSSM

O serviço é gerenciado pelo Windows, como o Hub Phronesis. Baixe o NSSM e deixe `nssm.exe` em um destes caminhos:

```text
C:\nssm\nssm-2.24\win64\nssm.exe
C:\nssm\nssm\nssm-2.24\win64\nssm.exe
```

Em um PowerShell **como Administrador**, na pasta do projeto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_windows_service.ps1
```

O instalador configura inicialização automática no boot, reinício pelo NSSM, logs em `logs\` e Waitress em `0.0.0.0:6767`.

Comandos de operação, também em PowerShell **como Administrador**:

```powershell
Get-Service AnaliseFundoCVM
Stop-Service AnaliseFundoCVM
Start-Service AnaliseFundoCVM
Restart-Service AnaliseFundoCVM
Get-Content .\logs\analise_fundo_cvm_stdout.log -Wait -Tail 50
```

Após atualizar o código:

```powershell
Stop-Service AnaliseFundoCVM
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Start-Service AnaliseFundoCVM
```

Não use `git reset --hard` se houver alterações locais.

## Acesso pela internet

URL de acesso: `http://IP_DA_VM:6767`

O Waitress escuta em todas as interfaces da VM. Além do serviço, libere a porta TCP `6767` no firewall do Windows e no firewall/NAT externo da rede ou provedor da VM, se necessário.
