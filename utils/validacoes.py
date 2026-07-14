"""
Módulo de validações e utilitários de data para o sistema de análise de fundos.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict
import pandas as pd


# ==========================================
# 1. FUNÇÕES BÁSICAS DE DATA
# ==========================================

def obter_ultimo_mes_completo() -> str:
    """
    Retorna o último mês completo no formato YYYY-MM.
    
    Exemplo:
        Hoje: 13/07/2026 -> Retorna: "2026-06"
    """
    hoje = datetime.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    return ultimo_dia_mes_anterior.strftime("%Y-%m")


def ultimo_dia_mes(data: datetime) -> datetime:
    """
    Retorna o último dia do mês da data informada.
    
    Exemplo:
        data: 13/07/2026 -> Retorna: 31/07/2026
    """
    if data.month == 12:
        return datetime(data.year + 1, 1, 1) - timedelta(days=1)
    else:
        return datetime(data.year, data.month + 1, 1) - timedelta(days=1)


def primeiro_dia_mes(data: datetime) -> datetime:
    """
    Retorna o primeiro dia do mês da data informada.
    
    Exemplo:
        data: 13/07/2026 -> Retorna: 01/07/2026
    """
    return data.replace(day=1)


def eh_fim_de_semana(data: datetime) -> bool:
    """
    Verifica se a data é sábado (5) ou domingo (6).
    
    Exemplo:
        data: 12/07/2026 (domingo) -> True
        data: 13/07/2026 (segunda) -> False
    """
    return data.weekday() >= 5


# ==========================================
# 2. DATA DE REFERÊNCIA
# ==========================================

def obter_data_referencia() -> datetime:
    """
    Retorna a data de referência para cálculos.
    
    REGRA DE NEGÓCIO:
    A data de referência é D-1 (ontem), pois a CVM disponibiliza
    os dados diários e a cota de ontem já está disponível.
    
    Se ontem for fim de semana, volta para sexta-feira.
    
    EXEMPLOS:
        Hoje: 13/07/2026 (segunda-feira)
        Ontem: 12/07/2026 (domingo) -> FIM DE SEMANA
        Retorna: 10/07/2026 (sexta-feira)
        
        Hoje: 14/07/2026 (terça-feira)
        Ontem: 13/07/2026 (segunda-feira) -> DIA ÚTIL
        Retorna: 13/07/2026
    """
    # Começa com ontem
    ontem = datetime.today() - timedelta(days=1)
    
    # Volta até encontrar um dia útil (seg-sex)
    while eh_fim_de_semana(ontem):
        ontem -= timedelta(days=1)
    
    return ontem


# ==========================================
# 3. CÁLCULO DE PERÍODOS
# ==========================================

def subtrair_dias_uteis(
    data_referencia: datetime,
    dias_uteis: int
) -> datetime:
    """
    Calcula uma data no passado baseada em dias úteis.
    
    CONCEITO:
    No mercado financeiro, 1 ano = 252 dias úteis.
    5 dias úteis = 7 dias corridos
    dias_corridos = dias_uteis * (7/5)
    
    EXEMPLOS:
        252 du * (7/5) = 353 dias corridos ≈ 12 meses
        504 du * (7/5) = 706 dias corridos ≈ 24 meses
    
    Args:
        data_referencia: Data final do período
        dias_uteis: Quantidade de dias úteis a subtrair
    
    Returns:
        Data inicial (sempre no dia 1 do mês)
    """
    # Converte dias úteis para dias corridos
    dias_corridos = int(dias_uteis * 7 / 5)
    
    # Subtrai os dias corridos
    data_inicial = data_referencia - timedelta(days=dias_corridos)
    
    # Ajusta para o primeiro dia do mês
    return primeiro_dia_mes(data_inicial)


# ==========================================
# 4. PERÍODOS PADRÃO
# ==========================================

# Definição dos períodos padrão do mercado financeiro
PERIODOS_PADRAO = [
    {
        "nome": "12 Meses",
        "dias_uteis": 252,
        "descricao": "1 ano de pregão"
    },
    {
        "nome": "24 Meses", 
        "dias_uteis": 504,
        "descricao": "2 anos de pregão"
    },
    {
        "nome": "36 Meses",
        "dias_uteis": 756,
        "descricao": "3 anos de pregão"
    },
    {
        "nome": "48 Meses",
        "dias_uteis": 1008,
        "descricao": "4 anos de pregão"
    },
    {
        "nome": "60 Meses",
        "dias_uteis": 1260,
        "descricao": "5 anos de pregão"
    }
]


def gerar_periodos_padrao(data_referencia: Optional[str] = None) -> List[Dict]:
    """
    Gera períodos padrão baseados em dias úteis.
    
    Períodos:
    - 12 meses (252 dias úteis)
    - 24 meses (504 dias úteis)
    - 36 meses (756 dias úteis)
    - 48 meses (1008 dias úteis)
    - 60 meses (1260 dias úteis)
    
    Args:
        data_referencia: Opcional. Data no formato YYYY-MM-DD.
                        Se None, usa D-1 (ontem/dia útil).
    
    Returns:
        Lista de períodos com data_inicial, data_final, label, etc.
    """
    # Define data de referência
    if data_referencia:
        data_ref = pd.to_datetime(data_referencia)
    else:
        data_ref = obter_data_referencia()
    
    periodos = []
    
    for padrao in PERIODOS_PADRAO:
        # Calcula data inicial baseada em dias úteis
        data_inicial = subtrair_dias_uteis(data_ref, padrao["dias_uteis"])
        
        # Calcula dias corridos reais
        dias_corridos = (data_ref - data_inicial).days
        
        periodos.append({
            "data_inicial": data_inicial.strftime("%Y-%m-%d"),
            "data_final": data_ref.strftime("%Y-%m-%d"),
            "label": f"{padrao['nome']} ({padrao['dias_uteis']} du)",
            "dias_uteis": padrao["dias_uteis"],
            "dias_corridos": dias_corridos,
            "descricao": padrao["descricao"],
            "data_referencia": data_ref.strftime("%d/%m/%Y"),
            "tipo": "padrao"
        })
    
    return periodos


def gerar_periodo_desde_inicio(data_referencia: Optional[str] = None) -> Dict:
    """
    Gera o período especial "Desde o Início".
    
    A data_inicial será "0000-01-01" como marcador para o serviço
    buscar desde a primeira cota disponível do fundo.
    
    Args:
        data_referencia: Opcional. Data final.
    
    Returns:
        Dicionário com o período "Desde o Início"
    """
    if data_referencia:
        data_ref = pd.to_datetime(data_referencia)
    else:
        data_ref = obter_data_referencia()
    
    return {
        "data_inicial": "0000-01-01",  # Marcador especial
        "data_final": data_ref.strftime("%Y-%m-%d"),
        "label": "Desde o Início",
        "dias_uteis": None,
        "dias_corridos": None,
        "descricao": "Rentabilidade total do fundo",
        "data_referencia": data_ref.strftime("%d/%m/%Y"),
        "tipo": "desde_inicio"
    }


def gerar_todos_periodos(data_referencia: Optional[str] = None) -> List[Dict]:
    """
    Gera todos os períodos: padrão + "Desde o Início".
    
    Returns:
        Lista completa de períodos
    """
    # Períodos padrão (12m, 24m, 36m, 48m, 60m)
    periodos = gerar_periodos_padrao(data_referencia)
    
    # Adiciona "Desde o Início" no começo da lista
    periodo_inicio = gerar_periodo_desde_inicio(data_referencia)
    periodos.insert(0, periodo_inicio)
    
    return periodos


# ==========================================
# 5. VALIDAÇÕES
# ==========================================

def validar_datas_periodo(
    data_inicial: str,
    data_final: str
) -> Tuple[bool, Optional[str]]:
    """
    Valida as datas do período.
    
    Args:
        data_inicial: Data inicial (YYYY-MM-DD ou YYYY-MM)
        data_final: Data final (YYYY-MM-DD ou YYYY-MM)
    
    Returns:
        Tupla (válido, mensagem_erro)
    """
    # Permite o marcador especial "0000-01-01" para "Desde o Início"
    if data_inicial == "0000-01-01":
        if not data_final:
            return False, "Informe a data final"
        return True, None
    
    if not data_inicial or not data_final:
        return False, "Informe data inicial e data final"
    
    # Converte para datetime para validação
    try:
        # Adiciona dia 01 se for apenas ano-mês
        if len(data_inicial) == 7:  # Formato YYYY-MM
            data_inicial = f"{data_inicial}-01"
        if len(data_final) == 7:  # Formato YYYY-MM
            # Último dia do mês
            ano, mes = map(int, data_final.split('-'))
            data_final = ultimo_dia_mes(datetime(ano, mes, 1)).strftime("%Y-%m-%d")
        
        inicio = pd.to_datetime(data_inicial)
        fim = pd.to_datetime(data_final)
        
        if inicio > fim:
            return False, "Data inicial não pode ser maior que a data final"
        
        # Verifica se a data final não está no futuro
        hoje = datetime.today()
        if fim > hoje:
            return False, "Data final não pode ser no futuro"
            
    except Exception as e:
        return False, f"Formato de data inválido: {str(e)}"
    
    return True, None


def validar_dados_variacao(dados: dict) -> Tuple[bool, Optional[str]]:
    """
    Valida os dados para cálculo de variação de um fundo.
    """
    cnpj = dados.get("cnpj")
    data_inicial = dados.get("data_inicial")
    data_final = dados.get("data_final")
    
    if not cnpj or not data_inicial or not data_final:
        return False, "Informe CNPJ, data inicial e data final"
    
    return validar_datas_periodo(data_inicial, data_final)


def validar_dados_comparacao(dados: dict) -> Tuple[bool, Optional[str]]:
    """
    Valida os dados para comparação de múltiplos fundos.
    """
    fundos = dados.get("fundos")
    periodos = dados.get("periodos")
    
    if not fundos:
        return False, "Adicione ao menos um fundo"
    
    if not periodos:
        return False, "Adicione ao menos um período"
    
    for periodo in periodos:
        # Para "Desde o Início", só precisa validar data_final
        if periodo.get("tipo") == "desde_inicio":
            if not periodo.get("data_final"):
                return False, "Data final é obrigatória para 'Desde o Início'"
            continue
        
        # Para períodos normais, valida ambas as datas
        valido, erro = validar_datas_periodo(
            periodo.get("data_inicial"),
            periodo.get("data_final")
        )
        if not valido:
            return False, erro
    
    return True, None