document.addEventListener("DOMContentLoaded", () => {

    // ==========================================
    // 1. EFEITOS DE UI/UX (Magnet e Tilt)
    // ==========================================

    // Botões Magnéticos
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

    // Cartões 3D (Tilt Card)
    const tiltCards = document.querySelectorAll('.tilt-card');
    tiltCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -5;
            const rotateY = ((x - centerX) / centerX) * 5;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.01, 1.01, 1.01)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
        });
    });

    // ==========================================
    // 2. UTILITÁRIOS
    // ==========================================

    // Loader Global
    const loader = document.getElementById('global_loader');
    const showLoader = () => loader.classList.add('loader-visible');
    const hideLoader = () => loader.classList.remove('loader-visible');

    // Formatação de cor baseada na rentabilidade
    const formatValue = (val) => {
        if (val > 0) return `<span class="text-[#00ff88]">+${val}%</span>`;
        if (val < 0) return `<span class="text-[#ff3366]">${val}%</span>`;
        return `<span class="text-gray-400">0.00%</span>`;
    };

    // Formata valor para "Desde o Início" (números grandes)
    const formatValueLarge = (val) => {
        if (val > 0) return `<span class="text-[#00ff88] font-bold">+${val}%</span>`;
        if (val < 0) return `<span class="text-[#ff3366] font-bold">${val}%</span>`;
        return `<span class="text-gray-400">0.00%</span>`;
    };

    // Formata a volatilidade
    const formatVolatilidade = (vol) => {
        if (vol === null || vol === undefined || isNaN(vol)) {
            return `<span class="vol-badge"><span class="vol-dot"></span>s/ dados</span>`;
        }

        return `<span class="vol-badge"><span class="vol-dot"></span>${vol.toFixed(2)}%</span>`;
    };
    // Debounce function
    function debounce(func, timeout = 300){
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    // ==========================================
    // 3. COMPARAÇÃO DE FUNDOS
    // ==========================================

    let fundosSelecionados = [];
    let periodosSelecionados = [];

    const inputBuscaComp = document.getElementById('busca_fundo_comparacao');
    const listaComp = document.getElementById('lista_fundos_comparacao');
    const divFundos = document.getElementById('fundos_adicionados');
    const divPeriodos = document.getElementById('periodos_adicionados');

    const renderDropdown = (items, listElement, onSelect) => {
        listElement.innerHTML = '';
        if(items.length === 0) {
            listElement.classList.add('hidden');
            return;
        }

        items.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'px-4 py-3 cursor-pointer hover:bg-white/5 border-b border-white/5 last:border-0 text-sm staggered-item text-gray-200 transition-colors';
            li.style.animationDelay = `${index * 0.05}s`;
            li.textContent = item.DENOM_SOCIAL;

            li.addEventListener('click', () => {
                onSelect(item);
                listElement.classList.add('hidden');
            });
            listElement.appendChild(li);
        });
        listElement.classList.remove('hidden');
    };

    const renderFundosChips = () => {
        divFundos.innerHTML = '';
        fundosSelecionados.forEach((fundo, idx) => {
            const chip = document.createElement('div');
            chip.className = 'flex items-center gap-2 bg-neon/10 border border-neon/20 text-neon px-3 py-1 rounded-full text-xs animate-fade-in-up';
            chip.innerHTML = `
                <span class="truncate max-w-[200px]">${fundo.nome}</span>
                <i class="ph ph-x cursor-pointer hover:text-white transition-colors" data-idx="${idx}"></i>
            `;
            chip.querySelector('i').addEventListener('click', () => {
                fundosSelecionados.splice(idx, 1);
                renderFundosChips();
            });
            divFundos.appendChild(chip);
        });
    };

    const fetchBuscaComp = debounce(async (termo) => {
        if(termo.length < 3) {
            listaComp.classList.add('hidden');
            return;
        }
        try {
            const res = await fetch(`/api/fundos/buscar?busca=${encodeURIComponent(termo)}`);
            const data = await res.json();
            renderDropdown(data, listaComp, (item) => {
                if(!fundosSelecionados.find(f => f.cnpj === item.CNPJ_FUNDO)) {
                    fundosSelecionados.push({ cnpj: item.CNPJ_FUNDO, nome: item.DENOM_SOCIAL });
                    renderFundosChips();
                }
                inputBuscaComp.value = '';
            });
        } catch (e) { console.error(e); }
    }, 400);

    inputBuscaComp.addEventListener('input', (e) => fetchBuscaComp(e.target.value));

    document.addEventListener('click', (e) => {
        if(!inputBuscaComp.contains(e.target)) listaComp.classList.add('hidden');
    });

    // ==========================================
    // 4. PERÍODOS
    // ==========================================

    // Duração em meses entre data_inicial e data_final. "Desde o Início"
    // recebe Infinity para sempre ficar por último na ordenação, já que sua
    // duração real varia por fundo (não é um período fixo como os outros).
    function duracaoEmMeses(periodo) {
        if (periodo.tipo === 'desde_inicio') return Infinity;
        if (!periodo.data_inicial || !periodo.data_final) return Infinity;

        const inicio = new Date(periodo.data_inicial + 'T00:00:00');
        const fim = new Date(periodo.data_final + 'T00:00:00');
        return (fim.getFullYear() - inicio.getFullYear()) * 12
            + (fim.getMonth() - inicio.getMonth());
    }

    // Ordena os períodos selecionados por duração crescente (meses),
    // deixando "Desde o Início" sempre no final.
    function ordenarPeriodosSelecionados() {
        periodosSelecionados.sort((a, b) => duracaoEmMeses(a) - duracaoEmMeses(b));
    }

    // Renderizar chips de períodos
    const renderPeriodosChips = () => {
        ordenarPeriodosSelecionados();
        divPeriodos.innerHTML = '';
        periodosSelecionados.forEach((p, idx) => {
            const chip = document.createElement('div');

            chip.className =
                'flex items-center gap-2 bg-white/5 border border-white/10 text-gray-300 px-3 py-1 rounded-full text-xs animate-fade-in-up';

            const label = p.label || `${p.data_inicial} até ${p.data_final}`;
            chip.innerHTML = `
                <span>${label}</span>
                <i class="ph ph-x cursor-pointer hover:text-white transition-colors" data-idx="${idx}"></i>
            `;
            chip.querySelector('i').addEventListener('click', () => {
                periodosSelecionados.splice(idx, 1);
                renderPeriodosChips();
            });
            divPeriodos.appendChild(chip);
        });
    };

    // Adicionar período customizado
    document.getElementById('btn_add_periodo').addEventListener('click', () => {
        const dI = document.getElementById('comp_data_ini').value;
        const dF = document.getElementById('comp_data_fim').value;

        if(!dI || !dF) {
            alert('Preencha as datas do período.');
            return;
        }

        const periodoExiste = periodosSelecionados.some(p =>
            p.data_inicial === dI && p.data_final === dF
        );

        if (periodoExiste) {
            alert('Este período já foi adicionado!');
            return;
        }

        periodosSelecionados.push({
            data_inicial: dI,
            data_final: dF,
            label: `${dI} até ${dF}`,
            tipo: 'customizado'
        });

        renderPeriodosChips();
        document.getElementById('comp_data_ini').value = '';
        document.getElementById('comp_data_fim').value = '';
    });

    // ==========================================
    // 5. PERÍODOS PADRÃO
    // ==========================================

    async function carregarPeriodosPadrao() {
        try {
            const response = await fetch('/api/periodos/padrao');
            const periodos = await response.json();
            renderizarPeriodosPadrao(periodos);
        } catch (error) {
            console.error('Erro ao carregar períodos padrão:', error);
        }
    }

    function renderizarPeriodosPadrao(periodos) {
        const container = document.getElementById('periodos_padrao_container');
        if (!container) return;

        container.innerHTML = '';

        if (periodos.length > 0) {
            const periodoRef = periodos.find(p => p.data_referencia);
            if (periodoRef) {
                const labelRef = document.getElementById('data_referencia_label');
                if (labelRef) {
                    labelRef.textContent = `Ref: ${periodoRef.data_referencia}`;
                }
            }
        }

        periodos.forEach(periodo => {
            const btn = document.createElement('button');

            btn.className =
                'bg-surface hover:bg-neon/10 text-gray-300 hover:text-neon px-3 py-2 rounded-lg transition-all border border-white/10 text-xs font-medium text-left w-full';

            if (periodo.tipo === 'desde_inicio') {
                btn.innerHTML = `
                    <div class="font-medium">
                        ${periodo.label}
                    </div>
                    <div class="text-gray-500 text-[10px] mt-0.5">
                        Primeira cota → ${new Date(periodo.data_final + 'T00:00:00').toLocaleDateString('pt-BR')}
                    </div>
                `;
            } else {
                const dataIni = new Date(periodo.data_inicial + 'T00:00:00');
                const dataFim = new Date(periodo.data_final + 'T00:00:00');
                const fmtData = (d) => d.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' });

                btn.innerHTML = `
                    <div class="font-medium">${periodo.label}</div>
                    <div class="text-gray-500 text-[10px] mt-0.5">
                        ${fmtData(dataIni)} → ${fmtData(dataFim)}
                    </div>
                `;
            }

            btn.addEventListener('click', () => {
                adicionarPeriodoPadrao(periodo);
            });

            container.appendChild(btn);
        });
    }

    function adicionarPeriodoPadrao(periodo) {
        const periodoExiste = periodosSelecionados.some(p =>
            p.data_inicial === periodo.data_inicial &&
            p.data_final === periodo.data_final
        );

        if (periodoExiste) {
            alert('Este período já foi adicionado!');
            return;
        }

        periodosSelecionados.push({
            data_inicial: periodo.data_inicial,
            data_final: periodo.data_final,
            label: periodo.label,
            tipo: periodo.tipo || 'padrao'
        });

        renderPeriodosChips();
    }

    // ==========================================
    // 6. COMPARAR FUNDOS
    // ==========================================

    document.getElementById('btn_comparar').addEventListener('click', async () => {
        if(fundosSelecionados.length === 0 || periodosSelecionados.length === 0) {
            alert('Adicione pelo menos um fundo e um período.');
            return;
        }

        showLoader();
        try {
            const res = await fetch('/api/fundos/comparar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    fundos: fundosSelecionados,
                    periodos: periodosSelecionados
                })
            });
            const data = await res.json();

            if(data.erro) {
                alert(data.erro);
                hideLoader();
                return;
            }

            // Renderizar Tabela
            const thead = document.getElementById('tabela_comparacao_head');
            const tbody = document.getElementById('tabela_comparacao_body');

            thead.innerHTML = '<th class="px-4 py-3 font-medium text-gray-400">Fundo</th>';
            data.periodos.forEach(p => {
                let label;
                if (p.label) {
                    label = p.label;
                } else if (p.data_inicial && p.data_final) {
                    const ini = new Date(p.data_inicial + 'T00:00:00');
                    const fim = new Date(p.data_final + 'T00:00:00');
                    const fmt = (d) => d.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' });
                    label = `${fmt(ini)}<br>${fmt(fim)}`;
                } else {
                    label = 'Período';
                }
                thead.innerHTML += `<th class="px-4 py-3 font-medium text-gray-400 text-right text-xs">${label}</th>`;
            });

            tbody.innerHTML = '';
            data.fundos.forEach(f => {
                let row = `<tr class="border-b border-white/5">
                    <td class="px-4 py-4 text-gray-200 align-top">
                        <div class="truncate max-w-[250px] font-medium" title="${f.nome}">${f.nome}</div>
                        <div class="text-xs text-gray-500">${f.cnpj}</div>
                    </td>`;

                f.variacoes.forEach(v => {
                    // Rentabilidade (formato grande para "Desde o Início")
                    const valorFormatado = v.tipo === 'desde_inicio'
                        ? formatValueLarge(v.variacao_percentual)
                        : formatValue(v.variacao_percentual);

                    // Badge de volatilidade
                    const volFormatada = formatVolatilidade(v.volatilidade_percentual);

                    // Tooltip com informações extras para "Desde o Início"
                    let tooltip = '';
                    if (v.tipo === 'desde_inicio' && v.primeira_data) {
                        tooltip = `title="Desde ${v.primeira_data}"`;
                    }

                    row += `
                        <td class="px-4 py-4 text-right" ${tooltip}>
                            <div class="metric-cell">
                                <span class="rentabilidade font-medium">${valorFormatado}</span>
                                ${volFormatada}
                            </div>
                        </td>`;
                });
                row += '</tr>';
                tbody.innerHTML += row;
            });

            // Atualiza subtítulo com contagem de fundos/períodos
            const titulo = document.getElementById('modal_titulo');
            if (titulo) {
                titulo.textContent = 'Resultado da Comparação';
            }
            const subtitulo = document.getElementById('modal_subtitulo');
            if (subtitulo) {
                subtitulo.textContent = `${data.fundos.length} fundo(s) · ${data.periodos.length} período(s)`;
            }

            abrirModalResultado();

        } catch(e) {
            alert('Erro ao comparar fundos.');
            console.error(e);
        } finally {
            hideLoader();
        }
    });

    // ==========================================
    // 7. RANKING (modal de filtros + geração)
    // ==========================================

    // Guarda a data de referência do último ranking gerado, para que o
    // cálculo de volatilidade de cada fundo use os mesmos períodos.
    let dataReferenciaRankingAtual = null;

    const PERIODOS_RANKING = ['12m', '24m', '36m', '48m', '60m'];

    const ROTULOS_CATEGORIA = {
        todos: 'Todos',
        acoes: 'Ações',
        multimercado: 'Multimercado',
    };

    const modalFiltrosRanking = document.getElementById('modal_filtros_ranking');
    const inputsPesoRanking = document.querySelectorAll('.peso-ranking-input');
    const somaPesosLabel = document.getElementById('filtro_ranking_soma');
    const erroPesosLabel = document.getElementById('filtro_ranking_erro');
    const btnConfirmarFiltrosRanking = document.getElementById('btn_confirmar_filtros_ranking');

    function somaPesosAtual() {
        let soma = 0;
        inputsPesoRanking.forEach(input => {
            soma += parseFloat(input.value) || 0;
        });
        return soma;
    }

    // Atualiza o rótulo da soma dos pesos e trava o botão OK enquanto a
    // soma não fechar exatamente em 100%.
    function atualizarSomaPesos() {
        const soma = Math.round(somaPesosAtual() * 100) / 100;
        somaPesosLabel.textContent = `${soma}%`;

        const valido = Math.abs(soma - 100) < 0.01;

        somaPesosLabel.classList.toggle('text-neon', valido);
        somaPesosLabel.classList.toggle('text-[#ff3366]', !valido);

        erroPesosLabel.classList.toggle('hidden', valido);

        btnConfirmarFiltrosRanking.disabled = !valido;
        btnConfirmarFiltrosRanking.classList.toggle('opacity-50', !valido);
        btnConfirmarFiltrosRanking.classList.toggle('cursor-not-allowed', !valido);
    }

    inputsPesoRanking.forEach(input => {
        input.addEventListener('input', atualizarSomaPesos);
    });

    function abrirModalFiltrosRanking() {
        atualizarSomaPesos();
        modalFiltrosRanking.classList.remove('hidden');
        modalFiltrosRanking.classList.add('flex');
    }

    function fecharModalFiltrosRanking() {
        modalFiltrosRanking.classList.add('hidden');
        modalFiltrosRanking.classList.remove('flex');
    }

    document.getElementById('btn_abrir_filtros_ranking').addEventListener('click', abrirModalFiltrosRanking);
    document.getElementById('btn_fechar_filtros_ranking').addEventListener('click', fecharModalFiltrosRanking);

    // Fecha o modal de filtros ao clicar no backdrop
    modalFiltrosRanking.addEventListener('click', (e) => {
        if (e.target === modalFiltrosRanking || e.target.classList.contains('bg-black/85')) {
            fecharModalFiltrosRanking();
        }
    });

    // Renderiza a tabela de resultado do ranking a partir dos dados da API
    function renderizarRanking(data) {
        const thead = document.getElementById('tabela_comparacao_head');
        const tbody = document.getElementById('tabela_comparacao_body');
        const titulo = document.getElementById('modal_titulo');
        const subtitulo = document.getElementById('modal_subtitulo');

        thead.innerHTML = `
            <th class="px-4 py-3 font-medium text-gray-400">#</th>
            <th class="px-4 py-3 font-medium text-gray-400">Fundo</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-right">12m</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-right">24m</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-right">36m</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-right">48m</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-right">60m</th>
            <th class="px-4 py-3 font-medium text-neon text-right">Nota</th>
            <th class="px-4 py-3 font-medium text-gray-400 text-center">Volatilidade</th>`;
        tbody.innerHTML = '';

        dataReferenciaRankingAtual = data.data_referencia;

        data.fundos.forEach((fundo, indice) => {
            const linha = document.createElement('tr');
            linha.className = 'border-b border-white/5 hover:bg-white/[0.02]';

            const celulasRentabilidade = PERIODOS_RANKING.map(periodo => `
                <td class="px-4 py-4 text-right" data-periodo="${periodo}">
                    <div class="metric-cell">
                        <span class="rentabilidade text-[10px] font-medium">${formatValue(fundo['rentabilidade_' + periodo])}</span>
                        <span class="vol-slot"></span>
                    </div>
                </td>`).join('');

            linha.innerHTML = `
                <td class="px-4 py-4 text-neon font-semibold text-xs">${indice + 1}</td>
                <td class="px-4 py-4 text-gray-200">
                    <div class="truncate max-w-[200px] text-xs font-medium" title="${fundo.nome}">${fundo.nome}</div>
                    <div class="text-[10px] text-gray-500">${fundo.cnpj}</div>
                </td>
                ${celulasRentabilidade}
                <td class="px-4 py-4 text-right font-bold text-[10px]">${fundo.nota_final.toFixed(4)}</td>
                <td class="px-4 py-4 text-center">
                    <button
                        class="btn-vol-fundo bg-white/5 hover:bg-neon/10 text-gray-300 hover:text-neon border border-white/10 rounded-lg px-3 py-1.5 text-xs whitespace-nowrap transition-colors"
                        data-cnpj="${fundo.cnpj}"
                    >
                        <i class="ph ph-chart-line-up"></i> Ver Volatilidade
                    </button>
                </td>`;
            tbody.appendChild(linha);
        });

        const rotuloCategoria = ROTULOS_CATEGORIA[data.categoria] || data.categoria;
        titulo.textContent = `Ranking Top ${data.fundos.length} de Fundos`;
        subtitulo.textContent = `${data.fundos.length} fundo(s) elegível(is) · Categoria: ${rotuloCategoria} · Referência: ${data.data_referencia}`;
    }

    // Busca o ranking na API com os filtros escolhidos pelo usuário no modal
    async function gerarRanking(quantidade, categoria, pesos) {
        showLoader();
        try {
            const params = new URLSearchParams({
                top_n: quantidade,
                categoria: categoria,
            });

            Object.entries(pesos).forEach(([periodo, valor]) => {
                params.set(`peso_${periodo}`, valor);
            });

            const res = await fetch(`/api/fundos/ranking?${params.toString()}`);
            const data = await res.json();

            if (!res.ok || data.erro) {
                alert(data.erro || 'Não foi possível gerar o ranking.');
                return;
            }

            renderizarRanking(data);
            abrirModalResultado();
        } catch (e) {
            alert('Erro ao gerar o ranking.');
            console.error(e);
        } finally {
            hideLoader();
        }
    }

    btnConfirmarFiltrosRanking.addEventListener('click', () => {
        const soma = Math.round(somaPesosAtual() * 100) / 100;
        if (Math.abs(soma - 100) > 0.01) {
            return; // botão já fica desabilitado, isso aqui é só uma trava extra
        }

        const quantidade = parseInt(document.getElementById('filtro_ranking_quantidade').value, 10);
        const categoria = document.getElementById('filtro_ranking_categoria').value;

        if (!quantidade || quantidade < 1) {
            alert('Informe uma quantidade válida de fundos.');
            return;
        }

        const pesos = {};
        inputsPesoRanking.forEach(input => {
            pesos[input.dataset.periodo] = parseFloat(input.value) || 0;
        });

        fecharModalFiltrosRanking();
        gerarRanking(quantidade, categoria, pesos);
    });

    // Delegação de evento: as linhas do ranking são recriadas a cada
    // geração, então o listener fica no tbody (que é fixo) em vez de em
    // cada botão individualmente.
    document.getElementById('tabela_comparacao_body').addEventListener('click', async (e) => {
        const botao = e.target.closest('.btn-vol-fundo');
        if (!botao) return;

        const cnpj = botao.dataset.cnpj;
        const linha = botao.closest('tr');
        const textoOriginal = botao.innerHTML;

        botao.disabled = true;
        botao.classList.add('opacity-60', 'cursor-wait');
        botao.innerHTML = '<i class="ph ph-spinner animate-spin"></i> Calculando...';

        try {
            const params = new URLSearchParams({ cnpj });
            if (dataReferenciaRankingAtual) {
                params.set('data_referencia', dataReferenciaRankingAtual);
            }

            const res = await fetch(`/api/fundo/volatilidade-ranking?${params.toString()}`);
            const dadosVol = await res.json();

            if (!res.ok || dadosVol.erro) {
                alert(dadosVol.erro || 'Não foi possível calcular a volatilidade deste fundo.');
                botao.disabled = false;
                botao.classList.remove('opacity-60', 'cursor-wait');
                botao.innerHTML = textoOriginal;
                return;
            }

            // Preenche o badge de volatilidade em cada célula de período da linha
            PERIODOS_RANKING.forEach(periodo => {
                const celula = linha.querySelector(`td[data-periodo="${periodo}"] .vol-slot`);
                if (celula) {
                    celula.innerHTML = formatVolatilidade(dadosVol[`volatilidade_${periodo}`]);
                }
            });

            botao.innerHTML = '<i class="ph ph-check-circle"></i> Volatilidade calculada';
            botao.classList.remove('opacity-60', 'cursor-wait');
        } catch (erro) {
            alert('Erro ao calcular volatilidade do fundo.');
            console.error(erro);
            botao.disabled = false;
            botao.classList.remove('opacity-60', 'cursor-wait');
            botao.innerHTML = textoOriginal;
        }
    });

    // ==========================================
    // 8. MODAL DE RESULTADO (Tela Full-Screen)
    // ==========================================

    const modalResultado = document.getElementById('modal_resultado');

    function abrirModalResultado() {
        modalResultado.classList.remove('hidden');
        modalResultado.classList.add('flex');
        document.body.style.overflow = 'hidden';
        modalResultado.querySelector('.relative.z-10').classList.add('result-fade-in');
    }

    function fecharModalResultado() {
        modalResultado.classList.add('hidden');
        modalResultado.classList.remove('flex');
        document.body.style.overflow = '';
    }

    document.getElementById('btn_fechar_modal').addEventListener('click', fecharModalResultado);

    // Fecha ao clicar no backdrop (fora do conteúdo)
    modalResultado.addEventListener('click', (e) => {
        if (e.target === modalResultado || e.target.classList.contains('bg-black/85')) {
            fecharModalResultado();
        }
    });

    // Fecha com ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modalResultado.classList.contains('hidden')) {
            fecharModalResultado();
        }
    });

    // ==========================================
    // 9. INICIALIZAÇÃO
    // ==========================================

    carregarPeriodosPadrao();

});