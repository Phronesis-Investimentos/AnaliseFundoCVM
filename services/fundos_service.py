from typing import List, Dict, Any
import pandas as pd
from services.cvm import (
    carregar_historico_fundo,
    calcular_variacao_periodo,
    filtrar_periodo
)
from utils.formatadores import formatar_cnpj


def processar_variacao_fundo(
    cnpj: str,
    data_inicial: str,
    data_final: str
) -> Dict[str, Any]:
    """
    Processa o cálculo de variação para um único fundo.
    """
    cnpj_formatado = formatar_cnpj(cnpj)
    
    df = carregar_historico_fundo(
        cnpj_formatado,
        data_inicial,
        data_final
    )
    
    variacao = calcular_variacao_periodo(df)
    
    return {
        "cnpj": cnpj_formatado,
        "data_inicial": data_inicial,
        "data_final": data_final,
        "variacao_percentual": round(variacao, 2)
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
                
                variacoes.append({
                    "data_inicial": periodo["data_inicial"],
                    "data_final": periodo["data_final"],
                    "label": periodo.get("label", ""),
                    "variacao_percentual": round(variacao, 2),
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
                
                # Calcula informações adicionais
                primeira_data = df_completo["DT_COMPTC"].min()
                ultima_data = df_completo["DT_COMPTC"].max()
                dias_totais = (pd.to_datetime(periodo["data_final"]) - primeira_data).days
                
                print(f"  ✅ Primeira cota: {primeira_data.strftime('%d/%m/%Y')}")
                print(f"  ✅ Última cota: {ultima_data.strftime('%d/%m/%Y')}")
                print(f"  ✅ Dias totais: {dias_totais}")
                print(f"  ✅ Variação: {variacao:.2f}%")
                
                variacoes.append({
                    "data_inicial": primeira_data.strftime("%Y-%m-%d"),
                    "data_final": periodo["data_final"],
                    "label": "Desde o Início",
                    "variacao_percentual": round(variacao, 2),
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
                    "tipo": "desde_inicio",
                    "erro": "Dados não encontrados"
                })
        
        resultado_fundos.append({
            "cnpj": cnpj_formatado,
            "nome": nome,
            "variacoes": variacoes
        })
    
    return {
        "periodos": periodos,
        "fundos": resultado_fundos
    }   