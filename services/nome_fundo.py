import io
import zipfile

import pandas as pd
import requests

from utils.formatadores import formatar_cnpj


URL_REGISTRO_CLASSES = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
)


def carregar_depara_fundos() -> pd.DataFrame:
    """Carrega o de-para de classes elegíveis do cadastro oficial da CVM.

    A classificação pertence à classe, mas os arquivos diários atualmente
    usam ``CNPJ_FUNDO``. Por isso, o ID de registro faz o vínculo com
    ``registro_fundo.csv`` e fornece a chave técnica usada nas cotas.
    """
    print("Carregando cadastro de classes de fundos...")

    response = requests.get(URL_REGISTRO_CLASSES, timeout=(10, 300))
    response.raise_for_status()

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
        & (classes["Classificacao"].str.strip().isin(["Ações", "Multimercado"]))
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

    return df[
        [
            "CNPJ_Classe",
            "Denominacao_Social",
            "Classificacao",
            "CNPJ_FUNDO",
            "DENOM_SOCIAL",
        ]
    ].reset_index(drop=True)
