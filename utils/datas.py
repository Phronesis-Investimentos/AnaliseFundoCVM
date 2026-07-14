"""
Módulo de utilidades para manipulação de datas e períodos.

Conceitos importantes:
- Data de referência: Último dia com dados disponíveis (ontem ou último dia útil)
- Dias úteis: Aproximação considerando 252 dias úteis por ano (mercado financeiro)
- Períodos padrão: Janelas de tempo pré-definidas para análise de rentabilidade
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional


# ==========================================
# 1. FUNÇÕES BÁSICAS DE DATA
# ==========================================

def hoje() -> datetime:
    """
    Retorna a data de hoje.
    
    Exemplo:
        hoje() -> 2026-07-13 14:30:00
    """
    return datetime.today()


def ultimo_dia_mes(data: datetime) -> datetime:
    """
    Retorna o último dia do mês da data informada.
    
    Exemplos:
        ultimo_dia_mes(2026-07-13) -> 2026-07-31
        ultimo_dia_mes(2026-02-15) -> 2026-02-28
    """
    if data.month == 12:
        return datetime(data.year + 1, 1, 1) - timedelta(days=1)
    else:
        return datetime(data.year, data.month + 1, 1) - timedelta(days=1)


def primeiro_dia_mes(data: datetime) -> datetime:
    """
    Retorna o primeiro dia do mês da data informada.
    
    Exemplo:
        primeiro_dia_mes(2026-07-13) -> 2026-07-01
    """
    return data.replace(day=1)


def formatar_data_iso(data: datetime) -> str:
    """
    Formata data no padrão ISO (YYYY-MM-DD).
    
    Exemplo:
        formatar_data_iso(2026-07-13) -> "2026-07-13"
    """
    return data.strftime("%Y-%m-%d")


def formatar_data_br(data: datetime) -> str:
    """
    Formata data no padrão brasileiro.
    
    Exemplo:
        formatar_data_br(2026-07-13) -> "13/07/2026"
    """
    return data.strftime("%d/%m/%Y")


def eh_fim_de_semana(data: datetime) -> bool:
    """
    Verifica se a data é sábado ou domingo.
    
    Exemplos:
        eh_fim_de_semana(2026-07-11) -> True  (sábado)
        eh_fim_de_semana(2026-07-12) -> True  (domingo)
        eh_fim_de_semana(2026-07-13) -> False (segunda)
    """
    return data.weekday() >= 5  # 5 = sábado, 6 = domingo


# ==========================================
# 2. LÓGICA DE DATA DE REFERÊNCIA
# ==========================================

def calcular_data_referencia() -> datetime:
    """
    Calcula a data de referência para análise de fundos.
    
    NOVA REGRA DE NEGÓCIO:
    A data de referência é ONTEM (D-1), pois a CVM disponibiliza
    os dados diários e a cota de ontem já está disponível.
    
    Se ontem for fim de semana, volta para sexta-feira.
    
    EXEMPLOS:
        Hoje: 13/07/2026 (segunda-feira)
        Ontem: 12/07/2026 (domingo) -> FIM DE SEMANA
        Data referência: 10/07/2026 (sexta-feira)
        
        Hoje: 14/07/2026 (terça-feira)
        Ontem: 13/07/2026 (segunda-feira) -> DIA ÚTIL
        Data referência: 13/07/2026
        
        Hoje: 15/07/2026 (quarta-feira)
        Ontem: 14/07/2026 (terça-feira) -> DIA ÚTIL
        Data referência: 14/07/2026
    
    RESUMO: Sempre usa o último dia útil (ontem ou sexta passada).
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
    Para converter dias úteis em dias corridos, multiplicamos por 7/5
    (porque uma semana tem 7 dias corridos e 5 dias úteis).
    
    FÓRMULA:
    dias_corridos = dias_uteis × (7/5)
    
    EXEMPLOS:
        252 dias úteis × (7/5) = 353 dias corridos ≈ 12 meses
        504 dias úteis × (7/5) = 706 dias corridos ≈ 24 meses
        756 dias úteis × (7/5) = 1058 dias corridos ≈ 36 meses
    
    Args:
        data_referencia: Data final do período
        dias_uteis: Quantidade de dias úteis a subtrair
    
    Returns:
        Data inicial aproximada (sempre no dia 1 do mês)
    """
    # Converte dias úteis para dias corridos
    # 5 dias úteis = 7 dias corridos
    # Então: dias_corridos = dias_uteis * (7/5)
    dias_corridos = int(dias_uteis * 7 / 5)
    
    # Subtrai os dias corridos da data de referência
    data_inicial = data_referencia - timedelta(days=dias_corridos)
    
    # Ajusta para o primeiro dia do mês (para facilitar consultas)
    return primeiro_dia_mes(data_inicial)


# ==========================================
# 4. GERAÇÃO DE PERÍODOS PADRÃO
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
    Gera a lista de períodos padrão para análise.
    
    FLUXO:
    1. Define a data de referência (ONTEM ou último dia útil)
    2. Para cada período padrão (12m, 24m, 36m, 48m, 60m):
       - Calcula quantos dias corridos equivalem aos dias úteis
       - Subtrai da data de referência para achar a data inicial
    3. Retorna lista com todos os períodos calculados
    
    EXEMPLO DE SAÍDA (hoje: 13/07/2026 - segunda):
    Data referência: 10/07/2026 (sexta-feira, pois ontem era domingo)
    
    [
        {
            "data_inicial": "2025-07-01",
            "data_final": "2026-07-10",
            "label": "12 Meses (252 du)",
            "dias_uteis": 252,
            "dias_corridos": 374,
            "data_referencia": "10/07/2026"
        },
        {
            "data_inicial": "2024-07-01",
            "data_final": "2026-07-10",
            "label": "24 Meses (504 du)",
            "dias_uteis": 504,
            "dias_corridos": 740,
            "data_referencia": "10/07/2026"
        },
        ...
    ]
    
    Args:
        data_referencia: Opcional. Data final no formato YYYY-MM-DD.
                        Se None, calcula automaticamente (ontem/dia útil).
    
    Returns:
        Lista de dicionários com os períodos calculados
    """
    # Passo 1: Define a data de referência
    if data_referencia:
        # Se foi informada uma data, converte para datetime
        data_ref = datetime.strptime(data_referencia, "%Y-%m-%d")
    else:
        # Se não foi informada, calcula automaticamente (ONTEM ou último dia útil)
        data_ref = calcular_data_referencia()
    
    print(f"\n=== GERANDO PERÍODOS PADRÃO ===")
    print(f"Data de referência: {formatar_data_br(data_ref)}")
    print(f"Dia da semana: {data_ref.strftime('%A')}")
    print(f"Explicação: Último dia útil disponível (D-1)")
    print("-" * 50)
    
    periodos = []
    
    # Passo 2: Para cada período padrão, calcula a data inicial
    for padrao in PERIODOS_PADRAO:
        # Calcula a data inicial subtraindo os dias úteis
        data_inicial = subtrair_dias_uteis(data_ref, padrao["dias_uteis"])
        
        # Calcula quantos dias corridos realmente deu
        dias_corridos = (data_ref - data_inicial).days
        
        # Monta o label descritivo
        label = f"{padrao['nome']} ({padrao['dias_uteis']} du)"
        
        # Cria o período
        periodo = {
            "data_inicial": formatar_data_iso(data_inicial),
            "data_final": formatar_data_iso(data_ref),
            "label": label,
            "dias_uteis": padrao["dias_uteis"],
            "dias_corridos": dias_corridos,
            "descricao": padrao["descricao"],
            "data_referencia": formatar_data_br(data_ref)
        }
        
        periodos.append(periodo)
        
        # Log para debug
        print(f"{label}:")
        print(f"  Data inicial: {formatar_data_br(data_inicial)}")
        print(f"  Data final:   {formatar_data_br(data_ref)}")
        print(f"  Dias úteis:   {padrao['dias_uteis']}")
        print(f"  Dias corridos:{dias_corridos}")
        print()
    
    print("=" * 50)
    
    return periodos


