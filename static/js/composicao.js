document.addEventListener('DOMContentLoaded', () => {
    const inputLista = document.getElementById('lista_fundos_composicao');
    const inputBusca = document.getElementById('busca_composicao');
    const sugestoes = document.getElementById('sugestoes_composicao');
    const botaoBuscar = document.getElementById('btn_buscar_composicao');
    const mensagem = document.getElementById('mensagem_composicao');
    const resultado = document.getElementById('resultado_composicao');
    const cartoes = document.getElementById('cartoes_composicao');
    let composicoesAtuais = [];
    let timerBusca;

    const escapar = (valor) => String(valor ?? '').replace(/[&<>"']/g, caractere => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[caractere]));
    const dinheiro = valor => typeof valor === 'number' ? valor.toLocaleString('pt-BR', {style:'currency',currency:'BRL'}) : '—';
    const percentual = valor => typeof valor === 'number' && Number.isFinite(valor) ? valor.toLocaleString('pt-BR', {minimumFractionDigits:2,maximumFractionDigits:2}) + '%' : '—';
    const dataBR = valor => valor ? new Date(`${valor}T00:00:00`).toLocaleDateString('pt-BR') : '';

    inputBusca.addEventListener('input', () => {
        clearTimeout(timerBusca);
        const termo = inputBusca.value.trim();
        if (termo.length < 2) { sugestoes.classList.add('hidden'); return; }
        timerBusca = setTimeout(async () => {
            try {
                const resposta = await fetch(`/api/composicao/buscar-fundos?busca=${encodeURIComponent(termo)}`);
                const fundos = await resposta.json();
                sugestoes.innerHTML = '';
                fundos.forEach(fundo => {
                    const item = document.createElement('li');
                    item.innerHTML = `<button type="button" class="w-full text-left px-4 py-3 hover:bg-neon/10 transition-colors"><span class="block text-sm font-medium">${escapar(fundo.nome)}</span><span class="text-xs text-gray-500">${escapar(fundo.cnpj)}</span></button>`;
                    item.querySelector('button').addEventListener('click', () => {
                        const linhas = inputLista.value.split(/[\n;,]+/).map(l => l.trim()).filter(Boolean);
                        if (!linhas.some(l => l.replace(/\D/g, '') === fundo.cnpj.replace(/\D/g, ''))) linhas.push(fundo.cnpj);
                        inputLista.value = linhas.join('\n');
                        inputBusca.value = '';
                        sugestoes.classList.add('hidden');
                        inputLista.focus();
                    });
                    sugestoes.appendChild(item);
                });
                sugestoes.classList.toggle('hidden', fundos.length === 0);
            } catch { sugestoes.classList.add('hidden'); }
        }, 250);
    });
    document.addEventListener('click', evento => { if (!sugestoes.contains(evento.target) && evento.target !== inputBusca) sugestoes.classList.add('hidden'); });

    function renderizarFundos(fundos) {
        cartoes.innerHTML = '';
        fundos.forEach(fundo => {
            const secao = document.createElement('article');
            secao.className = 'glass-panel rounded-2xl overflow-hidden';
            const status = fundo.competencia
                ? `<p class="text-xs text-gray-500 mt-1">Composição visível em ${dataBR(fundo.competencia)}</p>`
                : fundo.sigilo
                    ? `<p class="text-sm text-amber-600 dark:text-amber-400 mt-2">A CVM mostra o valor agregado sob sigilo na competência ${dataBR(fundo.sigilo.competencia)}${fundo.sigilo.ate ? `, com divulgação prevista após ${dataBR(fundo.sigilo.ate)}.` : '.'} Abaixo está a carteira aberta mais recente, se encontrada.</p>`
                    : '<p class="text-sm text-gray-500 mt-2">Não foi localizada composição individualizada nas competências consultadas.</p>';
            const resumoPL = fundo.pl_total !== null && fundo.pl_total !== undefined
                ? `<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4"><div class="rounded-xl bg-gray-100 dark:bg-white/5 p-3"><p class="text-xs text-gray-500">PL total do FOF</p><p class="font-semibold mt-1">${dinheiro(fundo.pl_total)}</p></div><div class="rounded-xl bg-gray-100 dark:bg-white/5 p-3"><p class="text-xs text-gray-500">Soma das posições em fundos</p><p class="font-semibold mt-1">${dinheiro(fundo.soma_posicoes)}</p></div><div class="rounded-xl bg-gray-100 dark:bg-white/5 p-3"><p class="text-xs text-gray-500">PL/POSIÇÕES - 1</p><p class="font-semibold mt-1">${percentual(fundo.percentual_pl_posicoes)}</p></div></div>`
                : '';
            const linhas = (fundo.posicoes || []).map(posicao => `<tr class="border-t border-gray-200 dark:border-white/5"><td class="px-4 py-3 text-sm min-w-[260px]">${escapar(posicao.nome)}</td><td class="px-4 py-3 text-sm whitespace-nowrap">${escapar(posicao.cnpj)}</td><td class="px-4 py-3 text-sm">${escapar(posicao.id_subclasse)}</td><td class="px-4 py-3 text-sm text-right whitespace-nowrap">${typeof posicao.quantidade === 'number' ? posicao.quantidade.toLocaleString('pt-BR',{maximumFractionDigits:4}) : '—'}</td><td class="px-4 py-3 text-sm text-right whitespace-nowrap">${dinheiro(posicao.valor)}</td><td class="px-4 py-3 text-sm text-right whitespace-nowrap">${typeof posicao.percentual_pl === 'number' ? `${posicao.percentual_pl.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}%` : '—'}</td></tr>`).join('');
            const linhaDiferenca = fundo.percentual_pl_posicoes !== null && fundo.percentual_pl_posicoes !== undefined
                ? `<tr class="border-t-2 border-neon/30 bg-neon/5 font-semibold"><td class="px-4 py-3 text-sm">PL/POSIÇÕES - 1</td><td colspan="4"></td><td class="px-4 py-3 text-sm text-right whitespace-nowrap">${percentual(fundo.percentual_pl_posicoes)}</td></tr>`
                : '';
            secao.innerHTML = `<div class="p-5 sm:p-6"><h3 class="font-semibold text-lg">${escapar(fundo.nome)}</h3><p class="text-sm text-gray-500">CNPJ ${escapar(fundo.cnpj)}</p>${status}${resumoPL}</div>${linhas ? `<div class="overflow-x-auto"><table class="w-full text-left"><thead class="bg-gray-100 dark:bg-white/5 text-xs uppercase text-gray-500"><tr><th class="px-4 py-3">Fundo investido</th><th class="px-4 py-3">CNPJ investido</th><th class="px-4 py-3">Subclasse</th><th class="px-4 py-3 text-right">Quantidade</th><th class="px-4 py-3 text-right">Valor de mercado</th><th class="px-4 py-3 text-right">% do PL do FOF</th></tr></thead><tbody>${linhas}${linhaDiferenca}</tbody></table></div>` : ''}`;
            cartoes.appendChild(secao);
        });
        resultado.classList.remove('hidden');
    }

    botaoBuscar.addEventListener('click', async () => {
        const fundos = inputLista.value.split(/[\n;,]+/).map(item => item.trim()).filter(Boolean);
        mensagem.classList.add('hidden');
        if (!fundos.length) { mensagem.textContent = 'Informe ao menos um CNPJ ou nome de fundo.'; mensagem.classList.remove('hidden'); return; }
        botaoBuscar.disabled = true;
        botaoBuscar.innerHTML = '<i class="ph ph-spinner animate-spin"></i><span>Consultando arquivos da CVM…</span>';
        try {
            const resposta = await fetch('/api/composicao/buscar', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fundos})});
            const dados = await resposta.json();
            if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível consultar as composições.');
            composicoesAtuais = dados.fundos || [];
            renderizarFundos(composicoesAtuais);
            resultado.scrollIntoView({behavior:'smooth',block:'start'});
        } catch (erro) {
            mensagem.textContent = erro.message;
            mensagem.classList.remove('hidden');
        } finally {
            botaoBuscar.disabled = false;
            botaoBuscar.innerHTML = '<i class="ph ph-magnifying-glass"></i><span>Buscar última composição visível</span>';
        }
    });

    async function exportar(formato) {
        if (!composicoesAtuais.length) return;
        const rota = `/api/composicao/exportar/${formato}`;
        const resposta = await fetch(rota, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fundos:composicoesAtuais})});
        if (!resposta.ok) { const erro = await resposta.json(); throw new Error(erro.erro || 'Falha na exportação.'); }
        const blob = await resposta.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `composicao_fundos_cvm.${formato === 'excel' ? 'xlsx' : 'pdf'}`;
        link.click();
        URL.revokeObjectURL(link.href);
    }
    document.getElementById('btn_exportar_pdf_composicao').addEventListener('click', () => exportar('pdf').catch(erro => alert(erro.message)));
    document.getElementById('btn_exportar_excel_composicao').addEventListener('click', () => exportar('excel').catch(erro => alert(erro.message)));
});
