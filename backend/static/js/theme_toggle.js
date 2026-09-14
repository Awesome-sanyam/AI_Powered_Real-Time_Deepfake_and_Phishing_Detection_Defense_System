/**
 * DEFENCESYS — Enterprise Theme Toggle & Styling Manager
 * =======================================================
 * Manages dark/light theme switching with:
 *  - Immediate flash-free initialisation
 *  - LocalStorage persistence
 *  - OS 'prefers-color-scheme' fallback
 *  - Custom 'themeChanged' event broadcast for canvas & Vis.js network re-renders
 *  - Accessible aria attributes & smooth icon transitions
 */
(function() {
    'use strict';

    const STORAGE_KEY = 'theme';

    /**
     * Determine current active theme ('dark' | 'light').
     */
    function getStoredTheme() {
        try {
            const stored = localStorage.getItem('theme') || localStorage.getItem('defencesys_theme');
            if (stored === 'dark' || stored === 'light') return stored;
        } catch (e) {
            // LocalStorage inaccessible (e.g. sandboxed iframe)
        }
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    /**
     * Apply the theme to documentElement and dispatch notification event.
     */
    function applyTheme(theme, dispatch = true) {
        const isDark = (theme === 'dark');
        const root = document.documentElement;

        if (isDark) {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }

        try {
            localStorage.setItem(STORAGE_KEY, theme);
            localStorage.setItem('theme', theme); // backward compatibility
        } catch (e) {}

        // Update all theme toggle buttons and icons on the page
        updateToggleButtons(isDark);

        if (dispatch) {
            window.dispatchEvent(new CustomEvent('themeChanged', {
                detail: { theme: isDark ? 'dark' : 'light', isDark: isDark }
            }));
        }
    }

    /**
     * Update icon and title on any theme toggle buttons.
     */
    function updateToggleButtons(isDark) {
        const toggleButtons = document.querySelectorAll('#theme-toggle, [data-theme-toggle]');
        toggleButtons.forEach((btn) => {
            btn.setAttribute('aria-label', isDark ? 'Switch to Light mode' : 'Switch to Dark mode');
            btn.setAttribute('title', isDark ? 'Switch to Light mode' : 'Switch to Dark mode');

            const icon = btn.querySelector('#theme-toggle-icon, .theme-toggle-icon');
            if (icon) {
                if (isDark) {
                    icon.classList.remove('fa-moon');
                    icon.classList.add('fa-sun', 'text-amber-400');
                } else {
                    icon.classList.remove('fa-sun', 'text-amber-400');
                    icon.classList.add('fa-moon');
                }
            }
        });
    }

    /**
     * Toggle current theme.
     */
    function toggleTheme() {
        const isCurrentDark = document.documentElement.classList.contains('dark');
        applyTheme(isCurrentDark ? 'light' : 'dark', true);
    }

    // Expose on window
    window.DEFENCESYS_THEME = {
        getTheme: () => document.documentElement.classList.contains('dark') ? 'dark' : 'light',
        setTheme: (t) => applyTheme(t, true),
        toggle: toggleTheme,
    };

    // Apply immediately to prevent any flash of unstyled theme
    const initialTheme = getStoredTheme();
    applyTheme(initialTheme, false);

    // Bind event listeners on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        const isDark = document.documentElement.classList.contains('dark');
        updateToggleButtons(isDark);

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('#theme-toggle, [data-theme-toggle]');
            if (btn) {
                e.preventDefault();
                toggleTheme();
            }
        });

        // Listen for system theme changes if user hasn't explicitly set preference
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('theme');
                if (!stored) {
                    applyTheme(e.matches ? 'dark' : 'light', true);
                }
            });
        }
    });
})();
