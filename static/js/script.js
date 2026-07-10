console.log("script.js carregado");

let fundosSelecionados = [];

// fundos e períodos escolhidos na tela de comparação
let cmpFundos = [];
let cmpPeriodos = [];


document.addEventListener(
    "DOMContentLoaded",
    () => {
        carregarFundos();
        configurarLimitesMeses();
    }
);


const campoFundo =
document.getElementById("fundo_busca");


campoFundo.addEventListener(
    "input",
    buscarFundos
);


// fecha as sugestões se o usuário clicar fora
document.addEventListener("click", function(evento){

    const dentroDoCampo =
        campoFundo.contains(evento.target);

    const dentroDasSugestoes =
        document.getElementById("sugestoes").contains(evento.target);

    if(!dentroDoCampo && !dentroDasSugestoes){
        document.getElementById("sugestoes").innerHTML = "";
    }

});


async function buscarFundos(){

    const termo =
    campoFundo.value.trim();


    if(termo.length < 3){

        document.getElementById(
            "sugestoes"
        ).innerHTML = "";

        return;

    }

    // se o usuário digitar de novo, o CNPJ escolhido antes fica inválido
    document.getElementById("cnpj").value = "";


    try {

        const resposta = await fetch(
            `/api/fundos/buscar?busca=${encodeURIComponent(termo)}`
        );

        if(!resposta.ok){
            console.error("Erro na busca de fundos:", resposta.status);
            return;
        }

        const fundos =
        await resposta.json();

        mostrarSugestoes(fundos);

    } catch (erro) {

        console.error("Erro ao buscar fundos:", erro);

    }

}


function mostrarSugestoes(fundos){


    const div =
    document.getElementById(
        "sugestoes"
    );


    div.innerHTML = "";


    if(fundos.length === 0){

        const vazio = document.createElement("div");

        vazio.className = "sugestao sugestao-vazia";

        vazio.textContent = "Nenhum fundo encontrado";

        div.appendChild(vazio);

        return;

    }


    fundos.forEach(fundo => {


        const item =
        document.createElement(
            "div"
        );


        item.className =
        "sugestao";


        item.textContent =
        fundo.DENOM_SOCIAL;



        item.onclick = function(){


            document.getElementById(
                "fundo_busca"
            ).value =
            fundo.DENOM_SOCIAL;



            document.getElementById(
                "cnpj"
            ).value =
            fundo.CNPJ_FUNDO;



            div.innerHTML = "";



            console.log(
                "CNPJ selecionado:",
                fundo.CNPJ_FUNDO
            );

        };



        div.appendChild(item);


    });


}


async function carregarFundos(){


    const resposta = await fetch(
        "/api/fundos"
    );


    const fundos = await resposta.json();


    const select =
    document.getElementById("fundo");


    if(!select){
        return;
    }


    fundos.forEach(fundo => {


        const opcao =
        document.createElement("option");


        opcao.value =
        fundo.CNPJ_FUNDO;


        opcao.textContent =
        fundo.DENOM_SOCIAL;


        select.appendChild(opcao);


    });


}

function adicionarFundo(){


    const cnpj =
    document.getElementById("cnpj").value;


    const nome =
    document.getElementById("fundo_busca").value;



    if(!cnpj){

        alert(
            "Selecione um fundo"
        );

        return;

    }



    fundosSelecionados.push({

        cnpj:cnpj,

        nome:nome

    });



    mostrarFundos();


}

function mostrarFundos(){


    const div = document.getElementById(
        "fundosSelecionados"
    );

    if(!div){
        return;
    }


    div.innerHTML="";


    fundosSelecionados.forEach(
        (fundo,index)=>{


        div.innerHTML += `

        <div class="result-card">

        ${fundo.nome}

        <button onclick="removerFundo(${index})">
        X
        </button>

        </div>

        `;


    });


}

function removerFundo(index){

    fundosSelecionados.splice(
        index,
        1
    );


    mostrarFundos();

}


function obterUltimoMesCompleto(){

    const hoje = new Date();

    let ano = hoje.getFullYear();
    let mes = hoje.getMonth(); // já é o mês anterior (getMonth() é 0-indexed)

    if(mes === 0){
        mes = 12;
        ano -= 1;
    }

    return { ano, mes };

}


