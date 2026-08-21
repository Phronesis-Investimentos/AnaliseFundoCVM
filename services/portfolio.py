import pandas as pd
from services.volatilidade import calcular_volatilidade_periodo
from services.cvm import carregar_historico_fundos, carregar_desde_inicio, filtrar_por_subclasse


def carregar_historico_36meses(
    fundos: pd.DataFrame,
    data_referencia: str | pd.Timestamp | None = None,
    subclasses: dict[str, str | None] | None = None,
) -> pd.DataFrame:
    colunas = ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA", "ID_SUBCLASSE"]
    if fundos.empty:
        return pd.DataFrame(columns=colunas)

    cnpjs = fundos["CNPJ_FUNDO"].dropna().astype(str).str.strip().unique().tolist()
    if not cnpjs:
        return pd.DataFrame(columns=colunas)

    data_final = pd.Timestamp(data_referencia).normalize() if data_referencia is not None else pd.Timestamp.today().normalize()
    data_inicial = data_final - pd.DateOffset(months=40)

    print(f"Carregando histórico inicial de {data_inicial:%d/%m/%Y} até {data_final:%d/%m/%Y}")
    print(f"Fundos: {len(cnpjs)}")

    df = carregar_historico_fundos(
        cnpjs=cnpjs,
        data_inicial=data_inicial.strftime("%Y-%m-%d"),
        data_final=data_final.strftime("%Y-%m-%d"),
        subclasses=subclasses,
    )

    if df.empty:
        df = pd.DataFrame(columns=colunas)
    else:
        df = df.copy()
        df["CNPJ_FUNDO"] = df["CNPJ_FUNDO"].astype(str).str.strip()
        df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
        df["VL_QUOTA"] = pd.to_numeric(df["VL_QUOTA"], errors="coerce")
        df = df.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
        df = df[(df["DT_COMPTC"] <= data_final) & (df["VL_QUOTA"] > 0)].copy()
        df = df.sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).drop_duplicates(["CNPJ_FUNDO", "DT_COMPTC"], keep="last")

    quantidade = df.groupby("CNPJ_FUNDO").size()
    fundos_incompletos = quantidade[quantidade < 756].index.tolist()
    fundos_encontrados = set(quantidade.index)
    fundos_incompletos += [c for c in cnpjs if c not in fundos_encontrados]
    fundos_incompletos = list(dict.fromkeys(fundos_incompletos))

    print(f"Fundos com 756 ou mais cotas: {(quantidade >= 756).sum()}")
    print(f"Fundos com menos de 756 cotas: {len(fundos_incompletos)}")

    historicos_desde_inicio = []
    for i, cnpj in enumerate(fundos_incompletos, 1):
        print(f"\n[{i}/{len(fundos_incompletos)}] Buscando histórico completo: {cnpj}")
        try:
            df_inicio = carregar_desde_inicio(
                cnpj=cnpj,
                data_final=data_final.strftime("%Y-%m-%d"),
                id_subclasse=(subclasses or {}).get(cnpj),
            )
            if df_inicio.empty:
                print(f"  ⚠️ Nenhum histórico encontrado para {cnpj}")
                continue

            df_inicio = df_inicio.copy()
            df_inicio["CNPJ_FUNDO"] = df_inicio["CNPJ_FUNDO"].astype(str).str.strip()
            df_inicio["DT_COMPTC"] = pd.to_datetime(df_inicio["DT_COMPTC"], errors="coerce")
            df_inicio["VL_QUOTA"] = pd.to_numeric(df_inicio["VL_QUOTA"], errors="coerce")
            df_inicio = df_inicio.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
            df_inicio = df_inicio[(df_inicio["DT_COMPTC"] <= data_final) & (df_inicio["VL_QUOTA"] > 0)].copy()
            df_inicio = df_inicio.sort_values("DT_COMPTC").drop_duplicates(["CNPJ_FUNDO", "DT_COMPTC"], keep="last")

            if not df_inicio.empty:
                historicos_desde_inicio.append(df_inicio[colunas])
                print(f"  ✅ {len(df_inicio)} cotas | {df_inicio['DT_COMPTC'].iloc[0]:%d/%m/%Y} até {df_inicio['DT_COMPTC'].iloc[-1]:%d/%m/%Y}")
        except Exception as erro:
            print(f"  ❌ Erro ao buscar início do fundo {cnpj}: {erro}")

    if fundos_incompletos and not df.empty:
        df = df[~df["CNPJ_FUNDO"].isin(fundos_incompletos)].copy()

    if historicos_desde_inicio:
        df = pd.concat([df, pd.concat(historicos_desde_inicio, ignore_index=True)], ignore_index=True)

    if df.empty:
        return pd.DataFrame(columns=colunas)

    df = df.sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).drop_duplicates(["CNPJ_FUNDO", "DT_COMPTC"], keep="last")

    # Somente fundos antigos são cortados para 756. Fundos novos mantêm tudo.
    partes = []
    for cnpj, grupo in df.groupby("CNPJ_FUNDO", sort=False):
        grupo = grupo.sort_values("DT_COMPTC")
        partes.append(grupo.tail(756) if len(grupo) >= 756 else grupo)

    df = pd.concat(partes, ignore_index=True).sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).reset_index(drop=True)

    quantidade_final = df.groupby("CNPJ_FUNDO").size()
    print(f"\nTotal de registros retornados: {len(df):,}")
    print(f"Fundos com 756 registros: {(quantidade_final == 756).sum()}")
    print(f"Fundos com menos de 756 registros: {(quantidade_final < 756).sum()}")

    if (quantidade_final < 756).any():
        print("\nFundos com histórico menor que 756:")
        for cnpj, qtd in quantidade_final[quantidade_final < 756].items():
            grupo = df[df["CNPJ_FUNDO"] == cnpj].sort_values("DT_COMPTC")
            print(f"  {cnpj}: {qtd} cotas | {grupo['DT_COMPTC'].iloc[0]:%d/%m/%Y} até {grupo['DT_COMPTC'].iloc[-1]:%d/%m/%Y}")

    return df


