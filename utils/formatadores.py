def formatar_cnpj(cnpj: str) -> str:
    """Formata um CNPJ para o padrão XX.XXX.XXX/XXXX-XX"""
    cnpj = (
        cnpj
        .replace(".", "")
        .replace("/", "")
        .replace("-", "")
    )

    return (
        cnpj[:2] + "."
        + cnpj[2:5] + "."
        + cnpj[5:8] + "/"
        + cnpj[8:12] + "-"
        + cnpj[12:]
    )