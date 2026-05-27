(function () {
  const overlayId = 'codeitPageLoading';
  let overlay = null;

  function getOverlay() {
    if (overlay) return overlay;

    overlay = document.getElementById(overlayId);
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = overlayId;
      overlay.className = 'codeit-page-loading';
      overlay.setAttribute('aria-hidden', 'true');
      overlay.innerHTML = '<div class="codeit-page-loading__spinner" role="status" aria-label="Loading"></div>';
      document.body.appendChild(overlay);
    }

    return overlay;
  }

  function show() {
    const node = getOverlay();
    node.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => {
      node.classList.add('is-active');
    });
  }

  function hide() {
    const node = getOverlay();
    node.classList.remove('is-active');
    node.setAttribute('aria-hidden', 'true');
  }

  function shouldSkipForm(form) {
    return (
      !form ||
      form.dataset.noLoading === 'true' ||
      form.target === '_blank'
    );
  }

  function scheduleFormLoading(event) {
    const form = event.target;
    if (shouldSkipForm(form)) return;

    window.setTimeout(() => {
      if (event.defaultPrevented) return;
      show();
    }, 40);
  }

  document.addEventListener('submit', scheduleFormLoading);

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-show-loading="true"]');
    if (!trigger) return;
    window.setTimeout(() => {
      if (!event.defaultPrevented) show();
    }, 40);
  });

  window.addEventListener('pageshow', hide);
  window.addEventListener('pagehide', hide);

  window.CodeitPageLoading = { show, hide };
})();
