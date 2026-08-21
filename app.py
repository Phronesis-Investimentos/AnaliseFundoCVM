import os
import threading

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from waitress import serve

from services.nome_fundo import carregar_depara_fundos
from services.fundos_service import (
    processar_variacao_fundo,
    processar_comparacao_fundos,
    gerar_ranking_fundos,
    calcular_volatilidade_ranking_fundo,
)
from services.exportacao_service import (
    iniciar_exportacao_ranking,
    obter_status_exportacao,
    obter_arquivo_exportacao,
)
from services.portfolio import portfolio as calcular_portfolio
from services.cvm import listar_subclasses_fundo, normalizar_id_subclasse
from services.exportacao_portfolio import gerar_excel_portfolio
from services.carteira_service import (
    salvar_carteira,
    listar_carteiras,
    obter_carteira,
    excluir_carteira,
)
from utils.validacoes import (
    validar_dados_variacao,
    validar_dados_comparacao,
    gerar_todos_periodos,
    obter_ultimo_mes_completo,
    obter_data_referencia,
)

app = Flask(__name__)

# O servidor deve iniciar mesmo se o cadastro da CVM estiver lento ou fora do ar.
# A lista é preenchida em segundo plano e cada requisição passa a usar o cadastro
# assim que o carregamento terminar.
df_fundos = pd.DataFrame(columns=["CNPJ_FUNDO", "DENOM_SOCIAL"])


def _carregar_fundos_em_segundo_plano():
    global df_fundos
    cadastro = carregar_depara_fundos()
    if not cadastro.empty:
        df_fundos = cadastro
        print(f"Cadastro de classes pronto: {len(df_fundos)} fundos.")


threading.Thread(target=_carregar_fundos_em_segundo_plano, daemon=True).start()

# Chaves dos 5 períodos usados no ranking (mesmas do fundos_service)
CHAVES_PERIODOS_RANKING = ["12m", "24m", "36m", "48m", "60m"]


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/comparar")
def comparar():
    return render_template("comparar.html")


@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")


@app.route("/api/fundos")
def listar_fundos():
    fundos = (
        df_fundos
        .sort_values("DENOM_SOCIAL")
        .to_dict(orient="records")
    )
    return jsonify(fundos)


@app.route("/api/fundos/buscar")
def buscar_fundos():
    termo = request.args.get("busca", "").strip()

    if len(termo) < 3:
        return jsonify([])

    # Permite buscar tanto pelo nome do fundo quanto pelo CNPJ
    # (com ou sem pontuação, ex: "15834698000118" ou "15.834.698/0001-18").
    filtro_nome = df_fundos["DENOM_SOCIAL"].str.contains(termo, case=False, na=False)

    cnpj_normalizado = df_fundos["CNPJ_FUNDO"].astype(str).str.replace(
        r"[./-]", "", regex=True
    )
    termo_cnpj = termo.replace(".", "").replace("/", "").replace("-", "")
    filtro_cnpj = cnpj_normalizado.str.contains(termo_cnpj, na=False)

    resultado = df_fundos[filtro_nome | filtro_cnpj].head(10)

    return jsonify(resultado.to_dict(orient="records"))


@app.get("/api/fundos/subclasses")
def listar_subclasses():
    """Informa as subclasses disponíveis para a seleção dinâmica da tela."""
    cnpj = request.args.get("cnpj", "").strip()
    if not cnpj:
        return jsonify({"erro": "Informe o parâmetro cnpj"}), 400
    try:
        return jsonify({"cnpj": cnpj, "subclasses": listar_subclasses_fundo(cnpj)})
    except (ValueError, TypeError) as erro:
        return jsonify({"erro": str(erro)}), 400


@app.route("/api/periodos/padrao")
def periodos_padrao():
    """
    Retorna os períodos padrão para análise.
    Inclui os períodos de 12m, 24m, 36m, 48m, 60m E "Desde o Início"
    """
    data_referencia = request.args.get("data_referencia")
    
    # Agora retorna TODOS os períodos, incluindo "Desde o Início"
    periodos = gerar_todos_periodos(data_referencia)
    
    return jsonify(periodos)

@app.post("/api/fundo/variacao")
def variacao_fundo():
    dados = request.get_json()
    
    # Validação
    valido, erro = validar_dados_variacao(dados)
    if not valido:
        return jsonify({"erro": erro}), 400
    
    # Processamento
    resultado = processar_variacao_fundo(
        cnpj=dados["cnpj"],
        data_inicial=dados["data_inicial"],
        data_final=dados["data_final"]
    )
    
    return jsonify(resultado)