# ==========================================
# 5. DEMONSTRAÇÃO / TESTE
# ==========================================

if __name__ == "__main__":
    """
    Execute este arquivo diretamente para ver a lógica funcionando:
        python utils/datas.py
    """
    
    print("\n" + "="*60)
    print("DEMONSTRAÇÃO DA LÓGICA DE PERÍODOS".center(60))
    print("="*60)
    
    # Mostra informações da data atual
    agora = hoje()
    print(f"\nHoje: {formatar_data_br(agora)} ({agora.strftime('%A')})")
    print(f"Dia do mês: {agora.day}")
    
    # Mostra ontem
    ontem = agora - timedelta(days=1)
    print(f"Ontem: {formatar_data_br(ontem)} ({ontem.strftime('%A')})")
    
    # Mostra a data de referência calculada
    data_ref = calcular_data_referencia()
    print(f"\nData de referência calculada: {formatar_data_br(data_ref)}")
    print(f"Explicação: Usamos o último dia útil (D-1),")
    print(f"pois a CVM já disponibilizou a cota de ontem.")
    
    # Gera e mostra os períodos
    periodos = gerar_periodos_padrao()
    
    print(f"\nForam gerados {len(periodos)} períodos:")
    for i, p in enumerate(periodos, 1):
        print(f"\n{i}. {p['label']}")
        print(f"   De {p['data_inicial']} até {p['data_final']}")
        print(f"   {p['dias_corridos']} dias corridos")
        print(f"   {p['descricao']}")

