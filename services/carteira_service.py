"""
Persistência de "Carteiras" salvas pelo usuário: um nome (ex.: "Carteira
XP") apontando para uma lista de CNPJs de fundos.

Isso NÃO guarda o resultado calculado (rentabilidade, volatilidade,
correlação etc.) — só guarda QUAIS fundos fazem parte da carteira. Toda
vez que o usuário abre uma carteira salva, o portfólio é recalculado do
zero (services.portfolio.portfolio) usando a data de hoje, então as
informações mostradas são sempre as mais recentes disponíveis.

Implementado como um arquivo JSON simples (data/carteiras.json) com lock
em memória para evitar corrida entre requisições concorrentes. Não
depende de banco de dados — se o projeto já usa algum, é só trocar as
funções `_carregar`/`_salvar` por chamadas ao banco, mantendo a mesma
assinatura pública (salvar_carteira / listar_carteiras / obter_carteira /
excluir_carteira).
"""

import json
import os
import threading
from datetime import datetime

_LOCK = threading.Lock()

_CAMINHO_ARQUIVO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "carteiras.json",
)


def _garantir_arquivo() -> None:
    os.makedirs(os.path.dirname(_CAMINHO_ARQUIVO), exist_ok=True)
    if not os.path.exists(_CAMINHO_ARQUIVO):
        with open(_CAMINHO_ARQUIVO, "w", encoding="utf-8") as arquivo:
            json.dump({}, arquivo)


def _carregar() -> dict:
    _garantir_arquivo()
    with open(_CAMINHO_ARQUIVO, "r", encoding="utf-8") as arquivo:
        try:
            return json.load(arquivo)
        except json.JSONDecodeError:
            # Arquivo vazio/corrompido — trata como se não houvesse
            # carteiras salvas ainda, em vez de quebrar a aplicação.
            return {}


def _salvar_arquivo(carteiras: dict) -> None:
    _garantir_arquivo()
    with open(_CAMINHO_ARQUIVO, "w", encoding="utf-8") as arquivo:
        json.dump(carteiras, arquivo, ensure_ascii=False, indent=2)


def salvar_carteira(nome: str, cnpjs: list[str | dict]) -> dict:
    """
    Cria (ou sobrescreve, se já existir uma carteira com esse nome) uma
    carteira salva com a lista de CNPJs informada.

    Parâmetros
    ----------
    nome : str
        Nome escolhido pelo usuário para a carteira (ex.: "Carteira XP").
        Espaços nas pontas são removidos; é usado como chave (não pode
        ser vazio).
    cnpjs : list[str]
        Lista de CNPJs dos fundos que compõem a carteira. Duplicados e
        valores vazios são descartados; a ordem original é preservada.

    Retorno
    -------
    dict
        { "nome": ..., "cnpjs": [...], "atualizado_em": "ISO 8601" }

    Lança
    -----
    ValueError
        Se `nome` ficar vazio depois do strip, ou se `cnpjs` não tiver
        nenhum CNPJ válido.
    """

    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe um nome para a carteira")

    cnpjs_normalizados = []
    vistos = set()
    fundos = []
    for item in cnpjs or []:
        if isinstance(item, dict):
            cnpj = str(item.get("cnpj", "")).strip()
            id_subclasse = item.get("id_subclasse")
            id_subclasse = str(id_subclasse).strip() if id_subclasse is not None and str(id_subclasse).strip() else None
        else:
            cnpj = str(item).strip()
            id_subclasse = None
        if cnpj and cnpj not in vistos:
            cnpjs_normalizados.append(cnpj)
            fundos.append({"cnpj": cnpj, "id_subclasse": id_subclasse})
            vistos.add(cnpj)

    if not cnpjs_normalizados:
        raise ValueError("Informe ao menos um fundo para a carteira")

    with _LOCK:
        carteiras = _carregar()
        carteiras[nome] = {
            "nome": nome,
            "cnpjs": cnpjs_normalizados,
            "fundos": fundos,
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        }
        _salvar_arquivo(carteiras)
        return carteiras[nome]


def listar_carteiras() -> list[dict]:
    """
    Lista todas as carteiras salvas (sem os CNPJs, só o resumo — usado
    pra montar a lista de "Minhas Carteiras" na tela).

    Retorno
    -------
    list[dict]
        [{ "nome": ..., "quantidade_fundos": int, "atualizado_em": ... }, ...]
        ordenado por nome (case-insensitive).
    """

    with _LOCK:
        carteiras = _carregar()

    resumo = [
        {
            "nome": carteira["nome"],
            "quantidade_fundos": len(carteira.get("cnpjs", [])),
            "atualizado_em": carteira.get("atualizado_em"),
        }
        for carteira in carteiras.values()
    ]

    return sorted(resumo, key=lambda c: c["nome"].lower())


def obter_carteira(nome: str) -> dict | None:
    """
    Retorna a carteira completa (com a lista de CNPJs) pelo nome exato.

    Retorno
    -------
    dict | None
        { "nome": ..., "cnpjs": [...], "atualizado_em": ... } ou None se
        não existir carteira com esse nome.
    """

    with _LOCK:
        carteiras = _carregar()

    return carteiras.get(nome)


def excluir_carteira(nome: str) -> bool:
    """
    Remove a carteira salva com esse nome, se existir.

    Retorno
    -------
    bool
        True se removeu, False se não existia carteira com esse nome.
    """

    with _LOCK:
        carteiras = _carregar()
        if nome not in carteiras:
            return False
        del carteiras[nome]
        _salvar_arquivo(carteiras)
        return True
