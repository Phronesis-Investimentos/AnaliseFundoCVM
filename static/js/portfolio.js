document.addEventListener("DOMContentLoaded", () => {

    // ==========================================
    // 1. EFEITOS DE UI/UX (Magnet e Tilt)
    // ==========================================

    const magneticButtons = document.querySelectorAll('.magnetic-btn');
    magneticButtons.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            btn.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = `translate(0px, 0px)`;
        });
    });

    const tiltCards = document.querySelectorAll('.tilt-card');
    tiltCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = ((y - centerY) / centerY) * -3;
            const rotateY = ((x - centerX) / centerX) * 3;
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.005, 1.005, 1.005)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
        });
    });

    // ==========================================
    // 2. UTILITÁRIOS
    // ==========================================

    const loader = document.getElementById('global_loader');
    const showLoader = () => loader.classList.add('loader-visible');
    const hideLoader = () => loader.classList.remove('loader-visible');

    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    // Formatação de cor baseada na rentabilidade (mesmo padrão da tela de comparação)
    const formatValue = (val) => {
        if (val === null || val === undefined || isNaN(val)) {
            return `<span class="text-gray-500">s/ dados</span>`;
        }
        if (val > 0) return `<span class="text-[#00ff88] font-semibold">+${val.toFixed(2)}%</span>`;
        if (val < 0) return `<span class="text-[#ff3366] font-semibold">${val.toFixed(2)}%</span>`;
        return `<span class="text-gray-400">0.00%</span>`;
    };

    // Formata "YYYY-MM-DD" (valor do <input type="date">) para "dd/mm/aaaa"
    const formatarDataBR = (dataISO) => {
        if (!dataISO) return '';
        const [ano, mes, dia] = dataISO.split('-');
        return `${dia}/${mes}/${ano}`;
    };

    // Badge de volatilidade com faixa de cor (baixa / média / alta)
    const formatVolatilidade = (vol) => {
        if (vol === null || vol === undefined || isNaN(vol)) {
            return `<span class="vol-badge vol-badge-na"><span class="vol-dot"></span>s/ dados</span>`;
        }
        let faixa = 'low';
        if (vol >= 18) faixa = 'high';
        else if (vol >= 8) faixa = 'mid';

        return `<span class="vol-badge vol-badge-${faixa}"><span class="vol-dot"></span>${vol.toFixed(2)}%</span>`;
    };

    // Cor de fundo da célula de correlação (verde-neon -> transparente -> vermelho)
    const corCelulaCorrelacao = (valor) => {
        if (valor === null || valor === undefined || isNaN(valor)) {
            return 'background: rgba(255,255,255,0.02); color: #6b7280;';
        }
        if (valor >= 0.999) {
            // Diagonal principal (fundo com ele mesmo)
            return 'background: rgba(255,255,255,0.06); color: #9ca3af;';
        }
        if (valor >= 0) {
            const alpha = 0.06 + valor * 0.32;
            return `background: rgba(0, 255, 136, ${alpha.toFixed(2)}); color: #eafff2;`;
        }
        const alpha = 0.06 + Math.abs(valor) * 0.32;
        return `background: rgba(255, 51, 102, ${alpha.toFixed(2)}); color: #ffe9ee;`;
    };

    // ==========================================
    // 3. SELEÇÃO DE FUNDOS (por nome ou CNPJ)
    // ==========================================

    let fundosPortfolio = [];

    const inputBusca = document.getElementById('busca_fundo_portfolio');
    const listaBusca = document.getElementById('lista_fundos_portfolio');
    const divFundosAdicionados = document.getElementById('fundos_portfolio_adicionados');
    const btnGerarPortfolio = document.getElementById('btn_gerar_portfolio');
    const inputDataReferencia = document.getElementById('portfolio_data_referencia');

    // Data de referência padrão: mês atual
    inputDataReferencia.value = new Date().toISOString().slice(0, 10);

    const renderDropdown = (items) => {
        listaBusca.innerHTML = '';
        if (items.length === 0) {
            listaBusca.classList.add('hidden');
            return;
        }

        items.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'px-4 py-3 cursor-pointer hover:bg-white/5 border-b border-white/5 last:border-0 text-sm staggered-item transition-colors';
            li.style.animationDelay = `${index * 0.05}s`;
            li.innerHTML = `
                <div class="text-gray-200 truncate">${item.DENOM_SOCIAL}</div>
                <div class="text-[11px] text-gray-500 mt-0.5">${item.CNPJ_FUNDO}</div>
            `;

            li.addEventListener('click', () => {
                if (!fundosPortfolio.find(f => f.cnpj === item.CNPJ_FUNDO)) {
                    fundosPortfolio.push({
                        cnpj: item.CNPJ_FUNDO,
                        nome: item.DENOM_SOCIAL,
                    });
                    renderChipsFundos();
                }
                inputBusca.value = '';
                listaBusca.classList.add('hidden');
            });
            listaBusca.appendChild(li);
        });
        listaBusca.classList.remove('hidden');
    };

    const renderChipsFundos = () => {
        divFundosAdicionados.innerHTML = '';
        fundosPortfolio.forEach((fundo, idx) => {
            const chip = document.createElement('div');
            chip.className = 'flex items-center gap-2 bg-neon/10 border border-neon/20 text-neon px-3 py-1 rounded-full text-xs animate-fade-in-up';
            chip.innerHTML = `
                <span class="truncate max-w-[220px]">${fundo.nome}</span>
                <i class="ph ph-x cursor-pointer hover:text-white transition-colors" data-idx="${idx}"></i>
            `;
            chip.querySelector('i').addEventListener('click', () => {
                fundosPortfolio.splice(idx, 1);
                renderChipsFundos();
            });
            divFundosAdicionados.appendChild(chip);
        });

        btnGerarPortfolio.disabled = fundosPortfolio.length === 0;
    };

    const fetchBuscaFundos = debounce(async (termo) => {
        if (termo.length < 3) {
            listaBusca.classList.add('hidden');
            return;
        }
        try {
            const res = await fetch(`/api/fundos/buscar?busca=${encodeURIComponent(termo)}`);
            const data = await res.json();
            renderDropdown(data);
        } catch (e) {
            console.error(e);
        }
    }, 400);

    inputBusca.addEventListener('input', (e) => fetchBuscaFundos(e.target.value));

    document.addEventListener('click', (e) => {
        if (!inputBusca.contains(e.target)) listaBusca.classList.add('hidden');
    });

    // ==========================================
    // 4. GERAÇÃO DO PORTFÓLIO (tabela + pesos + correlação)
    // ==========================================

    const painelResultado = document.getElementById('painel_resultado_portfolio');
    const painelCorrelacao = document.getElementById('painel_correlacao_portfolio');
    const painelCovariancia = document.getElementById('painel_covariancia_portfolio');
    const painelEstadoVazio = document.getElementById('painel_estado_vazio');
    const tabelaBody = document.getElementById('tabela_portfolio_body');
    const tabelaCorrelacao = document.getElementById('tabela_correlacao');
    const tabelaCovariancia = document.getElementById('tabela_covariancia');
    const contagemResultado = document.getElementById('portfolio_resultado_contagem');
    const somaPesosBox = document.getElementById('portfolio_soma_pesos');
    const somaPesosValor = document.getElementById('portfolio_soma_pesos_valor');
    const btnDistribuirIgual = document.getElementById('btn_distribuir_pesos_igual');
    const btnExportarPortfolio = document.getElementById('btn_exportar_portfolio');

    // Guarda o último resultado vindo da API (fundos + correlação) para
    // poder re-renderizar (ex: ao remover um fundo da tabela) sem
    // precisar chamar a API de novo.
    let ultimoResultado = { fundos: [], correlacao: {} };

    async function chamarApiPortfolio(cnpjs, dataReferencia) {
        const res = await fetch('/api/portfolio/gerar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fundos: cnpjs, data_referencia: dataReferencia }),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.erro || 'Não foi possível gerar o portfólio.');
        }
        return data;
    }

    // ---- Pesos ----

    function distribuirPesosIgualmente() {
        const linhas = tabelaBody.querySelectorAll('input[data-peso-cnpj]');
        if (linhas.length === 0) return;

        const pesoBase = +(100 / linhas.length).toFixed(2);
        linhas.forEach((input, idx) => {
            // Ajusta a última linha para garantir soma exata de 100%
            if (idx === linhas.length - 1) {
                const somaAnteriores = pesoBase * (linhas.length - 1);
                input.value = (100 - somaAnteriores).toFixed(2);
            } else {
                input.value = pesoBase.toFixed(2);
            }
        });
        atualizarSomaPesos();
    }

    function atualizarSomaPesos() {
        const inputs = tabelaBody.querySelectorAll('input[data-peso-cnpj]');
        let soma = 0;
        inputs.forEach(input => { soma += parseFloat(input.value) || 0; });
        soma = Math.round(soma * 100) / 100;

        somaPesosValor.textContent = soma.toFixed(2).replace(/\.00$/, '');

        const fechou100 = Math.abs(soma - 100) < 0.01;
        somaPesosBox.classList.remove(
            'text-[#00ff88]', 'border-[#00ff88]/30', 'bg-[#00ff88]/10',
            'text-[#ff3366]', 'border-[#ff3366]/30', 'bg-[#ff3366]/10'
        );
        somaPesosBox.querySelector('i').className = fechou100 ? 'ph ph-check-circle' : 'ph ph-warning-circle';

        if (fechou100) {
            somaPesosBox.classList.add('text-[#00ff88]', 'border-[#00ff88]/30', 'bg-[#00ff88]/10');
        } else {
            somaPesosBox.classList.add('text-[#ff3366]', 'border-[#ff3366]/30', 'bg-[#ff3366]/10');
        }

        atualizarMatrizCovariancia();

        return fechou100;
    }

    // ---- Matriz de covariância (recalculada no cliente sempre que um
    // peso muda, para exibir/exportar exatamente o que está na tela:
    // cada célula = correlacao(i,j) * vol(i) * vol(j) * peso(i) * peso(j).
    // vol e peso entram como FRAÇÃO decimal (ex: 15% -> 0.15), não como
    // percentual — senão o resultado explode e passa de 1. ----

    function calcularCovarianciaAtual() {
        const correlacao = ultimoResultado.correlacao;
        if (!correlacao || Object.keys(correlacao).length === 0) return {};

        const volatilidades = Object.fromEntries(
            ultimoResultado.fundos.map(f => [f.cnpj, f.volatilidade_36m])
        );

        const inputs = tabelaBody.querySelectorAll('input[data-peso-cnpj]');
        const pesos = {};
        inputs.forEach(input => {
            pesos[input.dataset.pesoCnpj] = (parseFloat(input.value) || 0) / 100;
        });

        const cnpjs = Object.keys(correlacao);
        const covariancia = {};

        cnpjs.forEach(cnpjColuna => {
            covariancia[cnpjColuna] = {};
            cnpjs.forEach(cnpjLinha => {
                const corrIJ = correlacao?.[cnpjColuna]?.[cnpjLinha];
                const volI = volatilidades[cnpjLinha];
                const volJ = volatilidades[cnpjColuna];
                const pesoI = pesos[cnpjLinha];
                const pesoJ = pesos[cnpjColuna];

                if (corrIJ === null || corrIJ === undefined || isNaN(corrIJ)
                    || volI === undefined || volJ === undefined
                    || pesoI === undefined || pesoJ === undefined) {
                    covariancia[cnpjColuna][cnpjLinha] = null;
                    return;
                }

                // Percentual -> fração decimal (15.0 -> 0.15)
                const volIFracao = volI / 100;
                const volJFracao = volJ / 100;

                covariancia[cnpjColuna][cnpjLinha] = corrIJ * volIFracao * volJFracao * pesoI * pesoJ;
            });
        });

        return covariancia;
    }

    // Cor de fundo da célula de covariância (mesma lógica da correlação,
    // mas a escala vai de -1 a 1 no teor "cru" da fórmula — na prática os
    // valores costumam ficar bem menores, então a intensidade da cor é
    // proporcional ao valor absoluto)
    const corCelulaCovariancia = (valor) => {
        if (valor === null || valor === undefined || isNaN(valor)) {
            return 'background: rgba(255,255,255,0.02); color: #6b7280;';
        }
        if (valor >= 0) {
            const alpha = Math.min(0.06 + valor * 2, 0.85);
            return `background: rgba(0, 255, 136, ${alpha.toFixed(2)}); color: #eafff2;`;
        }
        const alpha = Math.min(0.06 + Math.abs(valor) * 2, 0.85);
        return `background: rgba(255, 51, 102, ${alpha.toFixed(2)}); color: #ffe9ee;`;
    };

    function renderizarMatrizCovariancia() {
        if (!tabelaCovariancia || !painelCovariancia) return;

        const fundos = ultimoResultado.fundos || [];
        const covariancia = calcularCovarianciaAtual();

        tabelaCovariancia.innerHTML = '';

        const cnpjs = fundos.map(f => f.cnpj);
        const nomeCurto = (nome) => nome.length > 18 ? nome.slice(0, 18) + '…' : nome;
        const mapaNomes = Object.fromEntries(fundos.map(f => [f.cnpj, f.nome]));

        if (cnpjs.length < 2 || !covariancia || Object.keys(covariancia).length === 0) {
            painelCovariancia.classList.add('hidden');
            return;
        }

        // Cabeçalho
        const thead = document.createElement('thead');
        const trHead = document.createElement('tr');
        trHead.innerHTML = `<th class="p-2"></th>` + cnpjs.map(cnpj =>
            `<th class="p-2 font-medium text-gray-400 text-[10px] max-w-[90px]" title="${mapaNomes[cnpj]}">${nomeCurto(mapaNomes[cnpj])}</th>`
        ).join('');
        thead.appendChild(trHead);
        tabelaCovariancia.appendChild(thead);

        // Corpo
        const tbody = document.createElement('tbody');
        cnpjs.forEach(cnpjLinha => {
            const tr = document.createElement('tr');
            let linhaHtml = `<th class="p-2 font-medium text-gray-400 text-[10px] text-right max-w-[110px] truncate" title="${mapaNomes[cnpjLinha]}">${nomeCurto(mapaNomes[cnpjLinha])}</th>`;

            cnpjs.forEach(cnpjColuna => {
                const valor = covariancia?.[cnpjColuna]?.[cnpjLinha];
                const texto = (valor === null || valor === undefined || isNaN(valor)) ? '—' : valor.toFixed(4);
                linhaHtml += `<td class="p-2 rounded-lg font-medium min-w-[52px]" style="${corCelulaCovariancia(valor)}">${texto}</td>`;
            });

            tr.innerHTML = linhaHtml;
            tbody.appendChild(tr);
        });
        tabelaCovariancia.appendChild(tbody);

        painelCovariancia.classList.remove('hidden');
    }

    function atualizarMatrizCovariancia() {
        renderizarMatrizCovariancia();
    }

    btnDistribuirIgual.addEventListener('click', distribuirPesosIgualmente);

    // ---- Exportar para Excel (tabela + matriz de correlação juntas) ----

    function coletarFundosComPesoAtual() {
        // Usa os dados já carregados (ultimoResultado) + o peso que está
        // atualmente digitado em cada linha da tabela, pra exportar
        // exatamente o que o usuário está vendo na tela.
        return ultimoResultado.fundos.map(fundo => {
            const input = tabelaBody.querySelector(`input[data-peso-cnpj="${fundo.cnpj}"]`);
            const peso = input ? parseFloat(input.value) || 0 : null;
            return { ...fundo, peso };
        });
    }

    async function exportarPortfolioExcel() {
        if (!ultimoResultado.fundos || ultimoResultado.fundos.length === 0) return;

        showLoader();
        try {
            const res = await fetch('/api/portfolio/exportar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fundos: coletarFundosComPesoAtual(),
                    correlacao: ultimoResultado.correlacao,
                    covariancia: calcularCovarianciaAtual(),
                    data_referencia: inputDataReferencia.value,
                }),
            });

            if (!res.ok) {
                const erro = await res.json().catch(() => ({}));
                throw new Error(erro.erro || 'Não foi possível exportar o portfólio.');
            }

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `portfolio_${inputDataReferencia.value || 'export'}.xlsx`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (erro) {
            console.error(erro);
            alert(erro.message || 'Erro ao exportar o portfólio.');
        } finally {
            hideLoader();
        }
    }

    btnExportarPortfolio.addEventListener('click', exportarPortfolioExcel);

    // ---- Remoção de um fundo direto na tabela ----

    async function removerFundoDaTabela(cnpj) {
        fundosPortfolio = fundosPortfolio.filter(f => f.cnpj !== cnpj);
        renderChipsFundos();

        if (fundosPortfolio.length === 0) {
            painelResultado.classList.add('hidden');
            painelCorrelacao.classList.add('hidden');
            if (painelCovariancia) painelCovariancia.classList.add('hidden');
            painelEstadoVazio.classList.remove('hidden');
            return;
        }

        // Reaproveita os dados já carregados (sem nova chamada à API)
        ultimoResultado.fundos = ultimoResultado.fundos.filter(f => f.cnpj !== cnpj);
        renderizarPortfolio(ultimoResultado);
    }

    // ---- Tabela principal ----

    function renderizarTabelaPortfolio(fundosComDados) {
        tabelaBody.innerHTML = '';
        const pesoIgual = +(100 / fundosComDados.length).toFixed(2);

        fundosComDados.forEach((fundo, idx) => {
            const linha = document.createElement('tr');
            linha.className = 'border-b border-white/5 hover:bg-white/[0.02] result-fade-in';

            // Última linha recebe o ajuste de arredondamento para fechar 100%
            const valorPeso = idx === fundosComDados.length - 1
                ? (100 - pesoIgual * (fundosComDados.length - 1)).toFixed(2)
                : pesoIgual.toFixed(2);

            linha.innerHTML = `
                <td class="px-4 py-4 text-xs text-gray-400">${fundo.cnpj}</td>
                <td class="px-4 py-4 text-gray-200">
                    <div class="truncate max-w-[260px] text-sm font-medium" title="${fundo.nome}">${fundo.nome}</div>
                </td>
                <td class="px-4 py-4 text-right">${formatValue(fundo.rentabilidade_36m)}</td>
                <td class="px-4 py-4 text-center">${formatVolatilidade(fundo.volatilidade_36m)}</td>
                <td class="px-4 py-4 text-center">
                    <div class="relative inline-flex items-center">
                        <input type="number" min="0" max="100" step="0.01"
                               data-peso-cnpj="${fundo.cnpj}"
                               value="${valorPeso}"
                               class="w-20 bg-black/50 border border-white/10 rounded-lg py-1.5 pl-2 pr-6 text-center text-sm focus:outline-none focus:border-neon focus:ring-1 focus:ring-neon transition-all">
                        <span class="absolute right-2 text-xs text-gray-500 pointer-events-none">%</span>
                    </div>
                </td>
                <td class="px-4 py-4 text-center">
                    <i class="ph ph-trash text-gray-500 hover:text-[#ff3366] cursor-pointer transition-colors" data-cnpj="${fundo.cnpj}"></i>
                </td>`;
            tabelaBody.appendChild(linha);
        });

        tabelaBody.querySelectorAll('[data-cnpj]').forEach(icon => {
            icon.addEventListener('click', () => removerFundoDaTabela(icon.dataset.cnpj));
        });

        tabelaBody.querySelectorAll('input[data-peso-cnpj]').forEach(input => {
            input.addEventListener('input', atualizarSomaPesos);
        });

        contagemResultado.textContent = `${fundosComDados.length} fundo(s) · Referência: ${formatarDataBR(inputDataReferencia.value)}`;
        atualizarSomaPesos();
    }

    // ---- Matriz de correlação ----

    function renderizarMatrizCorrelacao(fundosComDados, correlacao) {
        tabelaCorrelacao.innerHTML = '';

        const cnpjs = fundosComDados.map(f => f.cnpj);
        const nomeCurto = (nome) => nome.length > 18 ? nome.slice(0, 18) + '…' : nome;
        const mapaNomes = Object.fromEntries(fundosComDados.map(f => [f.cnpj, f.nome]));

        if (cnpjs.length < 2 || !correlacao || Object.keys(correlacao).length === 0) {
            painelCorrelacao.classList.add('hidden');
            return;
        }

        // Cabeçalho
        const thead = document.createElement('thead');
        const trHead = document.createElement('tr');
        trHead.innerHTML = `<th class="p-2"></th>` + cnpjs.map(cnpj =>
            `<th class="p-2 font-medium text-gray-400 text-[10px] max-w-[90px]" title="${mapaNomes[cnpj]}">${nomeCurto(mapaNomes[cnpj])}</th>`
        ).join('');
        thead.appendChild(trHead);
        tabelaCorrelacao.appendChild(thead);

        // Corpo
        const tbody = document.createElement('tbody');
        cnpjs.forEach(cnpjLinha => {
            const tr = document.createElement('tr');
            let linhaHtml = `<th class="p-2 font-medium text-gray-400 text-[10px] text-right max-w-[110px] truncate" title="${mapaNomes[cnpjLinha]}">${nomeCurto(mapaNomes[cnpjLinha])}</th>`;

            cnpjs.forEach(cnpjColuna => {
                const valor = correlacao?.[cnpjColuna]?.[cnpjLinha];
                const texto = (valor === null || valor === undefined || isNaN(valor)) ? '—' : valor.toFixed(2);
                linhaHtml += `<td class="p-2 rounded-lg font-medium min-w-[52px]" style="${corCelulaCorrelacao(valor)}">${texto}</td>`;
            });

            tr.innerHTML = linhaHtml;
            tbody.appendChild(tr);
        });
        tabelaCorrelacao.appendChild(tbody);

        painelCorrelacao.classList.remove('hidden');
    }

    // ---- Orquestra tabela + correlação a partir do resultado da API ----

    function renderizarPortfolio(resultado) {
        if (!resultado.fundos || resultado.fundos.length === 0) {
            painelResultado.classList.add('hidden');
            painelCorrelacao.classList.add('hidden');
            if (painelCovariancia) painelCovariancia.classList.add('hidden');
            painelEstadoVazio.classList.remove('hidden');
            return;
        }

        renderizarTabelaPortfolio(resultado.fundos);
        renderizarMatrizCorrelacao(resultado.fundos, resultado.correlacao);

        painelEstadoVazio.classList.add('hidden');
        painelResultado.classList.remove('hidden');
    }

    // ---- Botão principal ----

    btnGerarPortfolio.addEventListener('click', async () => {
        if (fundosPortfolio.length === 0) return;

        showLoader();
        try {
            const cnpjs = fundosPortfolio.map(f => f.cnpj);
            const resultado = await chamarApiPortfolio(cnpjs, inputDataReferencia.value);
            ultimoResultado = resultado;
            renderizarPortfolio(resultado);
        } catch (erro) {
            console.error(erro);
            alert(erro.message || 'Erro ao gerar o portfólio.');
        } finally {
            hideLoader();
        }
    });

});