# ==========================================
# 6. PERÍODO "DESDE O INÍCIO"
# ==========================================

def gerar_periodo_desde_inicio(data_referencia: Optional[str] = None) -> Dict:
    """
    Gera um período especial "Desde o Início" que vai buscar
    a primeira cota disponível do fundo.
    
    Diferente dos outros períodos, aqui a data_inicial será '0000-00-00'
    ou um marcador especial que indica para o serviço de dados
    buscar desde o primeiro registro disponível.
    
    Args:
        data_referencia: Opcional. Data final no formato YYYY-MM-DD.
                        Se None, calcula automaticamente.
    
    Returns:
        Dicionário com o período "Desde o Início"
    """
    if data_referencia:
        data_ref = datetime.strptime(data_referencia, "%Y-%m-%d")
    else:
        data_ref = calcular_data_referencia()
    
    return {
        "data_inicial": "0000-01-01",  # Marcador especial: buscar desde o início
        "data_final": formatar_data_iso(data_ref),
        "label": "Desde o Início",
        "dias_uteis": None,  # Não se aplica
        "dias_corridos": None,  # Será calculado depois
        "descricao": "Rentabilidade total do fundo",
        "data_referencia": formatar_data_br(data_ref),
        "tipo": "desde_inicio"  # Marcador para identificar este período especial
    }


def gerar_todos_periodos(data_referencia: Optional[str] = None) -> List[Dict]:
    """
    Gera todos os períodos incluindo o "Desde o Início".
    
    Returns:
        Lista completa de períodos (padrão + desde o início)
    """
    # Gera os períodos padrão (12m, 24m, 36m, 48m, 60m)
    periodos = gerar_periodos_padrao(data_referencia)
    
    # Adiciona o período "Desde o Início" no começo da lista
    periodo_inicio = gerar_periodo_desde_inicio(data_referencia)
    periodos.insert(0, periodo_inicio)  # Insere no início da lista
    
    return periodos


if __name__ == "__main__":
    # ... (código existente) ...
    
    # Adicione esta parte para testar:
    print("\n" + "="*60)
    print("TODOS OS PERÍODOS (INCLUINDO DESDE O INÍCIO)".center(60))
    print("="*60)
    
    todos_periodos = gerar_todos_periodos()
    
    for i, p in enumerate(todos_periodos, 1):
        if p.get("tipo") == "desde_inicio":
            print(f"\n{i}. ⭐ {p['label']}")
            print(f"   De PRIMEIRA COTA até {p['data_final']}")
            print(f"   {p['descricao']}")
        else:
            print(f"\n{i}. {p['label']}")
            print(f"   De {p['data_inicial']} até {p['data_final']}")
            print(f"   {p['dias_corridos']} dias corridos")