function formatarAnoMes(ano, mes){

    return `${ano}-${String(mes).padStart(2, "0")}`;

}


function configurarLimitesMeses(){

    const { ano, mes } = obterUltimoMesCompleto();

    const limite = formatarAnoMes(ano, mes);

    const campoDataFinal = document.getElementById("data_final");

    if(campoDataFinal){
        campoDataFinal.max = limite;
    }

    const campoPeriodoCompararFinal = document.getElementById("cmp_periodo_data_final");

    if(campoPeriodoCompararFinal){
        campoPeriodoCompararFinal.max = limite;
    }

}


async function consultar() {


    console.log("Botão clicado");


    const cnpj = document
        .getElementById("cnpj")
        .value;


    const data_inicial = document
        .getElementById("data_inicial")
        .value;


    const data_final = document
        .getElementById("data_final")
        .value;



    if (!cnpj || !data_inicial || !data_final) {

        document.getElementById("resultado").innerHTML =
            `
            <p>
            Preencha todos os campos.
            </p>
            `;

        return;

    }



    try {


        const resposta = await fetch(
            "/api/fundo/variacao",
            {

                method: "POST",

                headers: {

                    "Content-Type": "application/json"

                },

                body: JSON.stringify({

                    cnpj: cnpj,

                    data_inicial: data_inicial,

                    data_final: data_final

                })

            }

        );



        const dados = await resposta.json();



        console.log(dados);



        if (dados.erro) {


            document.getElementById("resultado").innerHTML =
            `
            <p>
            ${dados.erro}
            </p>
            `;


            return;

        }




        document.getElementById("resultado").innerHTML =

        `
        <h2>Resultado</h2>

        <p>
        <strong>CNPJ:</strong>
        ${dados.cnpj}
        </p>


        <p>
        <strong>Período:</strong>
        ${dados.data_inicial}
        até
        ${dados.data_final}
        </p>


        <p>
        <strong>Variação:</strong>
        ${dados.variacao_percentual}%
        </p>
        `;



    } catch (erro) {


        console.error(erro);


        document.getElementById("resultado").innerHTML =
        `
        <p>
        Erro ao comunicar com o servidor.
        </p>
        `;


    }


}


/* ---------- Comparação de múltiplos fundos e múltiplos períodos ---------- */


const campoFundoComparar =
document.getElementById("cmp_fundo_busca");


if(campoFundoComparar){

    campoFundoComparar.addEventListener(
        "input",
        buscarFundosComparar
    );

}


// fecha as sugestões da comparação se o usuário clicar fora
document.addEventListener("click", function(evento){

    if(!campoFundoComparar){
        return;
    }

    const divSugestoes = document.getElementById("cmp_sugestoes");

    const dentroDoCampo =
        campoFundoComparar.contains(evento.target);

    const dentroDasSugestoes =
        divSugestoes.contains(evento.target);

    if(!dentroDoCampo && !dentroDasSugestoes){
        divSugestoes.innerHTML = "";
    }

});


async function buscarFundosComparar(){

    const termo = campoFundoComparar.value.trim();

    if(termo.length < 3){
        document.getElementById("cmp_sugestoes").innerHTML = "";
        return;
    }

    try {

        const resposta = await fetch(
            `/api/fundos/buscar?busca=${encodeURIComponent(termo)}`
        );

        if(!resposta.ok){
            console.error("Erro na busca de fundos:", resposta.status);
            return;
        }

        const fundos = await resposta.json();

        mostrarSugestoesComparar(fundos);

    } catch (erro) {

        console.error("Erro ao buscar fundos:", erro);

    }

}


function mostrarSugestoesComparar(fundos){

    const div = document.getElementById("cmp_sugestoes");

    div.innerHTML = "";

    if(fundos.length === 0){

        const vazio = document.createElement("div");

        vazio.className = "sugestao sugestao-vazia";

        vazio.textContent = "Nenhum fundo encontrado";

        div.appendChild(vazio);

        return;

    }

    fundos.forEach(fundo => {

        const item = document.createElement("div");

        item.className = "sugestao";

        item.textContent = fundo.DENOM_SOCIAL;

        item.onclick = function(){

            const jaAdicionado = cmpFundos.some(
                f => f.cnpj === fundo.CNPJ_FUNDO
            );

            if(jaAdicionado){

                alert("Esse fundo já foi adicionado");

            } else {

                cmpFundos.push({
                    cnpj: fundo.CNPJ_FUNDO,
                    nome: fundo.DENOM_SOCIAL
                });

                mostrarFundosComparar();

            }

            campoFundoComparar.value = "";

            div.innerHTML = "";

        };

        div.appendChild(item);

    });

}