@app.post("/api/fundos/comparar")
def comparar_fundos():
    dados = request.get_json()
    
    # Validação
    valido, erro = validar_dados_comparacao(dados)
    if not valido:
        return jsonify({"erro": erro}), 400

    for fundo in dados["fundos"]:
        cnpj = str(fundo.get("cnpj", "")).strip()
        id_subclasse = normalizar_id_subclasse(fundo.get("id_subclasse"))
        disponiveis = listar_subclasses_fundo(cnpj)
        if disponiveis and id_subclasse is None:
            return jsonify({"erro": f"Selecione uma subclasse para o fundo {cnpj}"}), 400
        if id_subclasse is not None and id_subclasse not in disponiveis:
            return jsonify({"erro": f"Subclasse inválida para o fundo {cnpj}"}), 400
        fundo["id_subclasse"] = id_subclasse
    
    # Processamento
    resultado = processar_comparacao_fundos(
        fundos=dados["fundos"],
        periodos=dados["periodos"]
    )
    
    return jsonify(resultado)


@app.get("/api/fundos/ranking")
def ranking_fundos():
    """Retorna os melhores fundos com base nos cinco períodos padrão.

    Aceita pesos customizados por período via query string (em percentual,
    0-100): peso_12m, peso_24m, peso_36m, peso_48m, peso_60m. Se nenhum for
    informado, o serviço usa os pesos padrão (10/15/50/15/10).
    """
    try:
        top_n = int(request.args.get("top_n", 50))
    except ValueError:
        return jsonify({"erro": "top_n deve ser um número inteiro"}), 400

    if top_n < 1:
        return jsonify({"erro": "top_n deve ser maior que zero"}), 400

    categoria = request.args.get("categoria", "todos")

    # Se o usuário informou pelo menos um peso, monta o dicionário completo.
    # A validação de que a soma dá 100% (1.0) é feita dentro do
    # gerar_ranking_fundos, que já lança ValueError se não bater.
    pesos = None
    if any(f"peso_{chave}" in request.args for chave in CHAVES_PERIODOS_RANKING):
        try:
            pesos = {
                chave: float(request.args.get(f"peso_{chave}", 0)) / 100
                for chave in CHAVES_PERIODOS_RANKING
            }
        except ValueError:
            return jsonify({"erro": "Os pesos devem ser números"}), 400

    data_referencia = request.args.get("data_referencia")
    try:
        ranking = gerar_ranking_fundos(
            fundos=df_fundos,
            top_n=top_n,
            data_referencia=data_referencia,
            categoria=categoria,
            pesos=pesos,
        )
    except (ValueError, TypeError) as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify({
        "data_referencia": data_referencia or obter_data_referencia().strftime("%Y-%m-%d"),
        "categoria": categoria,
        "pesos": (
            {chave: round(valor * 100, 2) for chave, valor in pesos.items()}
            if pesos else None
        ),
        "fundos": ranking,
    })


@app.get("/api/fundo/volatilidade-ranking")
def volatilidade_ranking_fundo():
    """Calcula a volatilidade de um fundo específico nos cinco períodos do ranking.

    Chamada sob demanda pelo botão "Ver Volatilidade" de cada linha do
    ranking, para não pesar o cálculo do ranking geral (que não precisa da
    série diária completa).
    """
    cnpj = request.args.get("cnpj")
    if not cnpj:
        return jsonify({"erro": "Informe o parâmetro cnpj"}), 400

    data_referencia = request.args.get("data_referencia")
    try:
        resultado = calcular_volatilidade_ranking_fundo(
            cnpj=cnpj,
            data_referencia=data_referencia,
        )
    except (ValueError, TypeError) as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify(resultado)


