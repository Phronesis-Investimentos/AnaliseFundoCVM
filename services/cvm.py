import os
import io
import zipfile
import requests
import pandas as pd
from datetime import datetime

URL_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
URL_BASE_HIST = f"{URL_BASE}/HIST"
session = requests.Session()
# A VM pode ter variáveis de proxy apontando para um serviço local inexistente
# (por exemplo, 127.0.0.1:9). As consultas da CVM devem usar a conexão direta.
session.trust_env = False

COLUNAS_HISTORICO = ["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA", "ID_SUBCLASSE"]


def normalizar_id_subclasse(valor) -> str | None:
    """Normaliza o identificador sem convertê-lo para número/float."""
    if valor is None or pd.isna(valor):
        return None
    valor = str(valor).strip()
    return valor or None


def filtrar_por_subclasse(df: pd.DataFrame, id_subclasse: str | None) -> pd.DataFrame:
    """Aplica o filtro adicional somente quando uma subclasse foi escolhida."""
    if id_subclasse is None or df.empty or "ID_SUBCLASSE" not in df.columns:
        return df
    id_subclasse = normalizar_id_subclasse(id_subclasse)
    if id_subclasse is None:
        return df
    return df[df["ID_SUBCLASSE"].map(normalizar_id_subclasse) == id_subclasse].copy()


def _caminho_cache_mes(ano: int, mes: int) -> str:
    """Retorna o caminho do arquivo de cache para um mês específico"""
    return f"cache/{ano}{mes:02d}.parquet"


def _caminho_cache_ano(ano: int) -> str:
    """Retorna o caminho do cache para um ano inteiro (HIST)"""
    return f"cache/hist_{ano}.parquet"


def _processar_csv(csv_file) -> pd.DataFrame:
    """
    Processa o arquivo CSV (funciona tanto para mensal quanto anual)
    """
    # Lê cabeçalho para detectar coluna CNPJ
    cabecalho = pd.read_csv(
        csv_file,
        sep=";",
        encoding="latin1",
        nrows=0
    )
    
    # Detecta coluna de CNPJ
    if "CNPJ_FUNDO" in cabecalho.columns:
        coluna_cnpj = "CNPJ_FUNDO"
    elif "CNPJ_FUNDO_CLASSE" in cabecalho.columns:
        coluna_cnpj = "CNPJ_FUNDO_CLASSE"
    else:
        raise ValueError("Coluna de CNPJ não encontrada.")
    
    colunas = [coluna_cnpj, "DT_COMPTC", "VL_QUOTA"]
    # Arquivos antigos podem não possuir a coluna; nos novos, mantê-la é
    # essencial para que a série de uma subclasse não seja agregada à outra.
    if "ID_SUBCLASSE" in cabecalho.columns:
        colunas.append("ID_SUBCLASSE")

    csv_file.seek(0)
    
    # Lê em chunks para otimizar memória
    leitor = pd.read_csv(
        csv_file,
        sep=";",
        encoding="latin1",
        usecols=colunas,
        chunksize=100000,
        parse_dates=["DT_COMPTC"]
    )
    
    partes = []
    
    for chunk in leitor:
        chunk.rename(
            columns={coluna_cnpj: "CNPJ_FUNDO"},
            inplace=True
        )
        partes.append(chunk)
        del chunk
    
    df = pd.concat(partes, ignore_index=True)
    if "ID_SUBCLASSE" not in df.columns:
        df["ID_SUBCLASSE"] = None
    
    return df


def carregar_dataframe(ano: int, mes: int, cnpj: str) -> pd.DataFrame:
    """
    Carrega dados de um fundo específico para um mês/ano.
    
    Para anos <= 2020: Baixa o arquivo anual do HIST e faz cache por ano
    Para anos > 2020: Baixa o arquivo mensal e faz cache por mês
    """
    
    df_mes_completo = carregar_dataframe_mes_completo(ano, mes)
    return df_mes_completo[
        df_mes_completo["CNPJ_FUNDO"] == cnpj
    ].reset_index(drop=True)


