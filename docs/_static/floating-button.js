// Inject a floating GitHub button linking to the repository
(function () {
  try {
    const repoUrl = 'https://github.com/fresh-milkshake/research-ai';
    const btn = document.createElement('div');
    btn.className = 'floating-github';
    btn.innerHTML = '<div class="label">Open on GitHub</div>' +
      '<a href="' + repoUrl + '" target="_blank" rel="noopener" aria-label="Open repository on GitHub">' +
      '<svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24" aria-hidden="true">' +
      '<path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.02c-3.34.73-4.04-1.61-4.04-1.61-.55-1.4-1.34-1.77-1.34-1.77-1.1-.75.08-.73.08-.73 1.22.09 1.86 1.25 1.86 1.25 1.08 1.85 2.83 1.31 3.52 1 .11-.78.42-1.31.76-1.61-2.66-.3-5.46-1.33-5.46-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.8 5.62-5.47 5.92.43.37.82 1.1.82 2.22v3.29c0 .32.21.69.83.57A12 12 0 0 0 12 .5Z"></path>' +
      '</svg>' +
      '</a>';
    document.addEventListener('DOMContentLoaded', function () {
      document.body.appendChild(btn);
    });
  } catch (e) {
    // noop
  }
})();


