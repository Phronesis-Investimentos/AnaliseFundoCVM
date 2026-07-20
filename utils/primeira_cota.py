import io
import zipfile
from datetime import datetime

import pandas as pd
import requests

from services.nome_fundo import carregar_depara_fundos

URL_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
URL_BASE_HIST = f"{URL_BASE}/HIST"

session = requests.Session()


def fundos_validos_junho_2026():
    """
    Retorna um DataFrame com:
        CNPJ_FUNDO
        NR_COTST

    Somente fundos de Ações ou Multimercado, em funcionamento normal, que
    em junho/2026 possuem NR_COTST > 10.
    """

    url = f"{URL_BASE}/inf_diario_fi_202606.zip"

    r = session.get(url, timeout=(10, 300))
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        with z.open(z.namelist()[0]) as csv:

            cab = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0)

            if "CNPJ_FUNDO" in cab.columns:
                coluna = "CNPJ_FUNDO"
            else:
                coluna = "CNPJ_FUNDO_CLASSE"

            csv.seek(0)

            df = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                usecols=[coluna, "NR_COTST"],
            )

    df.rename(columns={coluna: "CNPJ_FUNDO"}, inplace=True)
    df["CNPJ_FUNDO"] = df["CNPJ_FUNDO"].astype(str).str.strip()
    df["NR_COTST"] = pd.to_numeric(df["NR_COTST"], errors="coerce")

    df = (
        df.groupby("CNPJ_FUNDO", as_index=False)["NR_COTST"]
          .max()
    )

    df = df[df["NR_COTST"] > 10]

    cnpjs_elegiveis = carregar_depara_fundos()["CNPJ_FUNDO"]
    df = df[df["CNPJ_FUNDO"].isin(cnpjs_elegiveis)].reset_index(drop=True)

    print(f"Fundos elegíveis: {len(df):,}")

    return df

def primeira_cota_fundos(df_validos):
    """
    Retorna:

    CNPJ_FUNDO
    DT_COMPTC
    VL_QUOTA
    NR_COTST

    onde NR_COTST é o de junho/2026.
    """

    cotistas = dict(
        zip(df_validos["CNPJ_FUNDO"], df_validos["NR_COTST"])
    )

    faltam = set(cotistas.keys())

    resultado = []

    ano_atual = datetime.today().year

    # ---------- HIST ----------
    for ano in range(2000, 2021):

        if not faltam:
            break

        print(f"Processando HIST {ano}")

        url = f"{URL_BASE_HIST}/inf_diario_fi_{ano}.zip"

        try:
            r = session.get(url, timeout=(10, 600))
            r.raise_for_status()
        except:
            continue

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open(z.namelist()[0]) as csv:

                cab = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0)

                if "CNPJ_FUNDO" in cab.columns:
                    coluna = "CNPJ_FUNDO"
                else:
                    coluna = "CNPJ_FUNDO_CLASSE"

                csv.seek(0)

                for chunk in pd.read_csv(
                    csv,
                    sep=";",
                    encoding="latin1",
                    chunksize=200000,
                    parse_dates=["DT_COMPTC"],
                    usecols=[coluna, "DT_COMPTC", "VL_QUOTA"],
                ):

                    chunk = chunk[
                        chunk[coluna].isin(faltam)
                    ]

                    if chunk.empty:
                        continue

                    chunk.rename(
                        columns={coluna: "CNPJ_FUNDO"},
                        inplace=True
                    )

                    chunk.sort_values("DT_COMPTC", inplace=True)

                    for cnpj, grupo in chunk.groupby("CNPJ_FUNDO"):

                        if cnpj not in faltam:
                            continue

                        linha = grupo.iloc[0]

                        resultado.append({
                            "CNPJ_FUNDO": cnpj,
                            "DT_COMPTC": linha["DT_COMPTC"],
                            "VL_QUOTA": linha["VL_QUOTA"],
                            "NR_COTST": cotistas[cnpj],
                        })

                        faltam.remove(cnpj)

    # ---------- MENSAIS ----------
    for ano in range(2021, ano_atual + 1):

        if not faltam:
            break

        for mes in range(1, 13):

            if not faltam:
                break

            print(f"Processando {ano}-{mes:02d}")

            url = f"{URL_BASE}/inf_diario_fi_{ano}{mes:02d}.zip"

            try:
                r = session.get(url, timeout=(10, 300))
                r.raise_for_status()
            except:
                continue

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                with z.open(z.namelist()[0]) as csv:

                    cab = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0)

                    if "CNPJ_FUNDO" in cab.columns:
                        coluna = "CNPJ_FUNDO"
                    else:
                        coluna = "CNPJ_FUNDO_CLASSE"

                    csv.seek(0)

                    for chunk in pd.read_csv(
                        csv,
                        sep=";",
                        encoding="latin1",
                        chunksize=200000,
                        parse_dates=["DT_COMPTC"],
                        usecols=[coluna, "DT_COMPTC", "VL_QUOTA"],
                    ):

                        chunk = chunk[
                            chunk[coluna].isin(faltam)
                        ]

                        if chunk.empty:
                            continue

                        chunk.rename(
                            columns={coluna: "CNPJ_FUNDO"},
                            inplace=True
                        )

                        chunk.sort_values("DT_COMPTC", inplace=True)

                        for cnpj, grupo in chunk.groupby("CNPJ_FUNDO"):

                            if cnpj not in faltam:
                                continue

                            linha = grupo.iloc[0]

                            resultado.append({
                                "CNPJ_FUNDO": cnpj,
                                "DT_COMPTC": linha["DT_COMPTC"],
                                "VL_QUOTA": linha["VL_QUOTA"],
                                "NR_COTST": cotistas[cnpj],
                            })

                            faltam.remove(cnpj)

    return (
        pd.DataFrame(resultado)
        .sort_values("DT_COMPTC")
        .reset_index(drop=True)
    )