def carregar_dataframe_mes_completo(ano: int, mes: int) -> pd.DataFrame:
    """Carrega todas as cotas de um mês, usando o cache local quando possível.

    Esta função é usada em operações em lote, como o ranking. Assim, cada
    arquivo mensal é lido uma vez, em vez de uma vez para cada fundo.
    """
    caminho_cache = _caminho_cache_mes(ano, mes)
    if os.path.exists(caminho_cache):
        print(f"Lendo do cache: {ano}-{mes:02d}")
        df_cache = pd.read_parquet(caminho_cache)
        # Caches criados antes deste ajuste não têm ID_SUBCLASSE e não podem
        # ser usados em cálculos que precisem separar subclasses.
        if "ID_SUBCLASSE" in df_cache.columns:
            return df_cache

    if ano <= 2020:
        # A função histórica também materializa o cache mensal.
        _carregar_dados_historicos(ano, mes, cnpj="")
    else:
        _carregar_dados_recentes(ano, mes, cnpj="")

    if os.path.exists(caminho_cache):
        df_atualizado = pd.read_parquet(caminho_cache)
        if "ID_SUBCLASSE" in df_atualizado.columns:
            return df_atualizado
        # Falha de rede não pode fazer o sistema voltar a usar uma série
        # legada e potencialmente agregada. Um cache sem a coluna só volta a
        # ser aceito após ser refeito pelo leitor atual.
        print(f"Cache legado não pôde ser atualizado: {ano}-{mes:02d}")

    return pd.DataFrame(columns=COLUNAS_HISTORICO)


def carregar_fundos_elegiveis_por_cotistas(
    ano: int,
    mes: int,
    minimo_cotistas: int = 10,
) -> pd.DataFrame:
    """Retorna CNPJs únicos com mais que ``minimo_cotistas`` no mês informado.

    O arquivo de elegibilidade é guardado separadamente porque os caches de
    cotas armazenam somente data e valor da cota, sem a coluna ``NR_COTST``.
    """
    caminho_cache = f"cache/elegiveis_{ano}{mes:02d}.parquet"
    if os.path.exists(caminho_cache):
        return pd.read_parquet(caminho_cache)

    arquivo = f"inf_diario_fi_{ano}{mes:02d}.zip"
    try:
        response = session.get(f"{URL_BASE}/{arquivo}", timeout=(10, 300))
        response.raise_for_status()
    except requests.RequestException as erro:
        print(f"Erro ao baixar elegibilidade de {ano}-{mes:02d}: {erro}")
        return pd.DataFrame(columns=["CNPJ_FUNDO", "NR_COTST"])

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        with zip_file.open(zip_file.namelist()[0]) as csv:
            cabecalho = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0)
            if "CNPJ_FUNDO" in cabecalho.columns:
                coluna_cnpj = "CNPJ_FUNDO"
            elif "CNPJ_FUNDO_CLASSE" in cabecalho.columns:
                coluna_cnpj = "CNPJ_FUNDO_CLASSE"
            else:
                raise ValueError("Coluna de CNPJ não encontrada.")

            csv.seek(0)
            partes = []
            for chunk in pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                usecols=[coluna_cnpj, "NR_COTST"],
                chunksize=100000,
            ):
                chunk["NR_COTST"] = pd.to_numeric(chunk["NR_COTST"], errors="coerce")
                partes.append(chunk.groupby(coluna_cnpj, as_index=False)["NR_COTST"].max())

    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "NR_COTST"])

    elegiveis = (
        pd.concat(partes, ignore_index=True)
        .groupby(coluna_cnpj, as_index=False)["NR_COTST"].max()
        .rename(columns={coluna_cnpj: "CNPJ_FUNDO"})
    )
    elegiveis["CNPJ_FUNDO"] = elegiveis["CNPJ_FUNDO"].astype(str).str.strip()
    elegiveis = elegiveis[elegiveis["NR_COTST"] > minimo_cotistas].reset_index(drop=True)

    os.makedirs("cache", exist_ok=True)
    elegiveis.to_parquet(caminho_cache, index=False)
    return elegiveis


