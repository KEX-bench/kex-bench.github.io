(function () {
    'use strict';

    const storageKey = 'kex-bench-theme';
    const themeColor = { light: '#ffffff', dark: '#121312' };

    function storedTheme() {
        try {
            const stored = localStorage.getItem(storageKey);
            return stored === 'light' || stored === 'dark' ? stored : 'dark';
        } catch {
            return 'dark';
        }
    }

    function applyTheme(theme) {
        document.documentElement.dataset.theme = theme;
        document.documentElement.style.colorScheme = theme;
        document.querySelector('meta[name="theme-color"]')?.setAttribute('content', themeColor[theme]);

        const button = document.querySelector('[data-theme-toggle]');
        if (button) {
            const next = theme === 'dark' ? 'light' : 'dark';
            button.dataset.themeState = theme;
            button.title = `Switch to ${next} mode`;
            button.setAttribute('aria-label', `Switch to ${next} mode`);
            button.setAttribute('aria-pressed', String(theme === 'dark'));
        }
    }

    applyTheme(storedTheme());

    document.addEventListener('DOMContentLoaded', () => {
        const button = document.querySelector('[data-theme-toggle]');
        if (!button) return;

        button.addEventListener('click', () => {
            const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
            try { localStorage.setItem(storageKey, next); } catch {}
            applyTheme(next);
        });

        applyTheme(storedTheme());
    });
})();
