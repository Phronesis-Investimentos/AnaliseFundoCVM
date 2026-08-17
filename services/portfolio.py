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

def calcular_covariancia(
    correlacao: pd.DataFrame,
    volatilidades: dict[str, float],
    pesos: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Calcula a matriz de covariância entre os fundos usando a fórmula
    simples de covariância a partir da correlação:

        cov(i, j) = correlacao(i, j) * vol(i) * vol(j) * peso(i) * peso(j)

    Ou seja, mesma estrutura/shape da matriz de correlação (CNPJ x
    CNPJ), mas com o valor "real" (não normalizado entre -1 e 1): cada
    célula já embute a volatilidade de cada fundo e o peso de cada um
    no portfólio.

    IMPORTANTE: como todos os termos da fórmula (correlação, volatilidade
    e peso) são frações entre -1 e 1, `volatilidades` aqui já é
    convertido de percentual (15.0 = 15%) para fração decimal (0.15)
    antes de multiplicar — senão o resultado explode (ex.: 15 * 15 = 225
    em vez de 0.15 * 0.15 = 0.0225). Com essa conversão, cada célula da
    matriz também fica sempre <= 1 (mesmo teto da correlação), já que é
    produto de frações <= 1.

    Parâmetros
    ----------
    correlacao : pd.DataFrame
        Matriz de correlação entre os fundos (ver `calcular_correlacao`),
        indexada e com colunas por CNPJ_FUNDO.
    volatilidades : dict[str, float]
        CNPJ_FUNDO -> volatilidade anualizada em PERCENTUAL (mesma escala
        de VOLATILIDADE, ex.: 15.0 = 15%). É convertida para fração
        decimal internamente.
    pesos : dict[str, float] | None
        CNPJ_FUNDO -> peso (fração, ex.: 0.25 para 25%). Se None, ou se
        um fundo não tiver peso informado, assume peso igual entre
        todos os fundos da matriz de correlação (1 / quantidade de
        fundos).

    Retorno
    -------
    pd.DataFrame
        Matriz de covariância, indexada e com colunas por CNPJ_FUNDO,
        no mesmo shape de `correlacao`.
    """

    if correlacao is None or correlacao.empty:
        return pd.DataFrame()

    cnpjs = list(correlacao.columns)

    # Sem pesos informados: distribui igualmente entre os fundos
    # (mesmo comportamento padrão usado na tela de Portfólio).
    if not pesos:
        peso_igual = 1 / len(cnpjs) if cnpjs else 0
        pesos = {cnpj: peso_igual for cnpj in cnpjs}

    covariancia = pd.DataFrame(index=cnpjs, columns=cnpjs, dtype=float)

    for cnpj_i in cnpjs:
        vol_i = volatilidades.get(cnpj_i)
        peso_i = pesos.get(cnpj_i, 0.0)

        for cnpj_j in cnpjs:
            vol_j = volatilidades.get(cnpj_j)
            peso_j = pesos.get(cnpj_j, 0.0)

            corr_ij = correlacao.loc[cnpj_i, cnpj_j]

            if vol_i is None or vol_j is None or pd.isna(corr_ij):
                covariancia.loc[cnpj_i, cnpj_j] = None
                continue

            # Percentual -> fração decimal (15.0 -> 0.15)
            vol_i_fracao = vol_i / 100
            vol_j_fracao = vol_j / 100

            covariancia.loc[cnpj_i, cnpj_j] = (
                corr_ij * vol_i_fracao * vol_j_fracao * peso_i * peso_j
            )

    return covariancia

def portfolio(
    fundos: pd.DataFrame,
    pesos: dict[str, float] | None = None,
    data_referencia: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calcula rentabilidade, volatilidade, a matriz de correlação e a
    matriz de covariância dos fundos informados, com base nos 756
    pregões anteriores à `data_referencia` (ou hoje, se não informada).

    Se a `data_referencia` cair em um dia não útil (fim de semana,
    feriado) ou não existir cota do fundo naquele dia, o cálculo já
    considera automaticamente a última data disponível anterior — ver
    `carregar_historico_36meses`.

    A matriz de covariância é calculada a partir da correlação entre os
    fundos, multiplicada pela volatilidade e pelo peso de cada par de
    fundos (ver `calcular_covariancia`). Sem `pesos` informado, assume
    peso igual entre todos os fundos.

    Retorno
    -------
    tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        (resultado_por_fundo, matriz_de_correlacao, matriz_de_covariancia)
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
            pd.DataFrame(),
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

    # Covariância = correlação x volatilidade x peso de cada par de
    # fundos. Precisa da volatilidade por fundo (calculada acima), por
    # isso só é calculada aqui, depois do loop.
    volatilidades = (
        resultado.set_index("CNPJ_FUNDO")["VOLATILIDADE"].to_dict()
        if not resultado.empty
        else {}
    )
    covariancia = calcular_covariancia(correlacao, volatilidades, pesos)

    return resultado, correlacao, covariancia