def _carregar_dados_recentes(ano: int, mes: int, cnpj: str) -> pd.DataFrame:
    """
    Carrega dados de anos > 2020 (formato mensal)
    """
    caminho_cache = _caminho_cache_mes(ano, mes)
    arquivo = f"inf_diario_fi_{ano}{mes:02d}.zip"
    url = f"{URL_BASE}/{arquivo}"
    
    print(f"Baixando {ano}-{mes:02d} (formato mensal)")
    
    try:
        response = session.get(url, timeout=(10, 300))
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ao baixar {arquivo}: {e}")
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        nome_csv = zip_file.namelist()[0]
        
        with zip_file.open(nome_csv) as csv:
            df_mes_completo = _processar_csv(csv)
    
    # Salva cache mensal
    os.makedirs("cache", exist_ok=True)
    df_mes_completo.to_parquet(caminho_cache, index=False)
    
    return df_mes_completo[
        df_mes_completo["CNPJ_FUNDO"] == cnpj
    ].reset_index(drop=True)


def _carregar_dados_historicos(ano: int, mes: int, cnpj: str) -> pd.DataFrame:
    """
    Carrega dados de anos <= 2020 (formato anual)
    """
    caminho_cache_mes = _caminho_cache_mes(ano, mes)
    caminho_cache_ano = _caminho_cache_ano(ano)
    
    # Se já temos o ano inteiro em cache, filtra o mês
    if os.path.exists(caminho_cache_ano):
        print(f"Lendo do cache anual: {ano}")
        df_ano = pd.read_parquet(caminho_cache_ano)
        # Cache legado não tem a chave de subclasse; baixa novamente para
        # não fabricar uma série agregada a partir de dados incompletos.
        usar_cache = "ID_SUBCLASSE" in df_ano.columns
    else:
        usar_cache = False

    if not usar_cache:
        arquivo = f"inf_diario_fi_{ano}.zip"
        url = f"{URL_BASE_HIST}/{arquivo}"
        
        print(f"Baixando {ano} completo (formato HIST)")
        
        try:
            response = session.get(url, timeout=(10, 600))
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Erro ao baixar {arquivo}: {e}")
            return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            nome_csv = zip_file.namelist()[0]
            
            with zip_file.open(nome_csv) as csv:
                df_ano = _processar_csv(csv)
        
        # Cache do ano inteiro
        os.makedirs("cache", exist_ok=True)
        df_ano.to_parquet(caminho_cache_ano, index=False)
    
    # Filtra o mês específico
    df_mes = df_ano[
        (df_ano["DT_COMPTC"].dt.month == mes)
    ].copy()
    
    # Cache do mês específico (extraído do ano)
    if not df_mes.empty:
        df_mes.to_parquet(caminho_cache_mes, index=False)
    
    return df_mes[
        df_mes["CNPJ_FUNDO"] == cnpj
    ].reset_index(drop=True)


def filtrar_periodo(
    df: pd.DataFrame,
    data_inicial: str,
    data_final: str
) -> pd.DataFrame:
    """
    Filtra o DataFrame para um período específico.
    """
    inicio = pd.to_datetime(data_inicial)
    fim = pd.to_datetime(data_final) + pd.offsets.MonthEnd(0)

    return df[
        (df["DT_COMPTC"] >= inicio) &
        (df["DT_COMPTC"] <= fim)
    ]


def calcular_variacao_periodo(df: pd.DataFrame) -> float:
    """
    Calcula a variação percentual entre o primeiro e último mês.
    """
    if df.empty:
        return 0.0

    df = df.copy()
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    cota_inicial = (
        df.groupby(df["DT_COMPTC"].dt.to_period("M"))
          .last()
          .iloc[0]["VL_QUOTA"]
    )

    cota_final = (
        df.groupby(df["DT_COMPTC"].dt.to_period("M"))
          .last()
          .iloc[-1]["VL_QUOTA"]
    )

    return ((cota_final / cota_inicial) - 1) * 100


