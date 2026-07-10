import io
import zipfile
from datetime import datetime
import os

import pandas as pd
import requests

URL_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"

session = requests.Session()

CACHE_DIR = "cache_cvm"

def _caminho_cache_mes(ano: int, mes: int) -> str:

    os.makedirs(CACHE_DIR, exist_ok=True)

    return os.path.join(CACHE_DIR, f"{ano}{mes:02d}.parquet")


def carregar_dataframe(ano: int, mes: int, cnpj: str) -> pd.DataFrame:

    caminho_cache = _caminho_cache_mes(ano, mes)

    # Se já baixamos e processamos esse mês inteiro antes, lê do disco
    if os.path.exists(caminho_cache):

        print(f"Lendo do cache: {ano}-{mes:02d}")

        df_mes_completo = pd.read_parquet(caminho_cache)

        return df_mes_completo[
            df_mes_completo["CNPJ_FUNDO"] == cnpj
        ].reset_index(drop=True)

    arquivo = f"inf_diario_fi_{ano}{mes:02d}.zip"
    url = f"{URL_BASE}/{arquivo}"

    print(f"Baixando {ano}-{mes:02d}")

    try:
        response = session.get(url, timeout=(10, 300))
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ao baixar {arquivo}: {e}")
        return pd.DataFrame(columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"])

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:

        nome_csv = zip_file.namelist()[0]

        with zip_file.open(nome_csv) as csv:

            cabecalho = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                nrows=0
            )

            if "CNPJ_FUNDO" in cabecalho.columns:
                coluna_cnpj = "CNPJ_FUNDO"
            elif "CNPJ_FUNDO_CLASSE" in cabecalho.columns:
                coluna_cnpj = "CNPJ_FUNDO_CLASSE"
            else:
                raise ValueError("Coluna de CNPJ não encontrada.")

            csv.seek(0)

            leitor = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                usecols=[coluna_cnpj, "DT_COMPTC", "VL_QUOTA"],
                chunksize=100000
            )

            partes = []

            for chunk in leitor:

                chunk.rename(
                    columns={coluna_cnpj: "CNPJ_FUNDO"},
                    inplace=True
                )

                partes.append(chunk)

                del chunk

            df_mes_completo = pd.concat(partes, ignore_index=True)

    # Salva o mês inteiro em cache (todos os fundos), pra próxima consulta
    # — de qualquer fundo nesse mês — ser instantânea
    df_mes_completo.to_parquet(caminho_cache, index=False)

    return df_mes_completo[
        df_mes_completo["CNPJ_FUNDO"] == cnpj
    ].reset_index(drop=True)


def carregar_historico_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str
) -> pd.DataFrame:

    inicio = datetime.strptime(data_inicial, "%Y-%m")
    fim = datetime.strptime(data_final, "%Y-%m")

    historico = []

    data = inicio

    while data <= fim:

        df_mes = carregar_dataframe(
            data.year,
            data.month,
            cnpj
        )

        if not df_mes.empty:
            historico.append(df_mes)

        del df_mes

        if data.month == 12:
            data = data.replace(
                year=data.year + 1,
                month=1
            )
        else:
            data = data.replace(
                month=data.month + 1
            )

    if not historico:
        return pd.DataFrame(
            columns=["CNPJ_FUNDO", "DT_COMPTC", "VL_QUOTA"]
        )

    df = pd.concat(historico, ignore_index=True)

    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    return df.sort_values("DT_COMPTC").reset_index(drop=True)


def calcular_variacao_periodo(df: pd.DataFrame) -> float:

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

    print("Cota inicial:", cota_inicial, "| Cota final:", cota_final)

    return ((cota_final / cota_inicial) - 1) * 100