@app.post("/api/portfolio/gerar")
def gerar_portfolio():
    """Calcula rentabilidade, volatilidade (36m) e correlação para o
    conjunto de fundos selecionado na tela de Portfólio.

    Espera um JSON com:
    { "fundos": ["<cnpj1>", "<cnpj2>", ...], "data_referencia": "YYYY-MM-DD" }

    "data_referencia" é opcional (usa hoje se não vier). Os 756 pregões
    são contados para trás a partir dela; se a data cair num dia não
    útil, o cálculo cai automaticamente para o último pregão disponível
    anterior.
    """
    dados = request.get_json(silent=True) or {}
    fundos_recebidos = dados.get("fundos")
    data_referencia = dados.get("data_referencia")
    # Opcional: { "<cnpj>": peso_percentual (0-100), ... } — vindo dos
    # inputs de peso da tela. Convertemos para fração (0-1) aqui.
    pesos_recebidos = dados.get("pesos")

    if not fundos_recebidos:
        return jsonify({"erro": "Nenhum fundo informado"}), 400

    # Aceita a lista antiga de CNPJs e o novo formato por fundo:
    # {cnpj: "...", id_subclasse: "..."}. O ID é validado no servidor
    # para impedir que uma requisição calcule uma combinação inexistente.
    cnpjs = []
    subclasses = {}
    for fundo in fundos_recebidos:
        if isinstance(fundo, dict):
            cnpj = str(fundo.get("cnpj", "")).strip()
            id_subclasse = normalizar_id_subclasse(fundo.get("id_subclasse"))
        else:
            cnpj = str(fundo).strip()
            id_subclasse = None
        if not cnpj or cnpj in cnpjs:
            continue
        disponiveis = listar_subclasses_fundo(cnpj)
        if disponiveis and id_subclasse is None:
            return jsonify({"erro": f"Selecione uma subclasse para o fundo {cnpj}"}), 400
        if id_subclasse is not None and id_subclasse not in disponiveis:
            return jsonify({"erro": f"Subclasse inválida para o fundo {cnpj}"}), 400
        cnpjs.append(cnpj)
        subclasses[cnpj] = id_subclasse

    if data_referencia:
        try:
            pd.Timestamp(data_referencia)
        except (ValueError, TypeError):
            return jsonify({"erro": "data_referencia inválida"}), 400

    pesos = None
    if pesos_recebidos:
        try:
            pesos = {
                str(cnpj): float(peso) / 100
                for cnpj, peso in pesos_recebidos.items()
            }
        except (TypeError, ValueError):
            return jsonify({"erro": "Os pesos devem ser números"}), 400

    fundos_selecionados = df_fundos[df_fundos["CNPJ_FUNDO"].isin(cnpjs)].copy()
    # Carteiras antigas podem conter fundos que já não aparecem no cadastro
    # corrente da CVM. O histórico continua sendo a fonte dos cálculos, então
    # não descarte esses CNPJs apenas por não haver um nome atualizado.
    encontrados = set(fundos_selecionados["CNPJ_FUNDO"])
    ausentes = [cnpj for cnpj in cnpjs if cnpj not in encontrados]
    if ausentes:
        fundos_selecionados = pd.concat([
            fundos_selecionados,
            pd.DataFrame({"CNPJ_FUNDO": ausentes, "DENOM_SOCIAL": ausentes}),
        ], ignore_index=True)

    resultado, correlacao, covariancia = calcular_portfolio(
        fundos_selecionados,
        pesos=pesos,
        data_referencia=data_referencia,
        subclasses=subclasses,
    )

    if resultado.empty:
        return jsonify({
            "fundos": [],
            "correlacao": {},
            "covariancia": {},
        })

    # Junta o nome do fundo ao resultado (o service só trabalha com CNPJ)
    resultado = resultado.merge(
        fundos_selecionados[["CNPJ_FUNDO", "DENOM_SOCIAL"]].drop_duplicates("CNPJ_FUNDO"),
        on="CNPJ_FUNDO",
        how="left",
    )

    fundos_json = [
        {
            "cnpj": linha["CNPJ_FUNDO"],
            "nome": linha["DENOM_SOCIAL"],
            "id_subclasse": subclasses.get(linha["CNPJ_FUNDO"]),
            "rentabilidade_36m": round(linha["RENTABILIDADE"], 2),
            "volatilidade_36m": round(linha["VOLATILIDADE"], 2),
            "risco_atribuido": (
                round(linha["RISCO_ATRIBUIDO"], 2)
                if pd.notnull(linha.get("RISCO_ATRIBUIDO"))
                else None
            ),
            "attribution": (
                round(linha["ATTRIBUTION"], 2)
                if pd.notnull(linha.get("ATTRIBUTION"))
                else None
            ),
            "attribution_por_risco": (
                round(linha["ATTRIBUTION_POR_RISCO"], 4)
                if pd.notnull(linha.get("ATTRIBUTION_POR_RISCO"))
                else None
            ),
        }
        for _, linha in resultado.iterrows()
    ]

    # Matriz de correlação -> dict serializável { cnpj: { cnpj: valor } }
    correlacao_json = (
        # A interface exibe duas casas, mas mantém precisão maior no payload
        # para a covariância exportada não ser reduzida a zero.
        correlacao.round(10).where(pd.notnull(correlacao), None).to_dict()
        if not correlacao.empty else {}
    )

    # Matriz de covariância (correlação x volatilidade x peso de cada par)
    covariancia_json = (
        covariancia.where(pd.notnull(covariancia), None).to_dict()
        if not covariancia.empty else {}
    )

    return jsonify({
        "fundos": fundos_json,
        "correlacao": correlacao_json,
        "covariancia": covariancia_json,
    })


