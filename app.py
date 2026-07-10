from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify

from services.cvm import (
    carregar_historico_fundo,
    calcular_variacao_periodo,
    filtrar_periodo
)
from services.nome_fundo import carregar_depara_fundos

app = Flask(__name__)


# carrega uma vez quando o Flask inicia
df_fundos = carregar_depara_fundos()


def formatar_cnpj(cnpj: str) -> str:

    cnpj = (
        cnpj
        .replace(".", "")
        .replace("/", "")
        .replace("-", "")
    )

    return (
        cnpj[:2] + "."
        + cnpj[2:5] + "."
        + cnpj[5:8] + "/"
        + cnpj[8:12] + "-"
        + cnpj[12:]
    )


def obter_ultimo_mes_completo() -> str:

    hoje = datetime.today()

    primeiro_dia_mes_atual = hoje.replace(day=1)

    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

    return ultimo_dia_mes_anterior.strftime("%Y-%m")


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

    termo = request.args.get(
        "busca",
        ""
    )

    if len(termo) < 3:

        return jsonify([])

    resultado = (
        df_fundos[
            df_fundos["DENOM_SOCIAL"]
            .str.contains(
                termo,
                case=False,
                na=False
            )
        ]
        .head(10)
    )

    return jsonify(
        resultado.to_dict(
            orient="records"
        )
    )


@app.post("/api/fundo/variacao")
def variacao_fundo():

    dados = request.get_json()

    cnpj = dados.get("cnpj")
    data_inicial = dados.get("data_inicial")
    data_final = dados.get("data_final")

    if not cnpj or not data_inicial or not data_final:
        return jsonify({
            "erro": "Informe CNPJ, data inicial e data final"
        }), 400

    ultimo_mes_completo = obter_ultimo_mes_completo()

    if data_final > ultimo_mes_completo:
        return jsonify({
            "erro": f"Só é possível consultar até {ultimo_mes_completo} (último mês fechado)"
        }), 400

    cnpj = formatar_cnpj(cnpj)

    df = carregar_historico_fundo(
        cnpj,
        data_inicial,
        data_final
    )

    variacao = calcular_variacao_periodo(df)

    return jsonify({
        "cnpj": cnpj,
        "data_inicial": data_inicial,
        "data_final": data_final,
        "variacao_percentual": round(variacao, 2)
    })


@app.post("/api/fundos/comparar")
def comparar_fundos():

    dados = request.get_json()

    fundos = dados.get("fundos")
    periodos = dados.get("periodos")

    if not fundos:
        return jsonify({
            "erro": "Adicione ao menos um fundo"
        }), 400

    if not periodos:
        return jsonify({
            "erro": "Adicione ao menos um período"
        }), 400

    ultimo_mes_completo = obter_ultimo_mes_completo()

    for periodo in periodos:

        if not periodo.get("data_inicial") or not periodo.get("data_final"):
            return jsonify({
                "erro": "Preencha todas as datas dos períodos"
            }), 400

        if periodo["data_final"] > ultimo_mes_completo:
            return jsonify({
                "erro": f"Só é possível consultar até {ultimo_mes_completo} (último mês fechado)"
            }), 400

    # baixa/lê do cache o intervalo geral uma única vez por fundo,
    # e depois recorta cada período dentro dele
    data_inicial_geral = min(p["data_inicial"] for p in periodos)
    data_final_geral = max(p["data_final"] for p in periodos)

    resultado_fundos = []

    for fundo in fundos:

        cnpj = fundo.get("cnpj")
        nome = fundo.get("nome", cnpj)

        if not cnpj:
            continue

        cnpj_formatado = formatar_cnpj(cnpj)

        df = carregar_historico_fundo(
            cnpj_formatado,
            data_inicial_geral,
            data_final_geral
        )

        variacoes = []

        for periodo in periodos:

            df_periodo = filtrar_periodo(
                df,
                periodo["data_inicial"],
                periodo["data_final"]
            )

            variacao = calcular_variacao_periodo(df_periodo)

            variacoes.append({
                "data_inicial": periodo["data_inicial"],
                "data_final": periodo["data_final"],
                "variacao_percentual": round(variacao, 2)
            })

        resultado_fundos.append({
            "cnpj": cnpj_formatado,
            "nome": nome,
            "variacoes": variacoes
        })

    return jsonify({
        "periodos": periodos,
        "fundos": resultado_fundos
    })


if __name__ == "__main__":
    app.run(
        debug=True,
        threaded=True
    )