def carregar_historico_fundos(
    cnpjs,
    data_inicial: str,
    data_final: str,
    minimo_cotistas: int = 10,
) -> pd.DataFrame:
    """
    Carrega em lote o histórico de vários fundos.

    Antes de carregar o histórico, filtra os fundos para manter somente
    aqueles que possuem >= minimo_cotistas cotistas no mês de referência
    (mês de data_final).

    Os arquivos mensais da CVM são lidos uma única vez e filtrados para os
    CNPJs elegíveis.

    Parâmetros
    ----------
    cnpjs : iterable
        Lista/set de CNPJs dos fundos candidatos.

    data_inicial : str
        Data inicial do histórico.

    data_final : str
        Data final do histórico.

    minimo_cotistas : int
        Número mínimo de cotistas. Padrão = 10.

    Retorno
    -------
    pd.DataFrame
        Histórico somente dos fundos que possuem pelo menos
        `minimo_cotistas` cotistas na data de referência.
    """

    # ============================================================
    # 1. NORMALIZA OS CNPJs
    # ============================================================

    cnpjs = {
        str(cnpj).strip()
        for cnpj in cnpjs
        if pd.notna(cnpj)
    }

    if not cnpjs:
        return pd.DataFrame(
            columns=[
                "CNPJ_FUNDO",
                "DT_COMPTC",
                "VL_QUOTA"
            ]
        )

    inicio = pd.to_datetime(data_inicial)
    fim = pd.to_datetime(data_final)

    # ============================================================
    # 2. BUSCA OS FUNDOS ELEGÍVEIS
    #
    # Usa o mês da data_final como referência.
    #
    # Exemplo:
    # data_final = 2026-08-20
    # -> verifica os cotistas de agosto/2026
    #
    # ============================================================

    print(
        f"\n=== FILTRO DE COTISTAS ==="
    )

    print(
        f"Data de referência: {fim:%d/%m/%Y}"
    )

    print(
        f"Mínimo de cotistas: {minimo_cotistas}"
    )

    try:

        elegiveis = carregar_fundos_elegiveis_por_cotistas(
            ano=fim.year,
            mes=fim.month,
            minimo_cotistas=minimo_cotistas,
        )

    except Exception as erro:

        print(
            f"❌ Erro ao carregar fundos elegíveis: {erro}"
        )

        return pd.DataFrame(
            columns=[
                "CNPJ_FUNDO",
                "DT_COMPTC",
                "VL_QUOTA"
            ]
        )

    if elegiveis.empty:

        print(
            "⚠️ Nenhum fundo elegível encontrado."
        )

        return pd.DataFrame(
            columns=[
                "CNPJ_FUNDO",
                "DT_COMPTC",
                "VL_QUOTA"
            ]
        )

    # Normaliza CNPJs
    elegiveis["CNPJ_FUNDO"] = (
        elegiveis["CNPJ_FUNDO"]
        .astype(str)
        .str.strip()
    )

    # ============================================================
    # 3. INTERSEÇÃO
    #
    # Mantém somente os fundos que:
    #
    # 1. Foram solicitados em `cnpjs`
    # 2. Possuem >= 10 cotistas
    #
    # ============================================================

    cnpjs_elegiveis = (
        set(elegiveis["CNPJ_FUNDO"])
        .intersection(cnpjs)
    )

    print(
        f"Fundos solicitados: {len(cnpjs)}"
    )

    print(
        f"Fundos com >= {minimo_cotistas} cotistas: "
        f"{len(cnpjs_elegiveis)}"
    )

    fundos_excluidos = cnpjs - cnpjs_elegiveis

    print(
        f"Fundos excluídos por cotistas: "
        f"{len(fundos_excluidos)}"
    )

    if not cnpjs_elegiveis:

        print(
            "⚠️ Nenhum dos fundos solicitados possui "
            f"{minimo_cotistas} ou mais cotistas."
        )

        return pd.DataFrame(
            columns=[
                "CNPJ_FUNDO",
                "DT_COMPTC",
                "VL_QUOTA"
            ]
        )

    # ============================================================
    # 4. MOSTRA OS FUNDOS QUE SERÃO CARREGADOS
    # ============================================================

    print(
        "\nFundos elegíveis:"
    )

    for cnpj in sorted(cnpjs_elegiveis):
        print(f"  ✅ {cnpj}")

    # A partir daqui NÃO usamos mais `cnpjs`.
    #
    # Isso é importante:
    #
    # antes:
    #     df_mes["CNPJ_FUNDO"].isin(cnpjs)
    #
    # agora:
    #     df_mes["CNPJ_FUNDO"].isin(cnpjs_elegiveis)
    #
    # Assim um fundo com menos de 10 cotistas nunca entra
    # no histórico.

    # ============================================================
    # 5. GERA OS MESES NECESSÁRIOS
    # ============================================================

    datas_mensais = pd.date_range(
        start=inicio.replace(day=1),
        end=fim.replace(day=1),
        freq="MS"
    )

    partes = []

    # ============================================================
    # 6. CARREGA OS DADOS
    # ============================================================

    for data_mes in datas_mensais:

        ano = data_mes.year
        mes = data_mes.month

        try:

            print(
                f"Carregando cotas: "
                f"{ano}-{mes:02d}"
            )

            df_mes = carregar_dataframe_mes_completo(
                ano,
                mes
            )

            if df_mes.empty:
                continue

            # Normaliza CNPJ
            df_mes["CNPJ_FUNDO"] = (
                df_mes["CNPJ_FUNDO"]
                .astype(str)
                .str.strip()
            )

            # ====================================================
            # FILTRO PRINCIPAL
            # ====================================================

            df_mes = df_mes[
                df_mes["CNPJ_FUNDO"].isin(
                    cnpjs_elegiveis
                )
            ].copy()

            if not df_mes.empty:
                partes.append(df_mes)

        except Exception as erro:

            print(
                f"Erro ao carregar "
                f"{ano}-{mes:02d}: {erro}"
            )

    # ============================================================
    # 7. NENHUM DADO
    # ============================================================

    if not partes:

        return pd.DataFrame(
            columns=[
                "CNPJ_FUNDO",
                "DT_COMPTC",
                "VL_QUOTA"
            ]
        )

    # ============================================================
    # 8. CONCATENA
    # ============================================================

    df_final = pd.concat(
        partes,
        ignore_index=True
    )

    # ============================================================
    # 9. LIMPEZA
    # ============================================================

    df_final["CNPJ_FUNDO"] = (
        df_final["CNPJ_FUNDO"]
        .astype(str)
        .str.strip()
    )

    df_final["DT_COMPTC"] = pd.to_datetime(
        df_final["DT_COMPTC"],
        errors="coerce"
    )

    df_final["VL_QUOTA"] = pd.to_numeric(
        df_final["VL_QUOTA"],
        errors="coerce"
    )

    df_final = df_final.dropna(
        subset=[
            "CNPJ_FUNDO",
            "DT_COMPTC",
            "VL_QUOTA"
        ]
    )

    # Remove duplicidades
    df_final = (
        df_final
        .drop_duplicates(
            subset=[
                "CNPJ_FUNDO",
                "DT_COMPTC"
            ],
            keep="last"
        )
        .sort_values(
            [
                "CNPJ_FUNDO",
                "DT_COMPTC"
            ]
        )
        .reset_index(drop=True)
    )

    # ============================================================
    # 10. LOG FINAL
    # ============================================================

    print(
        f"\n=== HISTÓRICO CARREGADO ==="
    )

    print(
        f"Fundos elegíveis: "
        f"{df_final['CNPJ_FUNDO'].nunique()}"
    )

    print(
        f"Registros: "
        f"{len(df_final):,}"
    )

    return df_final

