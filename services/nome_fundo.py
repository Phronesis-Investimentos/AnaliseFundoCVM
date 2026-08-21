import io
import os
import zipfile

import pandas as pd
import requests

from utils.formatadores import formatar_cnpj


URL_REGISTRO_CLASSES = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
)
CACHE_CADASTRO_CLASSES = os.path.join("cache", "cadastro_classes.parquet")
COLUNAS_CADASTRO_CLASSES = [
    "CNPJ_Classe",
    "Denominacao_Social",
    "Classificacao",
    "CNPJ_FUNDO",
    "DENOM_SOCIAL",
]


def _carregar_cache() -> pd.DataFrame | None:
    """Retorna o último cadastro válido salvo localmente, se houver."""
    if not os.path.exists(CACHE_CADASTRO_CLASSES):
        return None
    try:
        cadastro = pd.read_parquet(CACHE_CADASTRO_CLASSES)
        if set(COLUNAS_CADASTRO_CLASSES).issubset(cadastro.columns):
            print("Cadastro de classes carregado do cache local.")
            return cadastro[COLUNAS_CADASTRO_CLASSES]
    except Exception as erro:
        print(f"Não foi possível ler o cache do cadastro de classes: {erro}")
    return None


def carregar_depara_fundos() -> pd.DataFrame:
    """Carrega o de-para de classes elegíveis do cadastro oficial da CVM.

    A classificação pertence à classe, mas os arquivos diários atualmente
    usam ``CNPJ_FUNDO``. Por isso, o ID de registro faz o vínculo com
    ``registro_fundo.csv`` e fornece a chave técnica usada nas cotas.
    """
    cache = _carregar_cache()
    if cache is not None:
        return cache

    print("Carregando cadastro de classes de fundos...")
    # Não herda proxies inválidos do ambiente (por exemplo, 127.0.0.1:9).
    # A leitura tem prazo curto para não impedir a inicialização do site.
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(URL_REGISTRO_CLASSES, timeout=(10, 45))
        response.raise_for_status()
    except requests.RequestException as erro:
        print(f"Cadastro de classes indisponível: {erro}")
        print("O site iniciará sem a lista de fundos até que o cadastro possa ser carregado.")
        return pd.DataFrame(columns=COLUNAS_CADASTRO_CLASSES)

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        with zip_file.open("registro_classe.csv") as csv:
            classes = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                dtype=str,
                usecols=[
                    "ID_Registro_Fundo",
                    "CNPJ_Classe",
                    "Denominacao_Social",
                    "Situacao",
                    "Classificacao",
                ],
            )

        with zip_file.open("registro_fundo.csv") as csv:
            fundos = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                dtype=str,
                usecols=["ID_Registro_Fundo", "CNPJ_Fundo"],
            )

    classes = classes[
        (classes["Situacao"].str.strip() == "Em Funcionamento Normal")
        & (classes["Classificacao"].str.strip().isin(["Ações", "Multimercado", ""]))
    ].copy()

    df = classes.merge(fundos, on="ID_Registro_Fundo", how="inner")
    df["CNPJ_Classe"] = df["CNPJ_Classe"].str.strip()
    df["CNPJ_Fundo"] = df["CNPJ_Fundo"].str.strip()
    df["Denominacao_Social"] = df["Denominacao_Social"].str.strip()
    df["Classificacao"] = df["Classificacao"].str.strip()
    df = df.dropna(subset=["CNPJ_Classe", "CNPJ_Fundo", "Denominacao_Social"])
    df = df.drop_duplicates(subset=["CNPJ_Fundo"])

    # Aliases compatíveis com as APIs e serviços atuais.
    df["CNPJ_FUNDO"] = df["CNPJ_Fundo"].map(formatar_cnpj)
    df["DENOM_SOCIAL"] = df["Denominacao_Social"]

    cadastro = df[COLUNAS_CADASTRO_CLASSES].reset_index(drop=True)
    try:
        os.makedirs(os.path.dirname(CACHE_CADASTRO_CLASSES), exist_ok=True)
        cadastro.to_parquet(CACHE_CADASTRO_CLASSES, index=False)
    except Exception as erro:
        print(f"Não foi possível salvar o cache do cadastro de classes: {erro}")
    return cadastro
