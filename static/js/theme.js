/**
 * Tema claro/escuro (compartilhado por todas as páginas).
 *
 * Padrão: CLARO. Se o usuário nunca escolheu nada, não aplicamos a
 * classe "dark" (o HTML já nasce sem ela). A escolha fica salva em
 * localStorage e é reaplicada em toda página, antes mesmo do Tailwind
 * carregar (ver o <script> inline no <head> de cada página, que lê a
 * mesma chave pra evitar o "flash" do tema errado).
 */
(function () {
    const CHAVE_LOCALSTORAGE = 'phronesis-theme';

    function temaAtual() {
        return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    }

    function aplicarTema(tema) {
        if (tema === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        localStorage.setItem(CHAVE_LOCALSTORAGE, tema);

        // Avisa o resto da página (ex: portfolio.js redesenha as
        // matrizes de correlação/covariância com cores legíveis pro
        // tema novo) sem acoplamento direto.
        document.dispatchEvent(new CustomEvent('phronesis:tema-mudou', { detail: { tema } }));
    }

    function alternarTema() {
        aplicarTema(temaAtual() === 'dark' ? 'light' : 'dark');
    }

    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('btn_toggle_tema');
        if (btn) {
            btn.addEventListener('click', alternarTema);
        }
    });

    // Expõe pra quem quiser consultar o tema atual (ex: portfolio.js
    // decidindo a cor do texto nas células da matriz).
    window.phronesisTema = { atual: temaAtual, aplicar: aplicarTema, alternar: alternarTema };
})();