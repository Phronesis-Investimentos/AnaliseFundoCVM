import numpy as np
import pandas as pd


def calcular_volatilidade_periodo(
    df: pd.DataFrame,
    anualizar: bool = True,
    dias_uteis_ano: int = 252
) -> float:
    """
    Calcula a volatilidade (desvio padrão dos retornos) de um fundo
    para o período já filtrado.

    Passos:
    1. Ordena as cotas por data e remove duplicatas de data.
    2. Calcula os retornos diários (variação percentual entre cotas consecutivas).
    3. Calcula o desvio padrão amostral (ddof=1) desses retornos.
    4. Se anualizar=True, multiplica pela raiz quadrada do número de
       períodos no ano (padrão: 252 dias úteis).

    Args:
        df: DataFrame com colunas DT_COMPTC e VL_QUOTA, já filtrado
            pelo período desejado (ex: via filtrar_periodo).
        anualizar: Se True, retorna a volatilidade anualizada.
                   Se False, retorna a volatilidade "crua" do período
                   (na mesma frequência dos dados, geralmente diária).
        dias_uteis_ano: Fator de anualização. Use 252 para dados diários,
                        12 para mensais, 52 para semanais, etc.

    Returns:
        Volatilidade em percentual (ex: 12.34 significa 12.34%).
        Retorna 0.0 se não houver dados suficientes (menos de 2 cotas).
    """
    if df.empty or len(df) < 2:
        return 0.0

    df = df.copy()
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    # Garante uma cota por dia e ordena cronologicamente
    df = (
        df.sort_values("DT_COMPTC")
          .drop_duplicates(subset=["DT_COMPTC"])
          .reset_index(drop=True)
    )

    # Retornos percentuais entre cotas consecutivas
    retornos = df["VL_QUOTA"].pct_change().dropna()

    if retornos.empty or len(retornos) < 2:
        return 0.0

    # Desvio padrão amostral (ddof=1, conforme passo 3 da metodologia)
    desvio_padrao = retornos.std(ddof=1)

    if anualizar:
        desvio_padrao = desvio_padrao * np.sqrt(dias_uteis_ano)

    # Retorna em percentual
    return round(desvio_padrao * 100, 2)