def encontrar_primeira_cota(cnpj: str, id_subclasse: str | None = None) -> pd.DataFrame:
    """
    Encontra a primeira cota disponível de um fundo,
    vasculhando os arquivos históricos desde 2001.
    
    Estratégia:
    1. Começa do ano mais antigo (2001) e vai subindo
    2. Para cada ano, tenta encontrar o fundo
    3. Quando encontra, retorna a primeira ocorrência
    
    Args:
        cnpj: CNPJ do fundo
    
    Returns:
        DataFrame com a primeira cota encontrada
    """
    from datetime import datetime
    
    ano_atual = datetime.today().year
    
    print(f"\n=== BUSCANDO PRIMEIRA COTA DO FUNDO {cnpj} ===")
    
    # Para anos <= 2020, busca no arquivo anual
    for ano in range(2001, 2021):
        try:
            print(f"Verificando ano {ano}...")
            
            # Tenta carregar o arquivo anual
            arquivo = f"inf_diario_fi_{ano}.zip"
            url = f"{URL_BASE_HIST}/{arquivo}"
            
            response = session.get(url, timeout=(10, 600))
            
            if response.status_code != 200:
                print(f"  Ano {ano} não disponível")
                continue
            
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                nome_csv = zip_file.namelist()[0]
                
                with zip_file.open(nome_csv) as csv:
                    # Lê apenas as linhas do fundo específico
                    df_ano = _processar_csv_filtrado(csv, cnpj)
                    
                    if not df_ano.empty:
                        # Encontrou! Pega a primeira cota
                        primeira_cota = df_ano.sort_values("DT_COMPTC").iloc[0]
                        print(f"  ✅ Primeira cota encontrada em {primeira_cota['DT_COMPTC'].strftime('%d/%m/%Y')}")
                        print(f"  Valor: R$ {primeira_cota['VL_QUOTA']:.6f}")
                        return filtrar_por_subclasse(df_ano, id_subclasse).sort_values("DT_COMPTC").head(1)
        
        except Exception as e:
            print(f"  Erro no ano {ano}: {str(e)}")
            continue
    
    # Para anos > 2020, busca nos arquivos mensais
    for ano in range(2021, ano_atual + 1):
        for mes in range(1, 13):
            try:
                print(f"Verificando {ano}-{mes:02d}...")
                
                df_mes = carregar_dataframe(ano, mes, cnpj)
                
                if not df_mes.empty:
                    # Encontrou!
                    primeira_cota = df_mes.sort_values("DT_COMPTC").iloc[0]
                    print(f"  ✅ Primeira cota encontrada em {primeira_cota['DT_COMPTC'].strftime('%d/%m/%Y')}")
                    print(f"  Valor: R$ {primeira_cota['VL_QUOTA']:.6f}")
                    return filtrar_por_subclasse(df_mes, id_subclasse).sort_values("DT_COMPTC").head(1)
            
            except Exception as e:
                print(f"  Erro em {ano}-{mes:02d}: {str(e)}")
                continue
    
    return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])


