from flask import Flask, render_template, request, jsonify

from services.nome_fundo import carregar_depara_fundos
from services.fundos_service import (
    processar_variacao_fundo,
    processar_comparacao_fundos
)
from utils.validacoes import (
    validar_dados_variacao,
    validar_dados_comparacao,
    gerar_todos_periodos,
    obter_ultimo_mes_completo
)

app = Flask(__name__)

# Carrega uma vez quando o Flask inicia
df_fundos = carregar_depara_fundos()


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


if __name__ == "__main__":
    app.run(debug=True, threaded=True)