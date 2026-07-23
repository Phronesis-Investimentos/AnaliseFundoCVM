from flask import Flask, render_template, request, jsonify, send_file

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
from utils.validacoes import (
    validar_dados_variacao,
    validar_dados_comparacao,
    gerar_todos_periodos,
    obter_ultimo_mes_completo,
    obter_data_referencia,
)

app = Flask(__name__)

# Carrega uma vez quando o Flask inicia
df_fundos = carregar_depara_fundos()

# Chaves dos 5 períodos usados no ranking (mesmas do fundos_service)
CHAVES_PERIODOS_RANKING = ["12m", "24m", "36m", "48m", "60m"]


@app.route("/")
def index():
    return render_template("index.html")


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
    termo = request.args.get("busca", "")
    
    if len(termo) < 3:
        return jsonify([])
    
    resultado = (
        df_fundos[
            df_fundos["DENOM_SOCIAL"]
            .str.contains(termo, case=False, na=False)
        ]
        .head(10)
    )
    
    return jsonify(resultado.to_dict(orient="records"))


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
    app.run(debug=True, threaded=True)