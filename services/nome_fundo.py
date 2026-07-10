import io
import zipfile
import pandas as pd
import requests


URL_CADASTRO = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi_hist.zip"
)


def carregar_depara_fundos() -> pd.DataFrame:

    print("Carregando cadastro de fundos...")


    response = requests.get(
        URL_CADASTRO,
        timeout=(10, 300)
    )

    response.raise_for_status()


    with zipfile.ZipFile(
        io.BytesIO(response.content)
    ) as zip_file:


        arquivo = "cad_fi_hist_denom_social.csv"


        with zip_file.open(arquivo) as csv:


            df = pd.read_csv(
                csv,
                sep=";",
                encoding="latin1",
                dtype=str
            )


    # pega somente fundos com nome atual
    df = df[
        df["DT_FIM_DENOM_SOCIAL"].isna()
        |
        (df["DT_FIM_DENOM_SOCIAL"].str.strip() == "")
    ]


    # mantém apenas as colunas necessárias

    df = df[
        [
            "CNPJ_FUNDO",
            "DENOM_SOCIAL"
        ]
    ]


    # remove espaços

    df["CNPJ_FUNDO"] = (
        df["CNPJ_FUNDO"]
        .str.strip()
    )


    df["DENOM_SOCIAL"] = (
        df["DENOM_SOCIAL"]
        .str.strip()
    )


    return df.reset_index(drop=True)