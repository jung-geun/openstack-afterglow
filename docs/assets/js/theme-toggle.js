(() => {
  const storageKey = 'afterglow-docs-theme';
  const root = document.documentElement;
  const label = (theme) => theme === 'dark' ? '라이트 모드' : '다크 모드';

  const setTheme = (theme, persist = true) => {
    root.dataset.theme = theme;
    if (persist) window.localStorage.setItem(storageKey, theme);
    window.dispatchEvent(new CustomEvent('afterglow-theme-change', { detail: { theme } }));
    const button = document.querySelector('.theme-toggle');
    if (button) {
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      button.textContent = label(theme);
    }
  };

  const installToggle = () => {
    const target = document.querySelector('.aux-nav') || document.querySelector('.site-header') || document.querySelector('.main-header');
    if (!target || target.querySelector('.theme-toggle')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'theme-toggle';
    button.setAttribute('aria-label', '문서 색상 테마 전환');
    button.addEventListener('click', () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark'));
    target.prepend(button);
    setTheme(root.dataset.theme || 'light', false);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installToggle, { once: true });
  else installToggle();
})();
