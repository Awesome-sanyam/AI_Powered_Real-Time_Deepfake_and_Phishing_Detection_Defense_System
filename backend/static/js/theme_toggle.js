/**
 * DEFENCESYS — Enterprise Theme Toggle & Engine
 * ===============================================
 * Ensures Dark Mode remains the sleek default, while Light Mode renders as
 * a clean, high-contrast, professional light theme.
 *
 * Core Logic:
 *  - Reads localStorage.getItem('theme'). Defaults to 'dark' if unset.
 *  - Toggles 'dark' class on document.documentElement.
 *  - Binds click listener to #theme-toggle-btn (and #theme-toggle).
 *  - Broadcasts 'themeChanged' CustomEvent for Vis.js & canvas re-renders.
 *  - Eliminates visual flashes with instant execution in <head>.
 */
(function() {
    'use strict';

    const STORAGE_KEY = 'theme';

    /**
     * Determine initial theme ('dark' | 'light').
     * Defaults to 'dark' if unset in localStorage.
     */
    function getStoredTheme() {
        try {
            const stored = localStorage.getItem('theme');
            if (stored === 'dark' || stored === 'light') {
                return stored;
            }
        } catch (e) {
            // LocalStorage inaccessible (e.g. sandboxed iframe)
        }
        // Default to dark mode for enterprise SOC dashboard aesthetic
        return 'dark';
    }

    /**
     * Update toggle button icon and accessible labels.
     */
    function updateIcon(isDark) {
        const toggleButtons = document.querySelectorAll('#theme-toggle-btn, #theme-toggle, [data-theme-toggle]');
        toggleButtons.forEach((btn) => {
            btn.setAttribute('aria-label', isDark ? 'Switch to Light mode' : 'Switch to Dark mode');
            btn.setAttribute('title', isDark ? 'Switch to Light mode' : 'Switch to Dark mode');

            const icon = btn.querySelector('#theme-toggle-icon, .theme-toggle-icon') || btn.querySelector('i');
            if (icon) {
                if (isDark) {
                    icon.className = 'fa-solid fa-sun text-amber-400 text-sm';
                } else {
                    icon.className = 'fa-solid fa-moon text-slate-600 dark:text-zinc-300 text-sm';
                }
            }
        });
    }

    /**
     * Toggle current theme between dark and light.
     */
    function toggleTheme() {
        const isDark = document.documentElement.classList.toggle('dark');
        try {
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        } catch (e) {}
        updateIcon(isDark);

        // Dispatch notification event for Vis.js canvas, chart re-renders & HUDs
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: isDark ? 'dark' : 'light', isDark: isDark }
        }));
    }

    /**
     * Apply a specific theme ('dark' | 'light').
     */
    function applyTheme(theme, dispatch = false) {
        const isDark = (theme === 'dark');
        if (isDark) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        try {
            localStorage.setItem('theme', theme);
        } catch (e) {}
        updateIcon(isDark);

        if (dispatch) {
            window.dispatchEvent(new CustomEvent('themeChanged', {
                detail: { theme: isDark ? 'dark' : 'light', isDark: isDark }
            }));
        }
    }

    // Expose on window for programmatic control
    window.toggleTheme = toggleTheme;
    window.DEFENCESYS_THEME = {
        getTheme: () => document.documentElement.classList.contains('dark') ? 'dark' : 'light',
        setTheme: (t) => applyTheme(t, true),
        toggle: toggleTheme,
    };

    // Immediate flash-free execution (runs synchronously in <head>)
    const initialTheme = getStoredTheme();
    if (initialTheme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }

    // Attach listeners on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initUI);
    } else {
        initUI();
    }

    function initUI() {
        const isDark = document.documentElement.classList.contains('dark');
        updateIcon(isDark);

        // Explicit click binding for toggle button
        const btn = document.getElementById('theme-toggle-btn') || document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                toggleTheme();
            });
        }

        // Delegated listener for any dynamically inserted or alternate toggle elements
        document.addEventListener('click', (e) => {
            const target = e.target.closest('#theme-toggle-btn, #theme-toggle, [data-theme-toggle]');
            if (target && target !== btn) {
                e.preventDefault();
                toggleTheme();
            }
        });
    }
})();
