document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-link').forEach(link => {
        const active = link.getAttribute('href') === location.pathname;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', event => {
            queueMicrotask(() => {
                if (event.defaultPrevented || !form.checkValidity()) return;
                const button = event.submitter;
                if (!button || button.name) return;
                button.dataset.originalText = button.innerHTML;
                button.disabled = true;
                button.textContent = 'Processando…';
                button.setAttribute('aria-busy', 'true');
            });
        });
    });
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('[data-original-text]').forEach(button => {
            button.innerHTML = button.dataset.originalText;
            button.disabled = false;
            button.removeAttribute('aria-busy');
        });
    });
    const search = document.querySelector('[data-product-search]');
    if (!search) return;
    const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
    const rows = [...document.querySelectorAll('[data-product-row]')].map(row => ({row, text: normalize(row.dataset.productRow)}));
    const progress = document.getElementById('count-progress');
    const updateProgress = () => {
        const filled = rows.filter(({row}) => [...row.querySelectorAll('input')].some(input => input.value !== '')).length;
        progress.textContent = filled + ' de ' + rows.length + ' produtos preenchidos';
    };
    document.querySelectorAll('.count-table input').forEach(input => input.addEventListener('input', updateProgress));
    updateProgress();
    let frame;
    search.addEventListener('input', () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
            const term = normalize(search.value.trim());
            let visible = 0;
            rows.forEach(({row, text}) => { row.hidden = !text.includes(term); if (!row.hidden) visible++; });
            document.getElementById('search-empty').hidden = visible !== 0;
            document.getElementById('search-result').textContent = visible + ' produtos';
        });
    });
});
