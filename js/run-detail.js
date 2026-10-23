(function () {
    const modes = new Set(['type_a', 'type_b']);
    const buttons = document.querySelectorAll('[data-run-score-mode]');
    function setMode(mode) {
        if (!modes.has(mode)) mode = 'type_b';
        buttons.forEach(button => {
            const active = button.dataset.runScoreMode === mode;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        });
        document.querySelectorAll('[data-run-mode-value]').forEach(node => {
            node.textContent = node.getAttribute(`data-${mode}`) || '';
        });
        document.querySelectorAll('[data-run-mode]').forEach(row => {
            row.classList.toggle('hidden', row.dataset.runMode !== mode);
        });
        const url = new URL(window.location.href);
        if (mode === 'type_a') url.searchParams.set('mode', mode);
        else url.searchParams.delete('mode');
        window.history.replaceState(null, '', url);
        const back = document.querySelector('.run-back-link');
        if (back) {
            const base = back.dataset.baseUrl || back.getAttribute('href');
            back.dataset.baseUrl = base;
            back.setAttribute('href', `${base}${mode === 'type_a' ? '?mode=type_a' : ''}`);
        }
    }
    buttons.forEach(button => button.addEventListener('click', () => setMode(button.dataset.runScoreMode)));
    setMode(new URLSearchParams(window.location.search).get('mode'));
})();