@app.get("/api/carteiras")
def listar_carteiras_salvas():
    """Lista as carteiras salvas (nome, quantidade de fundos, última
    atualização) — usado para montar a lista de "Minhas Carteiras" na
    tela de Portfólio. Não retorna os CNPJs (ver /api/carteiras/<nome>
    para isso)."""
    return jsonify(listar_carteiras())


@app.post("/api/carteiras")
def salvar_carteira_route():
    """Salva (ou sobrescreve, se já existir uma com o mesmo nome) uma
    carteira: um nome escolhido pelo usuário apontando para a lista de
    CNPJs selecionados na tela naquele momento.

    Espera um JSON com:
    { "nome": "Carteira XP", "fundos": ["<cnpj1>", "<cnpj2>", ...] }
    """
    dados = request.get_json(silent=True) or {}

    try:
        carteira = salvar_carteira(dados.get("nome", ""), dados.get("fundos") or [])
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify(carteira)


@app.get("/api/carteiras/<nome>")
def obter_carteira_route(nome):
    """Retorna os CNPJs salvos de uma carteira pelo nome exato. O
    front-end usa isso pra popular os fundos selecionados e então chama
    /api/portfolio/gerar sem `data_referencia` (usa hoje), trazendo
    sempre as informações mais recentes daquela carteira."""
    carteira = obter_carteira(nome)
    if carteira is None:
        return jsonify({"erro": "Carteira não encontrada"}), 404

    return jsonify(carteira)


@app.delete("/api/carteiras/<nome>")
def excluir_carteira_route(nome):
    """Remove uma carteira salva pelo nome exato."""
    removida = excluir_carteira(nome)
    if not removida:
        return jsonify({"erro": "Carteira não encontrada"}), 404

    return jsonify({"ok": True})


@app.post("/api/portfolio/exportar")
def exportar_portfolio_excel():
    """Gera e devolve um .xlsx com a composição do portfólio (CNPJ, nome,
    rentabilidade, volatilidade, peso) e, em outra aba, a matriz de
    correlação — usando exatamente os dados/pesos que estão na tela no
    momento do clique (evita reprocessar e ficar diferente do que o
    usuário está vendo, principalmente os pesos editados manualmente).

    Espera um JSON com:
    {
      "fundos": [{ "cnpj", "nome", "rentabilidade_36m", "volatilidade_36m", "peso" }, ...],
      "correlacao": { "<cnpj>": { "<cnpj>": valor, ... }, ... },
      "covariancia": { "<cnpj>": { "<cnpj>": valor, ... }, ... },
      "data_referencia": "YYYY-MM-DD"
    }
    """
    dados = request.get_json(silent=True) or {}
    fundos = dados.get("fundos")

    if not fundos:
        return jsonify({"erro": "Nenhum fundo informado para exportação"}), 400

    buffer = gerar_excel_portfolio(
        fundos=fundos,
        correlacao=dados.get("correlacao"),
        covariancia=dados.get("covariancia"),
        data_referencia=dados.get("data_referencia"),
    )

    data_arquivo = dados.get("data_referencia") or obter_data_referencia().strftime("%Y-%m-%d")
    nome_arquivo = f"portfolio_{data_arquivo}.xlsx"

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nome_arquivo,
    )


@app.post("/api/fundos/ranking/exportar/iniciar")
def iniciar_exportacao_ranking_excel():
    """
    Inicia a exportação do ranking para Excel em background e retorna um
    job_id. O front-end usa esse job_id para consultar o progresso em
    /status/<job_id> e baixar o arquivo em /download/<job_id> quando
    concluído.
    """
    dados = request.get_json(silent=True) or {}
    fundos = dados.get("fundos")

    if not fundos:
        return jsonify({"erro": "Nenhum fundo informado para exportação"}), 400

    try:
        job_id = iniciar_exportacao_ranking(
            fundos,
            data_referencia=dados.get("data_referencia"),
            categoria=dados.get("categoria"),
        )
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    return jsonify({"job_id": job_id, "total": len(fundos)})


@app.get("/api/fundos/ranking/exportar/status/<job_id>")
def status_exportacao_ranking_excel(job_id):
    """Retorna o progresso atual de um job de exportação (para polling)."""
    status = obter_status_exportacao(job_id)
    if status is None:
        return jsonify({"erro": "Exportação não encontrada"}), 404

    return jsonify(status)


@app.get("/api/fundos/ranking/exportar/download/<job_id>")
def download_exportacao_ranking_excel(job_id):
    """Entrega o arquivo .xlsx de um job já concluído."""
    buffer, nome_arquivo = obter_arquivo_exportacao(job_id)
    if buffer is None:
        return jsonify({"erro": "Arquivo não disponível ou ainda não concluído"}), 404

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nome_arquivo,
    )


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", "6767")))