def _processar_csv_filtrado(csv_file, cnpj: str) -> pd.DataFrame:
    """
    Processa CSV procurando apenas um CNPJ específico.
    Mais eficiente que carregar tudo.
    """
    import io
    
    # Lê o arquivo em chunks procurando o CNPJ
    chunks = []
    
    for chunk in pd.read_csv(
        csv_file,
        sep=";",
        encoding="latin1",
        chunksize=100000,
        parse_dates=["DT_COMPTC"]
    ):
        # Detecta coluna CNPJ
        if "CNPJ_FUNDO" in chunk.columns:
            coluna_cnpj = "CNPJ_FUNDO"
        elif "CNPJ_FUNDO_CLASSE" in chunk.columns:
            coluna_cnpj = "CNPJ_FUNDO_CLASSE"
        else:
            continue
        
        # Filtra pelo CNPJ
        chunk_filtrado = chunk[chunk[coluna_cnpj] == cnpj].copy()
        
        if not chunk_filtrado.empty:
            chunk_filtrado.rename(columns={coluna_cnpj: "CNPJ_FUNDO"}, inplace=True)
            if "ID_SUBCLASSE" not in chunk_filtrado.columns:
                chunk_filtrado["ID_SUBCLASSE"] = None
            chunks.append(chunk_filtrado[COLUNAS_HISTORICO])
    
    if chunks:
        return pd.concat(chunks, ignore_index=True)
    
    return pd.DataFrame(columns=COLUNAS_HISTORICO)