def calcular_correlacao(base_cotas: pd.DataFrame) -> pd.DataFrame:
    if base_cotas.empty:
        return pd.DataFrame()

    df = base_cotas.copy()
    df["CNPJ_FUNDO"] = df["CNPJ_FUNDO"].astype(str).str.strip()
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
    df["VL_QUOTA"] = pd.to_numeric(df["VL_QUOTA"], errors="coerce")
    df = df.dropna(subset=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    df = df[df["VL_QUOTA"] > 0]
    df = df.sort_values(["CNPJ_FUNDO", "DT_COMPTC"]).drop_duplicates(["CNPJ_FUNDO", "DT_COMPTC"])

    # O primeiro dia de cada fundo não tem retorno. Na correlação, o pandas
    # usa somente as datas em que os DOIS fundos possuem retorno.
    df["RETORNO_DIARIO"] = df.groupby("CNPJ_FUNDO")["VL_QUOTA"].pct_change()
    retornos = df.pivot(index="DT_COMPTC", columns="CNPJ_FUNDO", values="RETORNO_DIARIO")
    return retornos.corr(method="pearson", min_periods=2)


def calcular_covariancia(base_cotas: pd.DataFrame, volatilidades: dict[str, float], pesos: dict[str, float] | None = None) -> pd.DataFrame:
    correlacao = calcular_correlacao(base_cotas)
    if correlacao is None or correlacao.empty:
        return pd.DataFrame()

    cnpjs = list(correlacao.columns)
    if not pesos:
        peso = 1 / len(cnpjs) if cnpjs else 0
        pesos = {cnpj: peso for cnpj in cnpjs}

    covariancia = pd.DataFrame(index=cnpjs, columns=cnpjs, dtype=float)
    for i in cnpjs:
        vol_i = volatilidades.get(i)
        peso_i = pesos.get(i, 0.0)
        for j in cnpjs:
            vol_j = volatilidades.get(j)
            peso_j = pesos.get(j, 0.0)
            corr = correlacao.loc[i, j]
            if vol_i is None or vol_j is None or pd.isna(corr):
                covariancia.loc[i, j] = None
                continue
            covariancia.loc[i, j] = corr * (vol_i / 100) * (vol_j / 100) * peso_i * peso_j
    return covariancia


def calcular_risk_attribution(covariancia: pd.DataFrame) -> pd.Series:
    if covariancia is None or covariancia.empty:
        return pd.Series(dtype=float)
    soma_colunas = covariancia.sum(axis=0, skipna=True)
    soma_total = covariancia.to_numpy(dtype=float).sum()
    if soma_total == 0 or pd.isna(soma_total):
        return pd.Series(0.0, index=covariancia.columns)
    return (soma_colunas / soma_total) * 100


def calcular_attribution(resultado: pd.DataFrame, pesos: dict[str, float] | None = None) -> pd.Series:
    if resultado is None or resultado.empty:
        return pd.Series(dtype=float)
    cnpjs = resultado["CNPJ_FUNDO"].tolist()
    if not pesos:
        peso = 1 / len(cnpjs) if cnpjs else 0
        pesos = {cnpj: peso for cnpj in cnpjs}
    rentabilidades = resultado.set_index("CNPJ_FUNDO")["RENTABILIDADE"]
    pesos_series = pd.Series({cnpj: pesos.get(cnpj, 0.0) for cnpj in cnpjs})
    return rentabilidades * pesos_series


def calcular_indice_attribution_risco(attribution: pd.Series, risco_atribuido: pd.Series) -> pd.Series:
    if attribution is None or attribution.empty or risco_atribuido is None or risco_atribuido.empty:
        return pd.Series(dtype=float)
    indice = pd.Series(index=attribution.index, dtype=float)
    for cnpj in attribution.index:
        risco = risco_atribuido.get(cnpj)
        if risco is None or pd.isna(risco) or risco == 0:
            indice.loc[cnpj] = None
        else:
            indice.loc[cnpj] = attribution.loc[cnpj] / abs(risco)
    return indice


def portfolio(
    fundos: pd.DataFrame,
    pesos: dict[str, float] | None = None,
    data_referencia: str | pd.Timestamp | None = None,
    subclasses: dict[str, str | None] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fundos = fundos.copy()
    fundos["CNPJ_FUNDO"] = fundos["CNPJ_FUNDO"].astype(str).str.strip()

    base_cotas = carregar_historico_36meses(
        fundos,
        data_referencia=data_referencia,
        subclasses=subclasses,
    )
    correlacao = calcular_correlacao(base_cotas)

    print("\n=== MATRIZ DE CORRELAÇÃO ===")
    print(correlacao)

    if base_cotas.empty:
        return (pd.DataFrame(columns=["CNPJ_FUNDO", "RENTABILIDADE", "VOLATILIDADE"]), correlacao, pd.DataFrame())

    resultados = []
    for cnpj in fundos["CNPJ_FUNDO"].dropna().unique():
        df_fundo = base_cotas[base_cotas["CNPJ_FUNDO"] == cnpj].copy()
        df_fundo = filtrar_por_subclasse(df_fundo, (subclasses or {}).get(cnpj))
        if df_fundo.empty:
            continue

        df_fundo["DT_COMPTC"] = pd.to_datetime(df_fundo["DT_COMPTC"], errors="coerce")
        df_fundo["VL_QUOTA"] = pd.to_numeric(df_fundo["VL_QUOTA"], errors="coerce")
        df_fundo = df_fundo.dropna(subset=["DT_COMPTC", "VL_QUOTA"])
        df_fundo = df_fundo[df_fundo["VL_QUOTA"] > 0]
        df_fundo = df_fundo.sort_values("DT_COMPTC").drop_duplicates("DT_COMPTC").reset_index(drop=True)

        if len(df_fundo) < 2:
            continue

        # Para fundos antigos, base_cotas já contém somente as últimas 756 cotas.
        # Para fundos novos, contém TODAS as cotas desde a primeira existência.
        cota_inicial = df_fundo.iloc[0]["VL_QUOTA"]
        cota_final = df_fundo.iloc[-1]["VL_QUOTA"]
        rentabilidade = ((cota_final / cota_inicial) - 1) * 100

        # A volatilidade usa exatamente o histórico disponível deste fundo.
        volatilidade = calcular_volatilidade_periodo(df_fundo, anualizar=True, dias_uteis_ano=252)

        qtd = len(df_fundo)
        resultados.append({
            "CNPJ_FUNDO": cnpj,
            "RENTABILIDADE": rentabilidade,
            "VOLATILIDADE": volatilidade,
            "QTD_DIAS": qtd,
            "DATA_INICIAL": df_fundo["DT_COMPTC"].iloc[0],
            "DATA_FINAL": df_fundo["DT_COMPTC"].iloc[-1],
            "COTA_INICIAL": cota_inicial,
            "COTA_FINAL": cota_final,
        })

        if qtd < 756:
            print("\n=== FUNDO COM MENOS DE 756 COTAS ===")
            print(f"CNPJ: {cnpj}")
            print(f"Quantidade: {qtd}")
            print(f"Data inicial: {df_fundo['DT_COMPTC'].iloc[0]:%d/%m/%Y}")
            print(f"Data final: {df_fundo['DT_COMPTC'].iloc[-1]:%d/%m/%Y}")
            print(f"Cota inicial: {cota_inicial:.8f}")
            print(f"Cota final: {cota_final:.8f}")
            print(f"Rentabilidade: {rentabilidade:.2f}%")
            print(f"Volatilidade: {volatilidade:.2f}%")

    resultado = pd.DataFrame(resultados)

    volatilidades = resultado.set_index("CNPJ_FUNDO")["VOLATILIDADE"].to_dict() if not resultado.empty else {}
    covariancia = calcular_covariancia(base_cotas, volatilidades, pesos)

    risco_atribuido = calcular_risk_attribution(covariancia)
    resultado["RISCO_ATRIBUIDO"] = resultado["CNPJ_FUNDO"].map(risco_atribuido) if not resultado.empty else None

    attribution = calcular_attribution(resultado, pesos)
    resultado["ATTRIBUTION"] = resultado["CNPJ_FUNDO"].map(attribution) if not resultado.empty else None

    indice = calcular_indice_attribution_risco(attribution, risco_atribuido)
    resultado["ATTRIBUTION_POR_RISCO"] = resultado["CNPJ_FUNDO"].map(indice) if not resultado.empty else None

    return resultado, correlacao, covariancia
