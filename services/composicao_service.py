"""Consulta as posições em cotas de fundos nos arquivos CDA públicos da CVM."""

from __future__ import annotations

import io
import math
import os
import re
import zipfile
import pandas as pd
import requests


URL_BASE_CDA = "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS"
PASTA_CACHE_CDA = os.path.join("cache", "cda")
session = requests.Session()
session.trust_env = False

COLUNAS_POSICOES = [
    "CNPJ_FUNDO_CLASSE", "DENOM_SOCIAL", "DT_COMPTC", "TP_APLIC", "QT_POS_FINAL",
    "VL_MERC_POS_FINAL", "CNPJ_FUNDO_CLASSE_COTA", "ID_SUBCLASSE",
    "NM_FUNDO_CLASSE_SUBCLASSE_COTA", "DT_CONFID_APLIC",
]


def normalizar_cnpj(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _texto_seguro(valor, padrao: str = "") -> str:
    """Converte campos textuais da CVM sem deixar NaN chegar ao JSON."""
    if valor is None or pd.isna(valor):
        return padrao
    texto = str(valor).strip()
    return texto if texto else padrao


def _numero_seguro(valor) -> float | None:
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero) or not math.isfinite(float(numero)):
        return None
    return float(numero)


def _meses_recentes(limite: int = 36):
    mes = pd.Timestamp.today().to_period("M")
    for _ in range(limite):
        yield mes
        mes -= 1


def _baixar_arquivo_cda(ano: int, mes: int) -> str | None:
    os.makedirs(PASTA_CACHE_CDA, exist_ok=True)
    caminho = os.path.join(PASTA_CACHE_CDA, f"cda_fi_{ano}{mes:02d}.zip")
    if os.path.exists(caminho) and zipfile.is_zipfile(caminho):
        return caminho

    url = f"{URL_BASE_CDA}/cda_fi_{ano}{mes:02d}.zip"
    try:
        resposta = session.get(url, timeout=(10, 90))
        if resposta.status_code == 404:
            return None
        resposta.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resposta.content)) as arquivo:
            if not any("BLC_2" in nome for nome in arquivo.namelist()):
                return None
        with open(caminho, "wb") as arquivo:
            arquivo.write(resposta.content)
        return caminho
    except (requests.RequestException, zipfile.BadZipFile) as erro:
        print(f"CDA {ano}-{mes:02d} indisponível: {erro}")
        return None


