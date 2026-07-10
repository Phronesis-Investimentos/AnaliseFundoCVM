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
            // Atração magnética
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
            
            // Calcula a rotação
            const rotateX = ((y - centerY) / centerY) * -5; // máx 5 graus
            const rotateY = ((x - centerX) / centerX) * 5;  // máx 5 graus
            
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

    // Debounce function
    function debounce(func, timeout = 300){
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    // ==========================================
    // 3. ANÁLISE INDIVIDUAL
    // ==========================================
    
    const inputBuscaInd = document.getElementById('busca_fundo_individual');
    const listaInd = document.getElementById('lista_fundos_individual');
    const inputCnpjInd = document.getElementById('cnpj_individual');

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

    const fetchBuscaInd = debounce(async (termo) => {
        if(termo.length < 3) {
            listaInd.classList.add('hidden');
            return;
        }
        try {
            const res = await fetch(`/api/fundos/buscar?busca=${encodeURIComponent(termo)}`);
            const data = await res.json();
            renderDropdown(data, listaInd, (item) => {
                inputBuscaInd.value = item.DENOM_SOCIAL;
                inputCnpjInd.value = item.CNPJ_FUNDO;
            });
        } catch (e) { console.error(e); }
    }, 400);

    inputBuscaInd.addEventListener('input', (e) => fetchBuscaInd(e.target.value));
    
    // Fechar dropdown ao clicar fora
    document.addEventListener('click', (e) => {
        if(!inputBuscaInd.contains(e.target)) listaInd.classList.add('hidden');
    });

    document.getElementById('btn_analisar').addEventListener('click', async () => {
        const cnpj = inputCnpjInd.value;
        const dtIni = document.getElementById('data_ini_individual').value;
        const dtFim = document.getElementById('data_fim_individual').value;

        if(!cnpj || !dtIni || !dtFim) {
            alert('Por favor, preencha o fundo e ambas as datas.');
            return;
        }

        showLoader();
        try {
            const res = await fetch('/api/fundo/variacao', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ cnpj, data_inicial: dtIni, data_final: dtFim })
            });
            const data = await res.json();
            
            if(data.erro) {
                alert(data.erro);
            } else {
                const resultDiv = document.getElementById('resultado_individual');
                document.getElementById('valor_variacao').innerHTML = formatValue(data.variacao_percentual);
                resultDiv.classList.remove('hidden');
            }
        } catch(e) {
            alert('Erro ao buscar dados.');
        } finally {
            hideLoader();
        }
    });

    // ==========================================
    // 4. COMPARAÇÃO DE FUNDOS
    // ==========================================
    
    let fundosSelecionados = [];
    let periodosSelecionados = [];

    const inputBuscaComp = document.getElementById('busca_fundo_comparacao');
    const listaComp = document.getElementById('lista_fundos_comparacao');
    const divFundos = document.getElementById('fundos_adicionados');
    const divPeriodos = document.getElementById('periodos_adicionados');

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

    // Períodos
    const renderPeriodosChips = () => {
        divPeriodos.innerHTML = '';
        periodosSelecionados.forEach((p, idx) => {
            const chip = document.createElement('div');
            chip.className = 'flex items-center gap-2 bg-white/5 border border-white/10 text-gray-300 px-3 py-1 rounded-full text-xs animate-fade-in-up';
            chip.innerHTML = `
                <span>${p.data_inicial} até ${p.data_final}</span>
                <i class="ph ph-x cursor-pointer hover:text-white transition-colors" data-idx="${idx}"></i>
            `;
            chip.querySelector('i').addEventListener('click', () => {
                periodosSelecionados.splice(idx, 1);
                renderPeriodosChips();
            });
            divPeriodos.appendChild(chip);
        });
    };

    document.getElementById('btn_add_periodo').addEventListener('click', () => {
        const dI = document.getElementById('comp_data_ini').value;
        const dF = document.getElementById('comp_data_fim').value;
        
        if(!dI || !dF) {
            alert('Preencha as datas do período.'); return;
        }
        
        periodosSelecionados.push({ data_inicial: dI, data_final: dF });
        renderPeriodosChips();
        document.getElementById('comp_data_ini').value = '';
        document.getElementById('comp_data_fim').value = '';
    });

    // Comparar
    document.getElementById('btn_comparar').addEventListener('click', async () => {
        if(fundosSelecionados.length === 0 || periodosSelecionados.length === 0) {
            alert('Adicione pelo menos um fundo e um período.'); return;
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
                thead.innerHTML += `<th class="px-4 py-3 font-medium text-gray-400 text-right">${p.data_inicial} <br> ${p.data_final}</th>`;
            });

            tbody.innerHTML = '';
            data.fundos.forEach(f => {
                let row = `<tr>
                    <td class="px-4 py-4 text-gray-200">
                        <div class="truncate max-w-[250px] font-medium" title="${f.nome}">${f.nome}</div>
                        <div class="text-xs text-gray-500">${f.cnpj}</div>
                    </td>`;
                
                f.variacoes.forEach(v => {
                    row += `<td class="px-4 py-4 text-right font-medium">${formatValue(v.variacao_percentual)}</td>`;
                });
                row += '</tr>';
                tbody.innerHTML += row;
            });

            document.getElementById('resultado_comparacao').classList.remove('hidden');
        } catch(e) {
            alert('Erro ao comparar fundos.');
        } finally {
            hideLoader();
        }
    });

});