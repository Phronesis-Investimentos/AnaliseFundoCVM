import numpy as np
import pandas as pd


def calcular_volatilidade_periodo(
    df: pd.DataFrame,
    anualizar: bool = True,
    dias_uteis_ano: int = 252
) -> float:
    if df.empty or len(df) < 2:
        return 0.0

    df = df.copy()
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"])

    df = (
        df.sort_values("DT_COMPTC")
          .drop_duplicates(subset=["DT_COMPTC"])
          .reset_index(drop=True)
    )

    # Cota nula ou <= 0 quebra o cálculo de retorno percentual (gera inf/-inf
    # quando a cota anterior é 0, ou distorce o desvio padrão). Trata como
    # dado inválido e remove essas linhas antes do pct_change, em vez de
    # deixar propagar inf/nan até o resultado final.
    df["VL_QUOTA"] = pd.to_numeric(df["VL_QUOTA"], errors="coerce")
    df = df[df["VL_QUOTA"] > 0]

    if len(df) < 2:
        return 0.0

    retornos = df["VL_QUOTA"].pct_change().dropna()

    # Remove eventuais infinitos residuais (defesa extra) antes do std.
    retornos = retornos[np.isfinite(retornos)]

    if retornos.empty or len(retornos) < 2:
        return 0.0

    desvio_padrao = retornos.std(ddof=1)

    if anualizar:
        desvio_padrao = desvio_padrao * np.sqrt(dias_uteis_ano)

    resultado = round(desvio_padrao * 100, 2)

    # Última barreira: nunca devolver inf/nan pro front-end (quebraria o
    # JSON.parse no navegador, já que Infinity/NaN não são JSON válido).
    if not np.isfinite(resultado):
        return 0.0

    return resultado