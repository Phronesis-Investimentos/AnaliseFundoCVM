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

    // Renderizar chips de períodos
    const renderPeriodosChips = () => {
        divPeriodos.innerHTML = '';
        periodosSelecionados.forEach((p, idx) => {
            const chip = document.createElement('div');
            
            // Estilo diferente para "Desde o Início"
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
        
        // Verifica se o período já existe
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

    // Carregar períodos padrão da API
    async function carregarPeriodosPadrao() {
        try {
            const response = await fetch('/api/periodos/padrao');
            const periodos = await response.json();
            renderizarPeriodosPadrao(periodos);
        } catch (error) {
            console.error('Erro ao carregar períodos padrão:', error);
        }
    }

    // Renderizar botões de períodos padrão
    function renderizarPeriodosPadrao(periodos) {
        const container = document.getElementById('periodos_padrao_container');
        if (!container) return;
        
        container.innerHTML = '';
        
        // Atualiza label com data de referência
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
            
            // Estilo diferente para "Desde o Início"
            btn.className =
                'bg-surface hover:bg-neon/10 text-gray-300 hover:text-neon px-3 py-2 rounded-lg transition-all border border-white/10 text-xs font-medium text-left w-full';
                        
            // Formata as datas para exibição
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

    // Adicionar período padrão à lista
    function adicionarPeriodoPadrao(periodo) {
        // Verifica se o período já foi adicionado
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
                    // Usa o label (ex: "12 Meses (252 du)")
                    label = p.label;
                } else if (p.data_inicial && p.data_final) {
                    // Formata datas
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
                    <td class="px-4 py-4 text-gray-200">
                        <div class="truncate max-w-[250px] font-medium" title="${f.nome}">${f.nome}</div>
                        <div class="text-xs text-gray-500">${f.cnpj}</div>
                    </td>`;
                
                f.variacoes.forEach(v => {
                    // Usa formatValueLarge para "Desde o Início"
                    const valorFormatado = v.tipo === 'desde_inicio' 
                        ? formatValueLarge(v.variacao_percentual)
                        : formatValue(v.variacao_percentual);
                    
                    // Tooltip com informações extras para "Desde o Início"
                    let tooltip = '';
                    if (v.tipo === 'desde_inicio' && v.primeira_data) {
                        tooltip = `title="Desde ${v.primeira_data}"`;
                    }
                    
                    row += `<td class="px-4 py-4 text-right font-medium" ${tooltip}>${valorFormatado}</td>`;
                });
                row += '</tr>';
                tbody.innerHTML += row;
            });

            document.getElementById('resultado_comparacao').classList.remove('hidden');
            
            // Scroll suave até a tabela
            document.getElementById('resultado_comparacao').scrollIntoView({ 
                behavior: 'smooth', 
                block: 'nearest' 
            });
            
        } catch(e) {
            alert('Erro ao comparar fundos.');
            console.error(e);
        } finally {
            hideLoader();
        }
    });

    // ==========================================
    // 7. INICIALIZAÇÃO
    // ==========================================
    
    // Carrega os períodos padrão ao iniciar
    carregarPeriodosPadrao();

});