def carregar_historico_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str,
    id_subclasse: str | None = None,
) -> pd.DataFrame:
    """
    Carrega o histórico completo de um fundo entre duas datas.
    
    Se data_inicial for '0000-01-01', busca desde a primeira cota disponível.
    """
    # Verifica se é período "Desde o Início"
    if data_inicial == "0000-01-01":
        return carregar_desde_inicio(cnpj, data_final, id_subclasse=id_subclasse)
    
    # Código existente para períodos normais...
    inicio = pd.to_datetime(data_inicial)
    fim = pd.to_datetime(data_final)
    
    datas_mensais = pd.date_range(
        start=inicio.replace(day=1),
        end=fim.replace(day=1),
        freq='MS'
    )
    
    if len(datas_mensais) == 0:
        datas_mensais = [inicio.replace(day=1)]
    
    partes = []
    
    for data_mes in datas_mensais:
        ano = data_mes.year
        mes = data_mes.month
        
        try:
            df_mes = carregar_dataframe(ano, mes, cnpj)
            
            if not df_mes.empty:
                partes.append(df_mes)
                
        except Exception as e:
            print(f"Erro ao carregar {ano}-{mes:02d}: {str(e)}")
            continue
    
    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    
    df_completo = filtrar_por_subclasse(pd.concat(partes, ignore_index=True), id_subclasse)
    df_completo = df_completo.drop_duplicates(subset=["DT_COMPTC"])
    df_completo = df_completo.sort_values("DT_COMPTC")
    
    return df_completo


def carregar_desde_inicio(cnpj: str, data_final: str, id_subclasse: str | None = None) -> pd.DataFrame:
    """
    Carrega todos os dados do fundo desde sua primeira cota até a data final.
    
    Estratégia otimizada:
    1. Primeiro encontra a data da primeira cota
    2. Depois carrega apenas do período necessário
    """
    print(f"\n=== CARREGANDO HISTÓRICO COMPLETO DO FUNDO {cnpj} ===")
    
    # Passo 1: Encontra a primeira cota
    df_primeira = encontrar_primeira_cota(cnpj, id_subclasse=id_subclasse)
    
    if df_primeira.empty:
        print("❌ Nenhuma cota encontrada para este fundo")
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    
    primeira_data = df_primeira.iloc[0]["DT_COMPTC"]
    print(f"✅ Primeira cota: {primeira_data.strftime('%d/%m/%Y')}")
    
    # Passo 2: Carrega do início até a data final
    # Usa a função normal com a data da primeira cota
    data_inicial = primeira_data.strftime("%Y-%m-%d")
    
    # Converte datas
    inicio = pd.to_datetime(data_inicial)
    fim = pd.to_datetime(data_final)
    
    # Gera lista de meses necessários
    datas_mensais = pd.date_range(
        start=inicio.replace(day=1),
        end=fim.replace(day=1),
        freq='MS'
    )
    
    if len(datas_mensais) == 0:
        datas_mensais = [inicio.replace(day=1)]
    
    print(f"Carregando {len(datas_mensais)} meses de dados...")
    
    partes = []
    
    for i, data_mes in enumerate(datas_mensais, 1):
        ano = data_mes.year
        mes = data_mes.month
        
        if i % 12 == 0:  # Log a cada ano
            print(f"  Progresso: {i}/{len(datas_mensais)} meses")
        
        try:
            df_mes = carregar_dataframe(ano, mes, cnpj)
            
            if not df_mes.empty:
                partes.append(df_mes)
                
        except Exception as e:
            print(f"  Erro ao carregar {ano}-{mes:02d}: {str(e)}")
            continue
    
    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    
    df_completo = filtrar_por_subclasse(pd.concat(partes, ignore_index=True), id_subclasse)
    df_completo = df_completo.drop_duplicates(subset=["DT_COMPTC"])
    df_completo = df_completo.sort_values("DT_COMPTC")
    
    print(f"✅ Total de {len(df_completo)} registros carregados")
    
    return df_completo


