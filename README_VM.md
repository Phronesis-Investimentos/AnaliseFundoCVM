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

## Agendador de Tarefas

Crie uma tarefa **Ao iniciar o computador** e configure:

1. Em **Ação**, use `powershell.exe`.
2. Em argumentos, informe `-NoProfile -ExecutionPolicy Bypass -File "C:\caminho\do\projeto\start_production.ps1"`.
3. Marque a execução mesmo sem usuário conectado, se aplicável à VM.
4. Em **Configurações**, habilite **Reiniciar a tarefa se falhar**, por exemplo a cada 1 minuto, com algumas tentativas.
5. Defina **Se a tarefa já estiver em execução** como **Não iniciar uma nova instância**.

URL de acesso: `http://IP_DA_VM:6767`

Se necessário, libere a porta TCP `6767` no firewall da VM e em qualquer firewall de rede aplicável.
