import pandas as pd
from services.volatilidade import calcular_volatilidade_periodo
from services.cvm import carregar_historico_fundos

def carregar_historico_36meses(
    fundos: pd.DataFrame,
    data_referencia: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Carrega os últimos 756 dias disponíveis de cada fundo, a partir de
    uma data de referência.

    Considera como referência a data informada (ou hoje, se não informada)
    e retorna, para cada CNPJ, as 756 observações mais recentes
    disponíveis até essa data.

    Como o filtro é "<= data_referencia" e pegamos os últimos 756
    registros já ordenados, se a data escolhida não for um dia útil
    (fim de semana/feriado) ou o fundo simplesmente não tiver cota
    naquele dia, o próprio filtro já cai automaticamente para a última
    data disponível anterior — não precisa de tratamento extra aqui.

    Parâmetros
    ----------
    fundos : pd.DataFrame
        DataFrame contendo a coluna CNPJ_FUNDO.
    data_referencia : str | pd.Timestamp | None
        Data final da janela de 756 dias (formato "YYYY-MM-DD" se string).
        Se None, usa a data de hoje.

    Retorno
    -------
    pd.DataFrame
        Histórico diário dos fundos, limitado às últimas 756 observações
        de cada CNPJ_FUNDO até a data de referência.
    """

    if fundos.empty:
        return pd.DataFrame(
            columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]
        )

    # CNPJs únicos
    cnpjs = (
        fundos["CNPJ_FUNDO"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    if len(cnpjs) == 0:
        return pd.DataFrame(
            columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]
        )

    # Data final = data de referência escolhida pelo usuário (ou hoje)
    data_final = (
        pd.Timestamp(data_referencia).normalize()
        if data_referencia
        else pd.Timestamp.today().normalize()
    )

    # Aproximadamente 36 meses para trás.
    # Carregamos uma margem maior para garantir 756 pregões.
    data_inicial = data_final - pd.DateOffset(months=40)

    print(
        f"Carregando histórico de {data_inicial:%d/%m/%Y} "
        f"até {data_final:%d/%m/%Y}"
    )
    print(f"Fundos: {len(cnpjs)}")

    # Usa a função em lote já existente no seu código.
    df = carregar_historico_fundos(
        cnpjs=cnpjs,
        data_inicial=data_inicial.strftime("%Y-%m-%d"),
        data_final=data_final.strftime("%Y-%m-%d")
    )

    if df.empty:
        return pd.DataFrame(
            columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]
        )

    # Garantir tipos
    df["CNPJ_FUNDO"] = df["CNPJ_FUNDO"].astype(str).str.strip()
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    # Garantir que não estamos pegando datas depois da referência.
    # Se a data escolhida não existir para um fundo (fim de semana,
    # feriado, fundo novo, etc.), esse filtro já garante que ficamos
    # só com o que existe até (e incluindo) a data de referência —
    # ou seja, o dia útil anterior disponível entra automaticamente.
    df = df[df["DT_COMPTC"] <= data_final]

    # Ordena por fundo e data
    df = df.sort_values(
        ["CNPJ_FUNDO", "DT_COMPTC"]
    )

    # Pega exatamente os 756 últimos registros de cada fundo
    df = (
        df.groupby("CNPJ_FUNDO", group_keys=False)
          .tail(756)
          .sort_values(["CNPJ_FUNDO", "DT_COMPTC"])
          .reset_index(drop=True)
    )

    print(f"Total de registros retornados: {len(df):,}")

    # Quantidade por fundo para conferência
    quantidade = df.groupby("CNPJ_FUNDO").size()

    print(
        f"Fundos com 756 registros: "
        f"{(quantidade == 756).sum()}"
    )

    print(
        f"Fundos com menos de 756 registros: "
        f"{(quantidade < 756).sum()}"
    )

    return df

def calcular_correlacao(base_cotas: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a matriz de correlação entre os fundos utilizando
    os retornos diários das cotas.

    Parâmetros
    ----------
    base_cotas : pd.DataFrame
        DataFrame contendo:
        CNPJ_FUNDO, DT_COMPTC e VL_QUOTA.

    Retorno
    -------
    pd.DataFrame
        Matriz de correlação entre os fundos.
    """

    if base_cotas.empty:
        return pd.DataFrame()

    df = base_cotas.copy()

    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    # Ordena por fundo e data
    df = df.sort_values(
        ["CNPJ_FUNDO", "DT_COMPTC"]
    )

    # Calcula retorno diário de cada fundo
    df["RETORNO_DIARIO"] = (
        df.groupby("CNPJ_FUNDO")["VL_QUOTA"]
          .pct_change()
    )

    # Transforma:
    #
    # DATA       FUNDO_A  FUNDO_B  FUNDO_C
    # 01/01      ...      ...      ...
    # 02/01      ...      ...      ...
    #
    retornos = df.pivot(
        index="DT_COMPTC",
        columns="CNPJ_FUNDO",
        values="RETORNO_DIARIO"
    )

    # Correlação de Pearson
    correlacao = retornos.corr()

    return correlacao

def portfolio(
    fundos: pd.DataFrame,
    pesos: dict[str, float] | None = None,
    data_referencia: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calcula rentabilidade, volatilidade e a matriz de correlação dos
    fundos informados, com base nos 756 pregões anteriores à
    `data_referencia` (ou hoje, se não informada).

    Se a `data_referencia` cair em um dia não útil (fim de semana,
    feriado) ou não existir cota do fundo naquele dia, o cálculo já
    considera automaticamente a última data disponível anterior — ver
    `carregar_historico_36meses`.

    `pesos` (CNPJ -> peso, somando 1.0) ainda não é utilizado no cálculo;
    fica reservado para quando o retorno ponderado do portfólio como um
    todo for implementado.

    Retorno
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (resultado_por_fundo, matriz_de_correlacao)
    """

    base_cotas = carregar_historico_36meses(fundos, data_referencia=data_referencia)

    # Correlação entre os fundos
    correlacao = calcular_correlacao(base_cotas)

    print("\n=== MATRIZ DE CORRELAÇÃO ===")
    print(correlacao)

    if base_cotas.empty:
        return (
            pd.DataFrame(
                columns=[
                    "CNPJ_FUNDO",
                    "RENTABILIDADE",
                    "VOLATILIDADE"
                ]
            ),
            correlacao,
        )

    resultados = []

    for cnpj in fundos["CNPJ_FUNDO"].dropna().unique():

        # Histórico do fundo
        df_fundo = base_cotas[
            base_cotas["CNPJ_FUNDO"] == cnpj
        ].copy()

        if df_fundo.empty:
            continue

        # Ordena cronologicamente
        df_fundo = df_fundo.sort_values("DT_COMPTC")

        # Precisa ter pelo menos duas cotas
        if len(df_fundo) < 2:
            continue

        # Primeira e última cota
        cota_inicial = df_fundo.iloc[0]["VL_QUOTA"]
        cota_final = df_fundo.iloc[-1]["VL_QUOTA"]

        # Rentabilidade dos 756 dias
        rentabilidade = (
            (cota_final / cota_inicial) - 1
        ) * 100

        # Volatilidade
        volatilidade = calcular_volatilidade_periodo(df_fundo)

        resultados.append({
            "CNPJ_FUNDO": cnpj,
            "RENTABILIDADE": rentabilidade,
            "VOLATILIDADE": volatilidade,
            "QTD_DIAS": len(df_fundo),
            "DATA_INICIAL": df_fundo["DT_COMPTC"].iloc[0],
            "DATA_FINAL": df_fundo["DT_COMPTC"].iloc[-1],
            "COTA_INICIAL": cota_inicial,
            "COTA_FINAL": cota_final,
        })

    resultado = pd.DataFrame(resultados)

    return resultado, correlacao

