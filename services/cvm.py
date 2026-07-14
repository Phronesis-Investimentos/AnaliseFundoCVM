import os
import io
import zipfile
import requests
import pandas as pd
from datetime import datetime

URL_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
URL_BASE_HIST = f"{URL_BASE}/HIST"
session = requests.Session()


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
    
    csv_file.seek(0)
    
    # Lê em chunks para otimizar memória
    leitor = pd.read_csv(
        csv_file,
        sep=";",
        encoding="latin1",
        usecols=[coluna_cnpj, "DT_COMPTC", "VL_QUOTA"],
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
    
    return df


def carregar_dataframe(ano: int, mes: int, cnpj: str) -> pd.DataFrame:
    """
    Carrega dados de um fundo específico para um mês/ano.
    
    Para anos <= 2020: Baixa o arquivo anual do HIST e faz cache por ano
    Para anos > 2020: Baixa o arquivo mensal e faz cache por mês
    """
    
    caminho_cache = _caminho_cache_mes(ano, mes)
    
    # Se já temos em cache, retorna direto
    if os.path.exists(caminho_cache):
        print(f"Lendo do cache: {ano}-{mes:02d}")
        df_mes_completo = pd.read_parquet(caminho_cache)
        return df_mes_completo[
            df_mes_completo["CNPJ_FUNDO"] == cnpj
        ].reset_index(drop=True)
    
    # Determina a estratégia de download baseada no ano
    if ano <= 2020:
        return _carregar_dados_historicos(ano, mes, cnpj)
    else:
        return _carregar_dados_recentes(ano, mes, cnpj)


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
    else:
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


def carregar_historico_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str
) -> pd.DataFrame:
    """
    Carrega o histórico completo de um fundo entre duas datas.
    Esta é a função principal que o fundos_service.py está tentando importar.
    """
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
    
    # Coleta dados de cada mês
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
    
    # Se não encontrou dados, retorna DataFrame vazio
    if not partes:
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])
    
    # Concatena todos os meses
    df_completo = pd.concat(partes, ignore_index=True)
    
    # Remove duplicatas
    df_completo = df_completo.drop_duplicates(subset=["DT_COMPTC"])
    
    # Ordena por data
    df_completo = df_completo.sort_values("DT_COMPTC")
    
    return df_completo

def encontrar_primeira_cota(cnpj: str) -> pd.DataFrame:
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
                        return df_ano.sort_values("DT_COMPTC").head(1)
        
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
                    return df_mes.sort_values("DT_COMPTC").head(1)
            
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
            chunks.append(chunk_filtrado[["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]])
    
    if chunks:
        return pd.concat(chunks, ignore_index=True)
    
    return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])


def carregar_historico_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str
) -> pd.DataFrame:
    """
    Carrega o histórico completo de um fundo entre duas datas.
    
    Se data_inicial for '0000-01-01', busca desde a primeira cota disponível.
    """
    # Verifica se é período "Desde o Início"
    if data_inicial == "0000-01-01":
        return carregar_desde_inicio(cnpj, data_final)
    
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
    
    df_completo = pd.concat(partes, ignore_index=True)
    df_completo = df_completo.drop_duplicates(subset=["DT_COMPTC"])
    df_completo = df_completo.sort_values("DT_COMPTC")
    
    return df_completo


def carregar_desde_inicio(cnpj: str, data_final: str) -> pd.DataFrame:
    """
    Carrega todos os dados do fundo desde sua primeira cota até a data final.
    
    Estratégia otimizada:
    1. Primeiro encontra a data da primeira cota
    2. Depois carrega apenas do período necessário
    """
    print(f"\n=== CARREGANDO HISTÓRICO COMPLETO DO FUNDO {cnpj} ===")
    
    # Passo 1: Encontra a primeira cota
    df_primeira = encontrar_primeira_cota(cnpj)
    
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
    
    df_completo = pd.concat(partes, ignore_index=True)
    df_completo = df_completo.drop_duplicates(subset=["DT_COMPTC"])
    df_completo = df_completo.sort_values("DT_COMPTC")
    
    print(f"✅ Total de {len(df_completo)} registros carregados")
    
    return df_completo