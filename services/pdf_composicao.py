"""Diagramação do relatório com medidas reais das fontes PDF padrão."""

from datetime import datetime
from io import BytesIO
from services.pdf_fontes import LARGURAS


def montar_pdf(resultados):
    largura, altura, margem = 842, 595, 32
    util = largura - 2 * margem
    larguras = [260, 110, 105, 95, 135, 73]
    xs = [margem]
    for medida in larguras:
        xs.append(xs[-1] + medida)
    paginas, comandos = [], []
    y = 0
    vinho, cinza = '0.40 0.08 0.18', '0.36 0.39 0.43'

    def codificar(valor):
        return str(valor or '').replace('\u2212', '-').encode('cp1252', errors='replace').decode('latin1')

    def medir(valor, tamanho=9, bold=False):
        fonte = LARGURAS['Helvetica-Bold' if bold else 'Helvetica']
        return sum(fonte.get(c, 556) for c in codificar(valor)) * tamanho / 1000

    def quebrar(valor, limite, tamanho=9, bold=False):
        linhas, atual = [], ''
        for palavra in str(valor or '-').split():
            candidato = f'{atual} {palavra}'.strip()
            if atual and medir(candidato, tamanho, bold) > limite:
                linhas.append(atual)
                atual = ''
            while medir(palavra, tamanho, bold) > limite:
                corte = 1
                while corte < len(palavra) and medir(palavra[:corte+1], tamanho, bold) <= limite:
                    corte += 1
                linhas.append(palavra[:corte])
                palavra = palavra[corte:]
            atual = f'{atual} {palavra}'.strip()
        if atual:
            linhas.append(atual)
        return linhas or ['-']

    def texto(x, base, valor, tamanho=9, bold=False, cor='0.12 0.14 0.17', direita=False):
        if direita:
            x -= medir(valor, tamanho, bold)
        literal = codificar(valor).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        comandos.append(f"BT /{'F2' if bold else 'F1'} {tamanho} Tf {cor} rg 1 0 0 1 {x:.2f} {base:.2f} Tm ({literal}) Tj ET")

    def retangulo(x, topo, w, h, cor):
        comandos.append(f'q {cor} rg {x} {topo-h} {w} {h} re f Q')

    def linha(base):
        comandos.append(f'q 0.87 0.89 0.91 RG 0.4 w {margem} {base} m {largura-margem} {base} l S Q')

    def numero(valor, casas=2, moeda=False):
        if not isinstance(valor, (float, int)):
            return '-'
        fmt = f'{valor:,.{casas}f}'.replace(',', '#').replace('.', ',').replace('#', '.')
        if casas == 4:
            fmt = fmt.rstrip('0').rstrip(',')
        return ('R$ ' if moeda else '') + fmt

    def data_br(valor):
        try:
            return datetime.strptime(valor, '%Y-%m-%d').strftime('%d/%m/%Y')
        except (TypeError, ValueError):
            return 'não disponível'

    def fechar_pagina():
        if comandos:
            linha(32)
            texto(margem, 18, 'Fonte: CVM | Composição de fundos', 8, cor=cinza)
            texto(largura-margem, 18, f'Página {len(paginas)+1}', 8, cor=cinza, direita=True)
            paginas.append('\n'.join(comandos).encode('latin1'))

    def nova_pagina(fundo, continuacao=False):
        nonlocal comandos, y
        fechar_pagina()
        comandos = []
        texto(margem, altura-30, 'COMPOSIÇÃO DE FUNDOS', 9, True, vinho)
        texto(largura-margem, altura-30, f"Gerado em {datetime.now():%d/%m/%Y}", 8, cor=cinza, direita=True)
        y = altura-58
        titulo = fundo.get('nome') or fundo.get('cnpj') or 'Fundo'
        for parte in quebrar(titulo, util, 13, True):
            texto(margem, y, parte, 13, True)
            y -= 17
        meta = f"CNPJ {fundo.get('cnpj', '-')}   |   Carteira de {data_br(fundo.get('competencia'))}"
        if continuacao:
            meta += '   |   Continuação'
        texto(margem, y-1, meta, 9, cor=cinza)
        y -= 22
        if not continuacao:
            cartoes = [('PL TOTAL DO FOF', fundo.get('pl_total')),
                       ('POSIÇÕES EM FUNDOS', fundo.get('soma_posicoes')),
                       ('PL/POSIÇÕES - 1', fundo.get('percentual_pl_posicoes'))]
            w = (util-20)/3
            for i, (rotulo, valor) in enumerate(cartoes):
                x = margem+i*(w+10)
                retangulo(x, y, w, 52, '0.96 0.95 0.96')
                texto(x+12, y-16, rotulo, 8, True, cinza)
                texto(x+12, y-36, (numero(valor)+'%' if valor is not None else '-') if i == 2 else numero(valor, moeda=True), 13, True, vinho)
            y -= 68
        # Preferência do usuário: cabeçalho das colunas só na primeira página.
        if not paginas:
            retangulo(margem, y, util, 30, vinho)
            titulos = ['Fundo investido', 'CNPJ', 'Subclasse', 'Quantidade', 'Valor de mercado (R$)', '% do PL']
            for i, titulo_coluna in enumerate(titulos):
                texto(xs[i+1]-9 if i >= 3 else xs[i]+9, y-19, titulo_coluna, 8, True, '1 1 1', i >= 3)
            y -= 30

    for fundo in resultados:
        nova_pagina(fundo)
        posicoes = fundo.get('posicoes') or []
        if not posicoes:
            aviso = 'Nenhuma posição individualizada disponível para este fundo.'
            if fundo.get('sigilo'):
                aviso += f" Registro sob sigilo na competência {data_br(fundo['sigilo'].get('competencia'))}."
            for parte in quebrar(aviso, util, 10):
                texto(margem, y-15, parte, 10, cor=cinza)
                y -= 15
        for indice, posicao in enumerate(posicoes):
            percentual = posicao.get('percentual_pl')
            valores = [posicao.get('nome'), posicao.get('cnpj'), posicao.get('id_subclasse'),
                       numero(posicao.get('quantidade'), 4), numero(posicao.get('valor'), moeda=True),
                       numero(percentual)+'%' if isinstance(percentual, (float, int)) else '-']
            tamanhos = [9.5, 8.5, 8, 9, 9.5, 10]
            celulas = [quebrar(v, larguras[i]-18, tamanhos[i], i == 5) for i, v in enumerate(valores)]
            h = max(34, max(map(len, celulas))*12+18)
            reserva = 42 if indice == len(posicoes)-1 and fundo.get('percentual_pl_posicoes') is not None else 0
            if y-h-reserva < 45:
                nova_pagina(fundo, continuacao=True)
            if indice % 2 == 0:
                retangulo(margem, y, util, h, '0.97 0.98 0.99')
            for i, partes in enumerate(celulas):
                for j, parte in enumerate(partes):
                    texto(xs[i+1]-9 if i >= 3 else xs[i]+9, y-17-j*12, parte,
                          tamanhos[i], i == 5, vinho if i == 5 else '0.12 0.14 0.17', i >= 3)
            y -= h
            linha(y)
        if fundo.get('percentual_pl_posicoes') is not None:
            if y-38 < 45:
                nova_pagina(fundo, continuacao=True)
            retangulo(margem, y, util, 38, '0.95 0.91 0.93')
            texto(margem+9, y-23, 'PL/POSIÇÕES - 1', 10, True, vinho)
            texto(xs[6]-9, y-23, numero(fundo['percentual_pl_posicoes'])+'%', 10, True, vinho, True)
    fechar_pagina()

    objetos = [b'<< /Type /Catalog /Pages 2 0 R >>', b'']
    referencias = []
    for i, conteudo in enumerate(paginas):
        pagina_id = 3+i*2
        referencias.append(f'{pagina_id} 0 R')
        objetos.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura} {altura}] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> /F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> >> >> /Contents {pagina_id+1} 0 R >>'.encode('ascii'))
        objetos.append(b'<< /Length '+str(len(conteudo)).encode('ascii')+b' >>\nstream\n'+conteudo+b'\nendstream')
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(referencias)}] /Count {len(paginas)} >>".encode('ascii')
    saida = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, objeto in enumerate(objetos, 1):
        offsets.append(len(saida))
        saida.extend(f'{i} 0 obj\n'.encode('ascii')+objeto+b'\nendobj\n')
    inicio_xref = len(saida)
    saida.extend(f'xref\n0 {len(objetos)+1}\n0000000000 65535 f \n'.encode('ascii'))
    for deslocamento in offsets:
        saida.extend(f'{deslocamento:010d} 00000 n \n'.encode('ascii'))
    saida.extend(f'trailer\n<< /Size {len(objetos)+1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF'.encode('ascii'))
    return BytesIO(saida)
