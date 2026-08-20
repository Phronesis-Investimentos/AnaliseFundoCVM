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
        return `<span class="text-gray-500 dark:text-gray-400">0.00%</span>`;
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

    // Cor de fundo da célula de correlação (verde-neon -> transparente -> vermelho).
    // Sensível ao tema: no claro usa texto escuro sobre os tons pastel,
    // no escuro mantém o visual original (texto quase branco).
    const corCelulaCorrelacao = (valor) => {
        const modoClaro = !document.documentElement.classList.contains('dark');

        if (valor === null || valor === undefined || isNaN(valor)) {
            return modoClaro
                ? 'background: rgba(0,0,0,0.03); color: #6b7280;'
                : 'background: rgba(255,255,255,0.02); color: #6b7280;';
        }
        if (valor >= 0.999) {
            // Diagonal principal (fundo com ele mesmo)
            return modoClaro
                ? 'background: rgba(0,0,0,0.05); color: #4b5563;'
                : 'background: rgba(255,255,255,0.06); color: #9ca3af;';
        }
        if (valor >= 0) {
            const alpha = 0.06 + valor * 0.32;
            return modoClaro
                ? `background: rgba(0, 200, 110, ${alpha.toFixed(2)}); color: #065f32;`
                : `background: rgba(0, 255, 136, ${alpha.toFixed(2)}); color: #eafff2;`;
        }
        const alpha = 0.06 + Math.abs(valor) * 0.32;
        return modoClaro
            ? `background: rgba(220, 38, 38, ${alpha.toFixed(2)}); color: #7f1d1d;`
            : `background: rgba(255, 51, 102, ${alpha.toFixed(2)}); color: #ffe9ee;`;
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

    // ---- Carteiras salvas ----
    const btnVerCarteiras = document.getElementById('btn_ver_carteiras');
    const btnAdicionarCarteira = document.getElementById('btn_adicionar_carteira');
    const popoverAdicionarCarteira = document.getElementById('popover_adicionar_carteira');
    const inputNomeCarteira = document.getElementById('input_nome_carteira');
    const btnConfirmarCarteira = document.getElementById('btn_confirmar_carteira');
    const modalVerCarteiras = document.getElementById('modal_ver_carteiras');
    const listaCarteirasModal = document.getElementById('lista_carteiras_modal');
    const carteirasModalVazio = document.getElementById('carteiras_modal_vazio');
    const btnFecharModalCarteiras = document.getElementById('btn_fechar_modal_carteiras');

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
            li.className = 'px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5 border-b border-gray-100 dark:border-white/5 last:border-0 text-sm staggered-item transition-colors';
            li.style.animationDelay = `${index * 0.05}s`;
            li.innerHTML = `
                <div class="text-gray-800 dark:text-gray-200 truncate">${item.DENOM_SOCIAL}</div>
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
                <i class="ph ph-x cursor-pointer hover:text-gray-900 dark:hover:text-white transition-colors" data-idx="${idx}"></i>
            `;
            chip.querySelector('i').addEventListener('click', () => {
                fundosPortfolio.splice(idx, 1);
                renderChipsFundos();
            });
            divFundosAdicionados.appendChild(chip);
        });

        btnGerarPortfolio.disabled = fundosPortfolio.length === 0;
        btnAdicionarCarteira.disabled = fundosPortfolio.length === 0;
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
    // 3B. CARTEIRAS SALVAS (popover "Adicionar" + modal "Ver Carteiras")
    // ==========================================

    // ---- Popover "Adicionar Carteira" ----

    function abrirPopoverCarteira() {
        popoverAdicionarCarteira.classList.remove('hidden');
        inputNomeCarteira.value = '';
        inputNomeCarteira.focus();
    }

    function fecharPopoverCarteira() {
        popoverAdicionarCarteira.classList.add('hidden');
    }

    btnAdicionarCarteira.addEventListener('click', (e) => {
        e.stopPropagation();
        if (popoverAdicionarCarteira.classList.contains('hidden')) {
            abrirPopoverCarteira();
        } else {
            fecharPopoverCarteira();
        }
    });

    // Clicar fora fecha o popover (mesmo padrão do dropdown de busca)
    document.addEventListener('click', (e) => {
        if (!popoverAdicionarCarteira.contains(e.target) && e.target !== btnAdicionarCarteira) {
            fecharPopoverCarteira();
        }
    });

    // Enter no campo de nome também confirma
    inputNomeCarteira.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            btnConfirmarCarteira.click();
        } else if (e.key === 'Escape') {
            fecharPopoverCarteira();
        }
    });

    btnConfirmarCarteira.addEventListener('click', async () => {
        const nome = inputNomeCarteira.value.trim();
        if (!nome) {
            inputNomeCarteira.focus();
            return;
        }
        if (fundosPortfolio.length === 0) return;

        try {
            const res = await fetch('/api/carteiras', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nome,
                    fundos: fundosPortfolio.map(f => f.cnpj),
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.erro || 'Não foi possível salvar a carteira.');

            // Salvou -> fecha a caixinha sozinha
            fecharPopoverCarteira();
        } catch (erro) {
            console.error(erro);
            alert(erro.message || 'Erro ao salvar a carteira.');
        }
    });

    // ---- Modal "Ver Carteiras" ----

    function abrirModalCarteiras() {
        modalVerCarteiras.classList.remove('hidden');
        carregarListaCarteirasNoModal();
    }

    function fecharModalCarteiras() {
        modalVerCarteiras.classList.add('hidden');
    }

    btnVerCarteiras.addEventListener('click', abrirModalCarteiras);
    btnFecharModalCarteiras.addEventListener('click', fecharModalCarteiras);

    // Clicar no backdrop (fora da caixa) fecha o modal
    modalVerCarteiras.addEventListener('click', (e) => {
        if (e.target === modalVerCarteiras) fecharModalCarteiras();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modalVerCarteiras.classList.contains('hidden')) {
            fecharModalCarteiras();
        }
    });

    async function carregarListaCarteirasNoModal() {
        listaCarteirasModal.innerHTML = '';
        carteirasModalVazio.classList.add('hidden');
        try {
            const res = await fetch('/api/carteiras');
            const carteiras = await res.json();
            renderizarListaCarteirasNoModal(carteiras);
        } catch (e) {
            console.error(e);
        }
    }

    function renderizarListaCarteirasNoModal(carteiras) {
        listaCarteirasModal.innerHTML = '';

        if (!carteiras || carteiras.length === 0) {
            carteirasModalVazio.classList.remove('hidden');
            return;
        }
        carteirasModalVazio.classList.add('hidden');

        carteiras.forEach(carteira => {
            const linha = document.createElement('div');
            linha.className = 'flex items-center justify-between gap-3 bg-surface hover:bg-surfaceHover border border-gray-200 dark:border-white/10 hover:border-neon/30 rounded-xl px-4 py-3 cursor-pointer transition-all group';
            linha.innerHTML = `
                <div class="flex items-center gap-3 min-w-0">
                    <i class="ph ph-bookmark-simple-fill text-neon text-lg flex-shrink-0"></i>
                    <div class="min-w-0">
                        <div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">${carteira.nome}</div>
                        <div class="text-[11px] text-gray-500">${carteira.quantidade_fundos} fundo(s)</div>
                    </div>
                </div>
                <i class="ph ph-trash text-gray-500 hover:text-[#ff3366] cursor-pointer transition-colors flex-shrink-0 p-1" data-excluir-carteira="${carteira.nome}"></i>
            `;

            // Clicar na linha (fora da lixeira) seleciona e carrega a carteira
            linha.addEventListener('click', (e) => {
                if (e.target.closest('[data-excluir-carteira]')) return;
                fecharModalCarteiras();
                carregarCarteira(carteira.nome);
            });

            linha.querySelector('[data-excluir-carteira]').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (!confirm(`Excluir a carteira "${carteira.nome}"?`)) return;
                try {
                    await fetch(`/api/carteiras/${encodeURIComponent(carteira.nome)}`, { method: 'DELETE' });
                    carregarListaCarteirasNoModal();
                } catch (erro) {
                    console.error(erro);
                    alert('Erro ao excluir a carteira.');
                }
            });

            listaCarteirasModal.appendChild(linha);
        });
    }

    // ---- Carregar uma carteira (usada ao clicar numa linha do modal) ----

    async function carregarCarteira(nome) {
        showLoader();
        try {
            const res = await fetch(`/api/carteiras/${encodeURIComponent(nome)}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.erro || 'Carteira não encontrada.');

            // Busca os dados (nome do fundo) de cada CNPJ salvo, já que a
            // carteira só guarda os CNPJs. Usa /api/fundos/buscar com o
            // próprio CNPJ como termo.
            const fundosEncontrados = [];
            for (const cnpj of data.cnpjs) {
                try {
                    const resBusca = await fetch(`/api/fundos/buscar?busca=${encodeURIComponent(cnpj)}`);
                    const encontrados = await resBusca.json();
                    const match = encontrados.find(f => f.CNPJ_FUNDO === cnpj) || encontrados[0];
                    if (match) {
                        fundosEncontrados.push({ cnpj: match.CNPJ_FUNDO, nome: match.DENOM_SOCIAL });
                    }
                } catch (e) {
                    console.error(`Erro ao buscar dados do fundo ${cnpj}:`, e);
                }
            }

            if (fundosEncontrados.length === 0) {
                throw new Error('Nenhum dos fundos salvos nessa carteira foi encontrado.');
            }

            fundosPortfolio = fundosEncontrados;
            renderChipsFundos();

            // Gera o portfólio direto, com a data de hoje (informações
            // mais recentes), igual clicar em "Gerar Portfólio".
            const cnpjs = fundosPortfolio.map(f => f.cnpj);
            const resultado = await chamarApiPortfolio(cnpjs, inputDataReferencia.value);
            ultimoResultado = resultado;
            renderizarPortfolio(resultado);
        } catch (erro) {
            console.error(erro);
            alert(erro.message || 'Erro ao carregar a carteira.');
        } finally {
            hideLoader();
        }
    }

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
        atualizarColunasAttribution();

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

    // ---- Risk Attribution: soma da coluna de cada fundo na matriz de
    // covariância, dividida pela soma total da matriz. Recalculado a
    // partir da mesma matriz de covariância já ao vivo (calculada acima),
    // então acompanha qualquer mudança de peso automaticamente. ----

    function calcularRiskAttribution(covariancia) {
        if (!covariancia || Object.keys(covariancia).length === 0) return {};

        const cnpjs = Object.keys(covariancia);

        let somaTotal = 0;
        cnpjs.forEach(cnpjColuna => {
            cnpjs.forEach(cnpjLinha => {
                const valor = covariancia?.[cnpjColuna]?.[cnpjLinha];
                if (valor !== null && valor !== undefined && !isNaN(valor)) {
                    somaTotal += valor;
                }
            });
        });

        const riscoAtribuido = {};
        cnpjs.forEach(cnpjColuna => {
            let somaColuna = 0;
            cnpjs.forEach(cnpjLinha => {
                const valor = covariancia?.[cnpjColuna]?.[cnpjLinha];
                if (valor !== null && valor !== undefined && !isNaN(valor)) {
                    somaColuna += valor;
                }
            });
            riscoAtribuido[cnpjColuna] = somaTotal !== 0 ? (somaColuna / somaTotal) * 100 : null;
        });

        return riscoAtribuido;
    }

    // ---- Attribution: rentabilidade (36m) x peso de cada fundo ----

    function calcularAttributionAtual() {
        const inputs = tabelaBody.querySelectorAll('input[data-peso-cnpj]');
        const attribution = {};

        inputs.forEach(input => {
            const cnpj = input.dataset.pesoCnpj;
            const peso = (parseFloat(input.value) || 0) / 100;
            const fundo = ultimoResultado.fundos.find(f => f.cnpj === cnpj);
            if (!fundo || fundo.rentabilidade_36m === null || fundo.rentabilidade_36m === undefined) {
                attribution[cnpj] = null;
                return;
            }
            attribution[cnpj] = fundo.rentabilidade_36m * peso;
        });

        return attribution;
    }

    // ---- Attribution / |Risk Attribution| e atualização das duas
    // colunas na tabela principal. Roda sempre que o peso muda, junto
    // com a matriz de covariância (que o Risk Attribution depende). ----

    function atualizarColunasAttribution() {
        const covariancia = calcularCovarianciaAtual();
        const riscoAtribuido = calcularRiskAttribution(covariancia);
        const attribution = calcularAttributionAtual();

        tabelaBody.querySelectorAll('[data-risco-atribuido-cnpj]').forEach(celula => {
            const cnpj = celula.dataset.riscoAtribuidoCnpj;
            const valor = riscoAtribuido[cnpj];
            celula.textContent = (valor === null || valor === undefined || isNaN(valor))
                ? '—'
                : `${valor.toFixed(2)}%`;
        });

        tabelaBody.querySelectorAll('[data-attribution-cnpj]').forEach(celula => {
            const cnpj = celula.dataset.attributionCnpj;
            const valor = attribution[cnpj];
            celula.textContent = (valor === null || valor === undefined || isNaN(valor))
                ? '—'
                : `${valor.toFixed(2)}%`;
        });

        tabelaBody.querySelectorAll('[data-attribution-risco-cnpj]').forEach(celula => {
            const cnpj = celula.dataset.attributionRiscoCnpj;
            const attr = attribution[cnpj];
            const risco = riscoAtribuido[cnpj];

            let valor = null;
            if (attr !== null && attr !== undefined && !isNaN(attr)
                && risco !== null && risco !== undefined && !isNaN(risco) && risco !== 0) {
                valor = attr / Math.abs(risco);
            }

            celula.textContent = (valor === null) ? '—' : valor.toFixed(4);
        });
    }

    // Cor de fundo da célula de covariância (mesma lógica da correlação,
    // mas a escala vai de -1 a 1 no teor "cru" da fórmula — na prática os
    // valores costumam ficar bem menores, então a intensidade da cor é
    // proporcional ao valor absoluto). Sensível ao tema, igual
    // corCelulaCorrelacao.
    const corCelulaCovariancia = (valor) => {
        const modoClaro = !document.documentElement.classList.contains('dark');

        if (valor === null || valor === undefined || isNaN(valor)) {
            return modoClaro
                ? 'background: rgba(0,0,0,0.03); color: #6b7280;'
                : 'background: rgba(255,255,255,0.02); color: #6b7280;';
        }
        if (valor >= 0) {
            const alpha = Math.min(0.06 + valor * 2, 0.85);
            return modoClaro
                ? `background: rgba(0, 200, 110, ${alpha.toFixed(2)}); color: #065f32;`
                : `background: rgba(0, 255, 136, ${alpha.toFixed(2)}); color: #eafff2;`;
        }
        const alpha = Math.min(0.06 + Math.abs(valor) * 2, 0.85);
        return modoClaro
            ? `background: rgba(220, 38, 38, ${alpha.toFixed(2)}); color: #7f1d1d;`
            : `background: rgba(255, 51, 102, ${alpha.toFixed(2)}); color: #ffe9ee;`;
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
            `<th class="p-2 font-medium text-gray-500 dark:text-gray-400 text-[10px] max-w-[90px]" title="${mapaNomes[cnpj]}">${nomeCurto(mapaNomes[cnpj])}</th>`
        ).join('');
        thead.appendChild(trHead);
        tabelaCovariancia.appendChild(thead);

        // Corpo
        const tbody = document.createElement('tbody');
        cnpjs.forEach(cnpjLinha => {
            const tr = document.createElement('tr');
            let linhaHtml = `<th class="p-2 font-medium text-gray-500 dark:text-gray-400 text-[10px] text-right max-w-[110px] truncate" title="${mapaNomes[cnpjLinha]}">${nomeCurto(mapaNomes[cnpjLinha])}</th>`;

            cnpjs.forEach(cnpjColuna => {
                const valor = covariancia?.[cnpjColuna]?.[cnpjLinha];
                const texto = (valor === null || valor === undefined || isNaN(valor)) ? '—' : valor.toFixed(4);
                linhaHtml += `<td class="p-2 rounded-lg font-medium min-w-[52px]" style="${corCelulaCovariancia(valor)}">${texto}</td>`;
            });

            tr.innerHTML = linhaHtml;
            tbody.appendChild(tr);
        });
        tabelaCovariancia.appendChild(tbody);

        // Rodapé: Risk Attribution de cada fundo (soma da coluna / soma
        // total da matriz), logo abaixo da matriz.
        const riscoAtribuido = calcularRiskAttribution(covariancia);
        const tfoot = document.createElement('tfoot');
        const trFoot = document.createElement('tr');
        let footHtml = `<th class="p-2 pt-4 font-semibold text-gray-900 dark:text-white text-[10px] text-right border-t border-gray-200 dark:border-white/10">Risco Atribuído</th>`;
        cnpjs.forEach(cnpj => {
            const valor = riscoAtribuido[cnpj];
            const texto = (valor === null || valor === undefined || isNaN(valor)) ? '—' : `${valor.toFixed(2)}%`;
            footHtml += `<td class="p-2 pt-4 font-semibold text-neon border-t border-gray-200 dark:border-white/10">${texto}</td>`;
        });
        trFoot.innerHTML = footHtml;
        tfoot.appendChild(trFoot);
        tabelaCovariancia.appendChild(tfoot);

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
        const covariancia = calcularCovarianciaAtual();
        const riscoAtribuido = calcularRiskAttribution(covariancia);
        const attribution = calcularAttributionAtual();

        return ultimoResultado.fundos.map(fundo => {
            const input = tabelaBody.querySelector(`input[data-peso-cnpj="${fundo.cnpj}"]`);
            const peso = input ? parseFloat(input.value) || 0 : null;

            const risco = riscoAtribuido[fundo.cnpj];
            const attr = attribution[fundo.cnpj];
            const attrPorRisco = (
                attr !== null && attr !== undefined && !isNaN(attr)
                && risco !== null && risco !== undefined && !isNaN(risco) && risco !== 0
            ) ? attr / Math.abs(risco) : null;

            return {
                ...fundo,
                peso,
                risco_atribuido: risco ?? null,
                attribution: attr ?? null,
                attribution_por_risco: attrPorRisco,
            };
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
            linha.className = 'border-b border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/[0.02] result-fade-in';

            // Última linha recebe o ajuste de arredondamento para fechar 100%
            const valorPeso = idx === fundosComDados.length - 1
                ? (100 - pesoIgual * (fundosComDados.length - 1)).toFixed(2)
                : pesoIgual.toFixed(2);

            linha.innerHTML = `
                <td class="px-4 py-4 text-xs text-gray-500 dark:text-gray-400">${fundo.cnpj}</td>
                <td class="px-4 py-4 text-gray-800 dark:text-gray-200">
                    <div class="truncate max-w-[260px] text-sm font-medium" title="${fundo.nome}">${fundo.nome}</div>
                </td>
                <td class="px-4 py-4 text-right">${formatValue(fundo.rentabilidade_36m)}</td>
                <td class="px-4 py-4 text-center">${formatVolatilidade(fundo.volatilidade_36m)}</td>
                <td class="px-4 py-4 text-center">
                    <div class="relative inline-flex items-center">
                        <input type="number" min="0" max="100" step="0.01"
                               data-peso-cnpj="${fundo.cnpj}"
                               value="${valorPeso}"
                               class="w-20 bg-gray-50 dark:bg-black/50 border border-gray-200 dark:border-white/10 rounded-lg py-1.5 pl-2 pr-6 text-center text-sm focus:outline-none focus:border-neon focus:ring-1 focus:ring-neon transition-all">
                        <span class="absolute right-2 text-xs text-gray-500 pointer-events-none">%</span>
                    </div>
                </td>
                <td class="px-4 py-4 text-center text-sm" data-risco-atribuido-cnpj="${fundo.cnpj}">—</td>
                <td class="px-4 py-4 text-center text-sm" data-attribution-cnpj="${fundo.cnpj}">—</td>
                <td class="px-4 py-4 text-center text-sm" data-attribution-risco-cnpj="${fundo.cnpj}">—</td>
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
            `<th class="p-2 font-medium text-gray-500 dark:text-gray-400 text-[10px] max-w-[90px]" title="${mapaNomes[cnpj]}">${nomeCurto(mapaNomes[cnpj])}</th>`
        ).join('');
        thead.appendChild(trHead);
        tabelaCorrelacao.appendChild(thead);

        // Corpo
        const tbody = document.createElement('tbody');
        cnpjs.forEach(cnpjLinha => {
            const tr = document.createElement('tr');
            let linhaHtml = `<th class="p-2 font-medium text-gray-500 dark:text-gray-400 text-[10px] text-right max-w-[110px] truncate" title="${mapaNomes[cnpjLinha]}">${nomeCurto(mapaNomes[cnpjLinha])}</th>`;

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

    // ==========================================
    // 5. TEMA CLARO/ESCURO — redesenha as matrizes ao trocar de tema
    // ==========================================
    // As cores das células (correlação/covariância) são calculadas em
    // JS, não via CSS — então não se ajustam sozinhas quando o tema
    // muda. theme.js dispara esse evento assim que a classe "dark" é
    // alternada; se já houver um portfólio na tela, redesenha as duas
    // matrizes com as cores certas pro tema novo.
    document.addEventListener('phronesis:tema-mudou', () => {
        if (!ultimoResultado.fundos || ultimoResultado.fundos.length === 0) return;
        renderizarMatrizCorrelacao(ultimoResultado.fundos, ultimoResultado.correlacao);
        renderizarMatrizCovariancia();
    });

});