(() => {
  'use strict';
  const metadata = document.querySelector('meta[name="site-root"]');
  const root = new URL(metadata?.content || './', document.baseURI);
  const storageKey = 'spec-compiler-theme';
  const query = new URLSearchParams(location.search);
  if (new URL(location.href).pathname === root.pathname && query.has('ontology')) {
    const target = new URL('ontologies/', root);
    target.search = location.search;
    target.hash = location.hash;
    location.replace(target.href);
    return;
  }
  const theme = () => document.documentElement.dataset.theme || 'light';
  function applyTheme(value, remember = false) {
    const next = value === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    if (remember) {
      try { localStorage.setItem(storageKey, next); } catch {}
    }
    window.dispatchEvent(new CustomEvent('site-theme', {detail: next}));
    document.querySelectorAll('.diagram-frame').forEach(frame => {
      frame.contentWindow?.postMessage({type: 'documentation-theme', theme: next}, location.origin);
    });
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-label', next === 'dark' ? 'Helles Farbschema aktivieren' : 'Dunkles Farbschema aktivieren');
      button.title = button.getAttribute('aria-label');
    });
  }
  let saved;
  try { saved = localStorage.getItem(storageKey); } catch {}
  applyTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  window.addEventListener('storage', event => {
    if (event.key === storageKey) applyTheme(event.newValue);
  });
  document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    button.addEventListener('click', () => applyTheme(theme() === 'dark' ? 'light' : 'dark', true));
  });
  document.querySelectorAll('.diagram-frame').forEach(frame => {
    frame.addEventListener('load', () => frame.contentWindow?.postMessage({type: 'documentation-theme', theme: theme()}, location.origin));
    if (query.get('diagram') === frame.closest('[data-diagram]')?.dataset.diagram && query.get('node')) {
      const url = new URL(frame.src);
      url.hash = 'focus=' + encodeURIComponent(query.get('node'));
      frame.src = url.href;
    }
  });
  window.addEventListener('message', event => {
    if (event.origin !== location.origin) return;
    const frame = Array.from(document.querySelectorAll('.diagram-frame')).find(item => item.contentWindow === event.source);
    if (!frame) return;
    if (event.data?.type === 'documentation-theme-change') applyTheme(event.data.theme, true);
  });
  const dialog = document.getElementById('site-search');
  const input = document.getElementById('site-search-input');
  const results = document.getElementById('site-search-results');
  const status = document.getElementById('site-search-status');
  if (!dialog || !input || !results || !status) return;
  let indexPromise;
  let generation = 0;
  const normalize = value => String(value).normalize('NFKD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('de');
  const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
  const loadIndex = () => indexPromise ||= fetch(new URL('assets/search-index.json', root)).then(response => {
    if (!response.ok) throw new Error('Suchindex nicht erreichbar');
    return response.json();
  });
  async function search() {
    const current = ++generation;
    const text = input.value.trim();
    if (!text) {
      results.replaceChildren();
      status.textContent = 'Tippe einen Suchbegriff.';
      return;
    }
    status.textContent = 'Suche läuft …';
    try {
      const index = await loadIndex();
      if (current !== generation) return;
      const words = normalize(text).split(/\s+/);
      const hits = index.map(entry => {
        const title = normalize(entry.title), body = normalize(entry.text);
        const score = words.every(word => title.includes(word) || body.includes(word))
          ? words.reduce((total, word) => total + (title === word ? 12 : title.startsWith(word) ? 7 : title.includes(word) ? 4 : 1), 0)
          : 0;
        return {entry, score};
      }).filter(hit => hit.score).sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title, 'de'));
      const unique = new Map();
      for (const hit of hits) if (!unique.has(hit.entry.url)) unique.set(hit.entry.url, hit.entry);
      const visible = Array.from(unique.values()).slice(0, 25);
      results.innerHTML = visible.map(entry => {
        const link = new URL(entry.url, root);
        if (link.origin !== root.origin || !link.pathname.startsWith(root.pathname)) return '';
        return '<li><a href="' + escapeHtml(link.href) + '"><span class="search-category">' + escapeHtml(entry.category) + '</span><strong>'
          + escapeHtml(entry.title) + '</strong><small>' + escapeHtml(entry.text.slice(0, 180)) + '</small></a></li>';
      }).join('');
      status.textContent = unique.size ? unique.size + ' Treffer' + (unique.size > 25 ? ' · erste 25 angezeigt' : '') : 'Keine passenden Treffer.';
    } catch {
      if (current === generation) status.textContent = 'Die Suche konnte nicht geladen werden. Bitte erneut versuchen.';
      indexPromise = undefined;
    }
  }
  function openSearch() {
    if (!dialog.open) dialog.showModal();
    input.focus();
    loadIndex().catch(() => {});
  }
  document.querySelectorAll('[data-search-open]').forEach(button => button.addEventListener('click', openSearch));
  input.addEventListener('input', search);
  input.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      results.querySelector('a')?.focus();
    } else if (event.key === 'Enter') {
      const first = results.querySelector('a');
      if (first) { event.preventDefault(); first.click(); }
    }
  });
  results.addEventListener('keydown', event => {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
    const links = Array.from(results.querySelectorAll('a'));
    const position = links.indexOf(document.activeElement);
    if (position < 0) return;
    event.preventDefault();
    const next = position + (event.key === 'ArrowDown' ? 1 : -1);
    if (next < 0) input.focus();
    else links[Math.min(next, links.length - 1)]?.focus();
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openSearch();
    }
  });
})();