def _ler_posicoes(caminho: str, cnpjs: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê em blocos as cotas e os avisos de sigilo da competência."""
    partes = []
    confidenciais = []
    with zipfile.ZipFile(caminho) as arquivo:
        nome_bloco = next((n for n in arquivo.namelist() if "BLC_2" in n), None)
        if nome_bloco:
            with arquivo.open(nome_bloco) as csv:
                cabecalho = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0).columns
                colunas = [c for c in COLUNAS_POSICOES if c in cabecalho]
                csv.seek(0)
                if "CNPJ_FUNDO_CLASSE" in colunas:
                    for bloco in pd.read_csv(
                        csv, sep=";", encoding="latin1", dtype=str,
                        usecols=colunas, chunksize=100_000,
                    ):
                        bloco["_CNPJ_NORMALIZADO"] = bloco["CNPJ_FUNDO_CLASSE"].map(normalizar_cnpj)
                        bloco = bloco[
                            bloco["_CNPJ_NORMALIZADO"].isin(cnpjs)
                            & bloco["TP_APLIC"].astype(str).str.strip().str.casefold().eq("cotas de fundos")
                        ].copy()
                        if not bloco.empty:
                            partes.append(bloco)

        nome_confid = next((n for n in arquivo.namelist() if "CONFID" in n), None)
        if nome_confid:
            with arquivo.open(nome_confid) as csv:
                cabecalho = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0).columns
                colunas = [c for c in [
                    "CNPJ_FUNDO_CLASSE", "DT_COMPTC", "TP_APLIC", "VL_MERC_POS_FINAL", "DT_CONFID_APLIC"
                ] if c in cabecalho]
                csv.seek(0)
                if {"CNPJ_FUNDO_CLASSE", "TP_APLIC"}.issubset(colunas):
                    for bloco in pd.read_csv(
                        csv, sep=";", encoding="latin1", dtype=str,
                        usecols=colunas, chunksize=100_000,
                    ):
                        bloco["_CNPJ_NORMALIZADO"] = bloco["CNPJ_FUNDO_CLASSE"].map(normalizar_cnpj)
                        bloco = bloco[
                            bloco["_CNPJ_NORMALIZADO"].isin(cnpjs)
                            & bloco["TP_APLIC"].astype(str).str.strip().str.casefold().eq("cotas de fundos")
                        ].copy()
                        if not bloco.empty:
                            confidenciais.append(bloco)

    posicoes = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    sigilos = pd.concat(confidenciais, ignore_index=True) if confidenciais else pd.DataFrame()
    return posicoes, sigilos


def _ler_pl(caminho: str, cnpjs: set[str]) -> dict[str, dict]:
    """Lê o PL dos fundos na mesma competência das posições CDA."""
    patrimonio = {}
    with zipfile.ZipFile(caminho) as arquivo:
        nome_pl = next((n for n in arquivo.namelist() if "_PL_" in n), None)
        if not nome_pl:
            return patrimonio
        with arquivo.open(nome_pl) as csv:
            cabecalho = pd.read_csv(csv, sep=";", encoding="latin1", nrows=0).columns
            colunas = [c for c in ["CNPJ_FUNDO_CLASSE", "DT_COMPTC", "VL_PATRIM_LIQ"] if c in cabecalho]
            if len(colunas) < 3:
                return patrimonio
            csv.seek(0)
            for bloco in pd.read_csv(csv, sep=";", encoding="latin1", dtype=str, usecols=colunas, chunksize=100_000):
                bloco["_CNPJ_NORMALIZADO"] = bloco["CNPJ_FUNDO_CLASSE"].map(normalizar_cnpj)
                bloco = bloco[bloco["_CNPJ_NORMALIZADO"].isin(cnpjs)]
                for cnpj, linhas in bloco.groupby("_CNPJ_NORMALIZADO"):
                    linha = linhas.sort_values("DT_COMPTC").iloc[-1]
                    patrimonio[cnpj] = {
                        "competencia": _texto_seguro(linha.get("DT_COMPTC"))[:10] or None,
                        "valor": _numero_seguro(linha.get("VL_PATRIM_LIQ")),
                    }
    return patrimonio


def buscar_composicoes(fundos: list[dict]) -> list[dict]:
    """Busca, para cada CNPJ, a última competência com posições individualizadas."""
    cnpjs = {normalizar_cnpj(f.get("cnpj")) for f in fundos if normalizar_cnpj(f.get("cnpj"))}
    cnpjs.discard("")
    abertas: dict[str, list[dict]] = {}
    sigilo_recente: dict[str, dict] = {}
    patrimonio_por_fundo: dict[str, dict] = {}

    for mes in _meses_recentes():
        pendentes = cnpjs - set(abertas)
        if not pendentes:
            break
        caminho = _baixar_arquivo_cda(mes.year, mes.month)
        if not caminho:
            continue
        try:
            posicoes, confidenciais = _ler_posicoes(caminho, pendentes)
        except (OSError, zipfile.BadZipFile, pd.errors.ParserError, ValueError) as erro:
            print(f"Não foi possível ler o CDA {mes}: {erro}")
            continue

        if not confidenciais.empty:
            for cnpj, linhas in confidenciais.groupby("_CNPJ_NORMALIZADO"):
                linha = linhas.sort_values("DT_COMPTC").iloc[-1].to_dict()
                if cnpj not in sigilo_recente:
                    sigilo_recente[cnpj] = linha

        if not posicoes.empty:
            for cnpj, linhas in posicoes.groupby("_CNPJ_NORMALIZADO"):
                if cnpj in abertas:
                    continue
                abertas[cnpj] = linhas.to_dict(orient="records")
            try:
                patrimonio_por_fundo.update(_ler_pl(caminho, set(posicoes["_CNPJ_NORMALIZADO"])))
            except (OSError, zipfile.BadZipFile, pd.errors.ParserError, ValueError) as erro:
                print(f"Não foi possível ler o PL CDA {mes}: {erro}")

    resultados = []
    for fundo in fundos:
        cnpj = normalizar_cnpj(fundo.get("cnpj"))
        linhas = abertas.get(cnpj, [])
        posicoes = []
        competencia = None
        if linhas:
            competencia = _texto_seguro(linhas[0].get("DT_COMPTC"))[:10] or None
            for linha in linhas:
                valor = _numero_seguro(linha.get("VL_MERC_POS_FINAL"))
                quantidade = _numero_seguro(linha.get("QT_POS_FINAL"))
                posicoes.append({
                    "cnpj": _texto_seguro(linha.get("CNPJ_FUNDO_CLASSE_COTA")),
                    "id_subclasse": _texto_seguro(linha.get("ID_SUBCLASSE")),
                    "nome": _texto_seguro(linha.get("NM_FUNDO_CLASSE_SUBCLASSE_COTA"), "(nome não informado pela CVM)"),
                    "quantidade": quantidade,
                    "valor": valor,
                })
            posicoes.sort(key=lambda item: item["valor"] or 0, reverse=True)

        patrimonio = patrimonio_por_fundo.get(cnpj, {})
        pl_total = patrimonio.get("valor") if patrimonio.get("competencia") == competencia else None
        soma_posicoes = round(sum(p["valor"] for p in posicoes if p["valor"] is not None), 2)
        percentual_pl_posicoes = (
            round((pl_total / soma_posicoes - 1) * 100, 6)
            if pl_total is not None and soma_posicoes != 0 else None
        )
        if pl_total is not None and pl_total != 0:
            for posicao in posicoes:
                posicao["percentual_pl"] = (
                    round(posicao["valor"] / pl_total * 100, 6) if posicao["valor"] is not None else None
                )
        else:
            for posicao in posicoes:
                posicao["percentual_pl"] = None

        sigilo = sigilo_recente.get(cnpj)
        valor_sigilo = _numero_seguro(sigilo.get("VL_MERC_POS_FINAL")) if sigilo else None
        resultados.append({
            "cnpj": _texto_seguro(fundo.get("cnpj")),
            "nome": _texto_seguro(fundo.get("nome"), _texto_seguro(fundo.get("cnpj"))),
            "competencia": competencia,
            "pl_total": pl_total,
            "soma_posicoes": soma_posicoes if posicoes else None,
            "percentual_pl_posicoes": percentual_pl_posicoes,
            "posicoes": posicoes,
            "sigilo": ({
                "competencia": _texto_seguro(sigilo.get("DT_COMPTC"))[:10],
                "ate": _texto_seguro(sigilo.get("DT_CONFID_APLIC"))[:10],
                "valor": valor_sigilo,
            } if sigilo else None),
        })
    return resultados