function mostrarFundosComparar(){

    const div = document.getElementById("cmp_fundosSelecionados");

    div.innerHTML = "";

    cmpFundos.forEach((fundo, index) => {

        div.innerHTML += `
        <div class="result-card">
            ${fundo.nome}
            <button onclick="removerFundoComparar(${index})">X</button>
        </div>
        `;

    });

}


function removerFundoComparar(index){

    cmpFundos.splice(index, 1);

    mostrarFundosComparar();

}


function adicionarPeriodoComparar(){

    const label = document.getElementById("cmp_periodo_label").value.trim();

    const data_inicial = document.getElementById("cmp_periodo_data_inicial").value;

    const data_final = document.getElementById("cmp_periodo_data_final").value;

    if(!data_inicial || !data_final){
        alert("Preencha data inicial e data final do período");
        return;
    }

    if(data_inicial > data_final){
        alert("A data inicial não pode ser depois da data final");
        return;
    }

    const { ano, mes } = obterUltimoMesCompleto();
    const limite = formatarAnoMes(ano, mes);

    if(data_final > limite){
        alert(`Só é possível consultar até ${limite} (último mês fechado)`);
        return;
    }

    cmpPeriodos.push({
        data_inicial: data_inicial,
        data_final: data_final,
        label: label || `${data_inicial} até ${data_final}`
    });

    document.getElementById("cmp_periodo_label").value = "";
    document.getElementById("cmp_periodo_data_inicial").value = "";
    document.getElementById("cmp_periodo_data_final").value = "";

    mostrarPeriodosComparar();

}


function mostrarPeriodosComparar(){

    const div = document.getElementById("cmp_periodosSelecionados");

    div.innerHTML = "";

    cmpPeriodos.forEach((periodo, index) => {

        div.innerHTML += `
        <div class="result-card">
            ${periodo.label}
            <button onclick="removerPeriodoComparar(${index})">X</button>
        </div>
        `;

    });

}


function removerPeriodoComparar(index){

    cmpPeriodos.splice(index, 1);

    mostrarPeriodosComparar();

}


async function compararFundos(){

    if(cmpFundos.length === 0){
        alert("Adicione ao menos um fundo");
        return;
    }

    if(cmpPeriodos.length === 0){
        alert("Adicione ao menos um período");
        return;
    }

    const divResultado = document.getElementById("cmp_resultado");

    divResultado.innerHTML = `<p>Calculando... isso pode levar alguns minutos na primeira consulta, pois os dados são baixados diretamente da CVM.</p>`;

    try {

        const resposta = await fetch("/api/fundos/comparar", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                fundos: cmpFundos,
                periodos: cmpPeriodos
            })

        });

        const dados = await resposta.json();

        if(dados.erro){
            divResultado.innerHTML = `<p>${dados.erro}</p>`;
            return;
        }

        let cabecalho = "<th>Fundo</th>";

        cmpPeriodos.forEach(periodo => {
            cabecalho += `<th>${periodo.label}</th>`;
        });

        let linhas = "";

        dados.fundos.forEach(fundo => {

            let celulas = `<td>${fundo.nome}</td>`;

            fundo.variacoes.forEach(variacao => {

                const classe = variacao.variacao_percentual >= 0 ? "positive" : "negative";

                celulas += `<td class="${classe}">${variacao.variacao_percentual}%</td>`;

            });

            linhas += `<tr>${celulas}</tr>`;

        });

        divResultado.innerHTML = `
        <table>
            <thead>
                <tr>${cabecalho}</tr>
            </thead>
            <tbody>
                ${linhas}
            </tbody>
        </table>
        `;

    } catch (erro) {

        console.error(erro);

        divResultado.innerHTML = `<p>Erro ao comunicar com o servidor.</p>`;

    }

}