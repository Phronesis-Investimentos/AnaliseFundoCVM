# Análise de Fundos CVM

Aplicação Flask para pesquisar fundos da CVM, comparar rentabilidade e volatilidade, gerar rankings e montar portfólios com correlação, covariância e exportação para Excel.

## Funcionalidades

- Comparação de fundos em períodos personalizados, incluindo “Desde o Início”.
- Ranking de fundos para 12, 24, 36, 48 e 60 meses.
- Portfólio com rentabilidade, volatilidade, correlação, covariância, *Risk Attribution* e *Attribution*.
- Carteiras salvas em `data/carteiras.json`.
- Exportação de ranking e portfólio para `.xlsx`.
- Cache local dos arquivos diários da CVM em `cache/`.
- Tema claro/escuro.

## Requisitos

- Python 3.10 ou superior
- Acesso à internet na primeira execução, para consultar os dados públicos da CVM

## Instalação e execução

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5000` no navegador.

## Estrutura principal

```text
app.py                         Rotas Flask e integração entre interface e serviços
services/cvm.py                Download, cache e leitura dos históricos da CVM
services/fundos_service.py     Comparação, variação e ranking
services/portfolio.py          Métricas e matrizes do portfólio
services/exportacao_*.py       Geração dos arquivos Excel
services/carteira_service.py   Persistência das carteiras salvas
templates/                     Páginas HTML
static/                        JavaScript e estilos
cache/                         Dados CVM armazenados localmente
data/carteiras.json            Carteiras salvas
```

## APIs principais

| Método | Rota | Finalidade |
| --- | --- | --- |
| `GET` | `/api/fundos/buscar?busca=...` | Pesquisa por nome ou CNPJ |
| `GET` | `/api/fundos/subclasses?cnpj=...` | Lista subclasses disponíveis |
| `POST` | `/api/fundos/comparar` | Compara fundos e períodos |
| `GET` | `/api/fundos/ranking` | Gera ranking |
| `POST` | `/api/portfolio/gerar` | Calcula o portfólio |
| `POST` | `/api/portfolio/exportar` | Exporta o portfólio para Excel |
| `GET/POST` | `/api/carteiras` | Lista ou salva carteiras |



## Fonte dos dados

Os dados são obtidos dos arquivos públicos da [CVM](https://dados.cvm.gov.br/). A disponibilidade e a data mais recente dependem da publicação da própria CVM.