def carregar_historico_fundos(
    cnpjs,
    data_inicial: str,
    data_final: str,
    subclasses: dict[str, str | None] | None = None,
) -> pd.DataFrame:
    """Carrega em lote o histórico de vários fundos.

    Os arquivos mensais da CVM são lidos uma única vez e filtrados para os
    CNPJs solicitados. Para o ranking isso elimina a leitura repetida dos
    mesmos 60 arquivos para cada fundo.
    """
    cnpjs = {str(cnpj).strip() for cnpj in cnpjs}
    if not cnpjs:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])

    inicio = pd.to_datetime(data_inicial)
    fim = pd.to_datetime(data_final)
    datas_mensais = pd.date_range(
        start=inicio.replace(day=1),
        end=fim.replace(day=1),
        freq="MS"
    )

    partes = []
    for data_mes in datas_mensais:
        try:
            df_mes = carregar_dataframe_mes_completo(data_mes.year, data_mes.month)
            df_mes = df_mes[df_mes["CNPJ_FUNDO"].isin(cnpjs)]
            if not df_mes.empty:
                partes.append(df_mes)
        except Exception as erro:
            print(f"Erro ao carregar {data_mes.year}-{data_mes.month:02d}: {erro}")

    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])

    df_final = pd.concat(partes, ignore_index=True)
    if "ID_SUBCLASSE" not in df_final.columns:
        df_final["ID_SUBCLASSE"] = None
    if subclasses:
        partes_filtradas = []
        for cnpj, grupo in df_final.groupby("CNPJ_FUNDO", sort=False):
            partes_filtradas.append(filtrar_por_subclasse(grupo, subclasses.get(str(cnpj).strip())))
        df_final = pd.concat(partes_filtradas, ignore_index=True) if partes_filtradas else df_final.iloc[0:0]

    return (
        df_final
        .drop_duplicates(subset=["CNPJ_FUNDO", "DT_COMPTC"])
        .sort_values(["CNPJ_FUNDO", "DT_COMPTC"])
        .reset_index(drop=True)
    )


def listar_subclasses_fundo(cnpj: str, data_referencia: str | None = None) -> list[str]:
    """Retorna IDs não vazios disponíveis para um fundo, sem alterar o fluxo legado."""
    fim = pd.Timestamp(data_referencia).normalize() if data_referencia else pd.Timestamp.today().normalize()
    inicio = fim - pd.DateOffset(months=2)
    df = carregar_historico_fundo(cnpj, inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d"))
    if df.empty or "ID_SUBCLASSE" not in df.columns:
        return []
    return sorted({valor for valor in df["ID_SUBCLASSE"].map(normalizar_id_subclasse) if valor is not None})


def carregar_cotas_referencia_fundos(cnpjs, datas_referencia) -> pd.DataFrame:
    """Carrega somente os fechamentos mensais necessários para rentabilidade.

    Para cada mês de referência, lê o arquivo da CVM uma vez e mantém a
    última cota mensal de cada CNPJ solicitado. É apropriada quando não há
    métricas, como volatilidade, que dependam do histórico diário completo.
    """
    cnpjs = set(cnpjs)
    meses = pd.PeriodIndex(pd.to_datetime(list(datas_referencia)), freq="M").unique()
    if not cnpjs or meses.empty:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])

    partes = []
    for mes in meses:
        try:
            df_mes = carregar_dataframe_mes_completo(mes.year, mes.month)
            cotas = df_mes[df_mes["CNPJ_FUNDO"].isin(cnpjs)].copy()
            if not cotas.empty:
                cotas["DT_COMPTC"] = pd.to_datetime(cotas["DT_COMPTC"])
                partes.append(
                    cotas.sort_values("DT_COMPTC")
                    .groupby("CNPJ_FUNDO", as_index=False)
                    .last()
                )
        except Exception as erro:
            print(f"Erro ao carregar {mes.year}-{mes.month:02d}: {erro}")

    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])

    return (
        pd.concat(partes, ignore_index=True)
        .drop_duplicates(subset=["CNPJ_FUNDO", "DT_COMPTC"])
        .sort_values(["CNPJ_FUNDO", "DT_COMPTC"])
        .reset_index(drop=True)
    )
