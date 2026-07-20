from typing import List, Dict, Any, Iterable, Optional
import pandas as pd
from services.cvm import (
    carregar_historico_fundo,
    carregar_cotas_referencia_fundos,
    carregar_fundos_elegiveis_por_cotistas,
    calcular_variacao_periodo,
    filtrar_periodo
)

from services.nome_fundo import carregar_depara_fundos
from services.volatilidade import calcular_volatilidade_periodo
from utils.formatadores import formatar_cnpj
from utils.validacoes import gerar_periodos_padrao, obter_ultimo_mes_completo


PESOS_RANKING_PADRAO = {
    "12m": 0.10,
    "24m": 0.15,
    "36m": 0.50,
    "48m": 0.15,
    "60m": 0.10,
}


def _periodos_ranking(data_referencia: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Mapeia os períodos padrão para as chaves usadas pelo ranking."""
    return {
        f"{indice * 12}m": periodo
        for indice, periodo in enumerate(gerar_periodos_padrao(data_referencia), start=1)
    }


def _possui_cotas_referencia(
    df: pd.DataFrame,
    periodos: Iterable[Dict[str, str]]
) -> bool:
    """Exige uma cota de fechamento em cada mês inicial e final."""
    if df.empty:
        return False

    cotas = pd.to_numeric(df["VL_QUOTA"], errors="coerce")
    # Cota nula, negativa ou ausente torna a rentabilidade indefinida.
    if cotas.isna().any() or (cotas <= 0).any():
        return False

    meses_disponiveis = set(df["DT_COMPTC"].dt.to_period("M"))
    for periodo in periodos:
        inicio = pd.Period(periodo["data_inicial"], freq="M")
        fim = pd.Period(periodo["data_final"], freq="M")
        if inicio not in meses_disponiveis or fim not in meses_disponiveis:
            return False
    return True


def gerar_ranking_fundos(
    pesos: Optional[Dict[str, float]] = None,
    top_n: int = 50,
    fundos: Optional[pd.DataFrame] = None,
    data_referencia: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Gera o ranking de fundos pela média ponderada de rentabilidades.

    Fundos sem cotas de fechamento para *todos* os cinco períodos são
    excluídos. Antes dos cálculos, considera somente CNPJs únicos com mais
    de 10 cotistas no último mês completo. Como o ranking considera somente
    rentabilidade, são lidos apenas os cinco meses iniciais e o mês final.
    """
    if fundos is None:

        fundos = carregar_depara_fundos()

    if top_n <= 0:
        return []
    if fundos.empty:
        return []

    pesos = PESOS_RANKING_PADRAO if pesos is None else pesos
    chaves_esperadas = set(PESOS_RANKING_PADRAO)
    if set(pesos) != chaves_esperadas:
        raise ValueError("Os pesos devem conter exatamente: 12m, 24m, 36m, 48m e 60m")
    if any(peso < 0 for peso in pesos.values()):
        raise ValueError("Os pesos não podem ser negativos")
    if abs(sum(pesos.values()) - 1) > 1e-9:
        raise ValueError("A soma dos pesos deve ser igual a 1")

    periodos = _periodos_ranking(data_referencia)
    cadastro = fundos[["CNPJ_FUNDO", "DENOM_SOCIAL"]].dropna().drop_duplicates("CNPJ_FUNDO")

    ano_elegibilidade, mes_elegibilidade = map(int, obter_ultimo_mes_completo().split("-"))
    elegiveis = carregar_fundos_elegiveis_por_cotistas(
        ano_elegibilidade, mes_elegibilidade
    )
    cadastro = cadastro[cadastro["CNPJ_FUNDO"].isin(elegiveis["CNPJ_FUNDO"])]
    if cadastro.empty:
        return []

    datas_referencia = [periodo["data_inicial"] for periodo in periodos.values()]
    datas_referencia.append(periodos["60m"]["data_final"])
    cotas_referencia = carregar_cotas_referencia_fundos(
        cadastro["CNPJ_FUNDO"].tolist(), datas_referencia
    )
    if cotas_referencia.empty:
        return []
    cotas_referencia = cotas_referencia.copy()
    cotas_referencia["DT_COMPTC"] = pd.to_datetime(cotas_referencia["DT_COMPTC"])

    resultados = []
    nomes_por_cnpj = cadastro.set_index("CNPJ_FUNDO")["DENOM_SOCIAL"]
    for cnpj, df_fundo in cotas_referencia.groupby("CNPJ_FUNDO", sort=False):
        if not _possui_cotas_referencia(df_fundo, periodos.values()):
            continue

        registro = {"nome": nomes_por_cnpj.get(cnpj, cnpj), "cnpj": cnpj}
        nota = 0.0
        for chave, periodo in periodos.items():
            meses_periodo = {
                pd.Period(periodo["data_inicial"], freq="M"),
                pd.Period(periodo["data_final"], freq="M"),
            }
            df_periodo = filtrar_periodo(
                df_fundo[df_fundo["DT_COMPTC"].dt.to_period("M").isin(meses_periodo)],
                periodo["data_inicial"], periodo["data_final"],
            )
            rentabilidade = calcular_variacao_periodo(df_periodo)
            registro[f"rentabilidade_{chave}"] = float(round(rentabilidade, 2))
            nota += (rentabilidade / 100) * pesos[chave]

        registro["_nota_ordenacao"] = float(nota)
        registro["nota_final"] = float(round(nota, 2))
        resultados.append(registro)

    resultados.sort(key=lambda registro: registro["_nota_ordenacao"], reverse=True)
    for registro in resultados:
        registro.pop("_nota_ordenacao")
    return resultados[:top_n]


def calcular_volatilidade_ranking_fundo(
    cnpj: str,
    data_referencia: Optional[str] = None,
) -> Dict[str, Any]:
    """Calcula a volatilidade anualizada de um fundo nos cinco períodos do ranking.

    O ranking em si (gerar_ranking_fundos) só precisa dos fechamentos mensais
    para calcular rentabilidade, então não carrega a série diária completa.
    A volatilidade, porém, exige o histórico diário — por isso essa função é
    separada e só é chamada sob demanda (botão "Ver Volatilidade" de um fundo
    específico), evitando pesar o cálculo do ranking geral.
    """
    cnpj_formatado = formatar_cnpj(cnpj)
    periodos = _periodos_ranking(data_referencia)

    data_inicial_geral = min(periodo["data_inicial"] for periodo in periodos.values())
    data_final_geral = periodos["60m"]["data_final"]

    df = carregar_historico_fundo(cnpj_formatado, data_inicial_geral, data_final_geral)

    resultado: Dict[str, Any] = {"cnpj": cnpj_formatado}
    for chave, periodo in periodos.items():
        df_periodo = filtrar_periodo(df, periodo["data_inicial"], periodo["data_final"])
        resultado[f"volatilidade_{chave}"] = calcular_volatilidade_periodo(df_periodo)

    return resultado


def processar_variacao_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str
) -> Dict[str, Any]:
    """
    Processa o cálculo de variação (e volatilidade) para um único fundo.
    """
    cnpj_formatado = formatar_cnpj(cnpj)

    df = carregar_historico_fundo(
        cnpj_formatado,
        data_inicial,
        data_final
    )

    variacao = calcular_variacao_periodo(df)
    volatilidade = calcular_volatilidade_periodo(df)

    return {
        "cnpj": cnpj_formatado,
        "data_inicial": data_inicial,
        "data_final": data_final,
        "variacao_percentual": round(variacao, 2),
        "volatilidade_percentual": volatilidade
    }


