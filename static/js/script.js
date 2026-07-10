console.log("script.js carregado");

let fundosSelecionados = [];


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