def processar_comparacao_fundos(
    fundos: List[Dict[str, str]],
    periodos: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Processa a comparação de múltiplos fundos em múltiplos períodos.

    Suporta dois tipos de períodos:
    - normal: Períodos com data inicial e final definidas
    - desde_inicio: Período especial que busca desde a primeira cota do fundo
    """
    # Separa períodos normais do período "Desde o Início"
    periodos_normais = [p for p in periodos if p.get("tipo") != "desde_inicio"]
    periodos_inicio = [p for p in periodos if p.get("tipo") == "desde_inicio"]

    # Define o intervalo geral para otimizar downloads (apenas períodos normais)
    data_inicial_geral = None
    data_final_geral = None

    if periodos_normais:
        data_inicial_geral = min(p["data_inicial"] for p in periodos_normais)
        data_final_geral = max(p["data_final"] for p in periodos_normais)

    if periodos_inicio:
        # Se tem "Desde o Início", usa a maior data final
        data_final_inicio = max(p["data_final"] for p in periodos_inicio)
        if data_final_geral:
            data_final_geral = max(data_final_geral, data_final_inicio)
        else:
            data_final_geral = data_final_inicio

    resultado_fundos = []

    for fundo in fundos:
        cnpj = fundo.get("cnpj")
        nome = fundo.get("nome", cnpj)

        if not cnpj:
            continue

        cnpj_formatado = formatar_cnpj(cnpj)

        variacoes = []

        # ==========================================
        # Processa períodos normais (12m, 24m, 36m, 48m, 60m)
        # ==========================================
        if periodos_normais and data_inicial_geral:
            print(f"\n📊 Processando períodos normais para {nome}")

            # Carrega dados uma única vez para o intervalo geral
            df = carregar_historico_fundo(
                cnpj_formatado,
                data_inicial_geral,
                data_final_geral
            )

            for periodo in periodos_normais:
                df_periodo = filtrar_periodo(
                    df,
                    periodo["data_inicial"],
                    periodo["data_final"]
                )

                variacao = calcular_variacao_periodo(df_periodo)
                volatilidade = calcular_volatilidade_periodo(df_periodo)

                variacoes.append({
                    "data_inicial": periodo["data_inicial"],
                    "data_final": periodo["data_final"],
                    "label": periodo.get("label", ""),
                    "variacao_percentual": round(variacao, 2),
                    "volatilidade_percentual": volatilidade,
                    "tipo": "normal"
                })

        # ==========================================
        # Processa período "Desde o Início"
        # ==========================================
        for periodo in periodos_inicio:
            print(f"\n🔍 Calculando 'Desde o Início' para {nome}")

            # Carrega histórico completo do fundo
            df_completo = carregar_historico_fundo(
                cnpj_formatado,
                periodo["data_inicial"],  # "0000-01-01"
                periodo["data_final"]
            )

            if not df_completo.empty:
                # Filtra até a data final
                data_primeira_cota = df_completo["DT_COMPTC"].min()

                df_periodo = filtrar_periodo(
                    df_completo,
                    data_primeira_cota.strftime("%Y-%m-%d"),
                    periodo["data_final"]
                )

                variacao = calcular_variacao_periodo(df_periodo)
                volatilidade = calcular_volatilidade_periodo(df_periodo)

                # Calcula informações adicionais
                primeira_data = df_completo["DT_COMPTC"].min()
                ultima_data = df_completo["DT_COMPTC"].max()
                dias_totais = (pd.to_datetime(periodo["data_final"]) - primeira_data).days

                print(f"  ✅ Primeira cota: {primeira_data.strftime('%d/%m/%Y')}")
                print(f"  ✅ Última cota: {ultima_data.strftime('%d/%m/%Y')}")
                print(f"  ✅ Dias totais: {dias_totais}")
                print(f"  ✅ Variação: {variacao:.2f}%")
                print(f"  ✅ Volatilidade: {volatilidade:.2f}%")

                variacoes.append({
                    "data_inicial": primeira_data.strftime("%Y-%m-%d"),
                    "data_final": periodo["data_final"],
                    "label": "Desde o Início",
                    "variacao_percentual": round(variacao, 2),
                    "volatilidade_percentual": volatilidade,
                    "tipo": "desde_inicio",
                    "primeira_data": primeira_data.strftime("%d/%m/%Y"),
                    "dias_totais": dias_totais
                })
            else:
                print(f"  ❌ Dados não encontrados para {nome}")
                variacoes.append({
                    "data_inicial": None,
                    "data_final": periodo["data_final"],
                    "label": "Desde o Início",
                    "variacao_percentual": 0,
                    "volatilidade_percentual": 0,
                    "tipo": "desde_inicio",
                    "erro": "Dados não encontrados"
                })

        resultado_fundos.append({
            "cnpj": cnpj_formatado,
            "nome": nome,
            "variacoes": variacoes
        })
        
        periodos_processados = periodos_normais + periodos_inicio

    return {
        "periodos": periodos_processados,
        "fundos": resultado_fundos
    }