(function () {
  const enhancedAttr = 'data-codeit-select-enhanced';
  const registry = new WeakMap();
  let activeState = null;
  let listIdCounter = 0;

  function shouldEnhance(select) {
    return (
      select instanceof HTMLSelectElement &&
      !select.multiple &&
      !select.hasAttribute(enhancedAttr) &&
      !select.hasAttribute('data-native-select') &&
      !select.closest('.codeit-select')
    );
  }

  function optionText(option) {
    return option ? option.textContent.trim() : 'Select';
  }

  function selectedOption(select) {
    return select.selectedOptions[0] || select.options[select.selectedIndex] || select.options[0] || null;
  }

  function copySelectSizing(select, wrapper, originalParent) {
    const isAuthField = originalParent && (
      originalParent.classList.contains('student-auth__field') ||
      originalParent.classList.contains('figma-field')
    );

    if (select.classList.contains('form-select-sm')) {
      wrapper.classList.add('codeit-select--small');
    }

    if (isAuthField) {
      wrapper.classList.add('codeit-select--field');
      wrapper.style.width = '100%';
      wrapper.style.height = '100%';
      return;
    }

    if (select.style.width) {
      wrapper.style.width = select.style.width;
    } else if (!select.classList.contains('form-select-sm') && !select.style.minWidth) {
      wrapper.classList.add('codeit-select--block');
    }

    if (select.style.minWidth) {
      wrapper.style.minWidth = select.style.minWidth;
    }

    if (select.style.maxWidth) {
      wrapper.style.maxWidth = select.style.maxWidth;
    }
  }

  function syncButton(state) {
    const option = selectedOption(state.select);
    state.label.textContent = optionText(option);
    state.wrapper.classList.toggle('is-disabled', state.select.disabled);
    state.wrapper.classList.toggle('is-placeholder', !state.select.value);
    state.button.disabled = state.select.disabled;
    state.button.setAttribute('aria-disabled', state.select.disabled ? 'true' : 'false');
  }

  function closeActive() {
    if (!activeState) return;
    activeState.wrapper.classList.remove('is-open');
    activeState.button.setAttribute('aria-expanded', 'false');
    if (activeState.list) {
      activeState.list.remove();
      activeState.list = null;
    }
    activeState = null;
  }

  function positionList(state) {
    if (!state.list) return;
    const rect = state.button.getBoundingClientRect();
    const margin = 8;
    const spaceBelow = window.innerHeight - rect.bottom - margin;
    const spaceAbove = rect.top - margin;
    const opensUp = spaceBelow < 180 && spaceAbove > spaceBelow;
    const available = Math.max(120, Math.min(280, (opensUp ? spaceAbove : spaceBelow) - margin));
    const width = Math.max(rect.width, 120);
    const left = Math.min(Math.max(margin, rect.left), window.innerWidth - width - margin);
    const top = opensUp
      ? Math.max(margin, rect.top - available - 6)
      : Math.min(window.innerHeight - margin, rect.bottom + 6);

    state.list.style.left = left + 'px';
    state.list.style.top = top + 'px';
    state.list.style.width = width + 'px';
    state.list.style.maxHeight = available + 'px';
    state.list.dataset.placement = opensUp ? 'top' : 'bottom';
  }

  function selectOption(state, index) {
    const option = state.select.options[index];
    if (!option || option.disabled) return;

    state.select.selectedIndex = index;
    state.wrapper.classList.remove('is-invalid');
    syncButton(state);
    state.select.dispatchEvent(new Event('change', { bubbles: true }));
    closeActive();
    state.button.focus();
  }

  function focusOption(list, direction) {
    const options = Array.from(list.querySelectorAll('.codeit-select__option:not([aria-disabled="true"])'));
    if (!options.length) return;
    const currentIndex = options.indexOf(document.activeElement);
    const nextIndex = currentIndex < 0
      ? 0
      : (currentIndex + direction + options.length) % options.length;
    options[nextIndex].focus();
  }

  function buildList(state) {
    const list = document.createElement('div');
    list.className = 'codeit-select__list';
    list.id = state.listId;
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', state.select.getAttribute('aria-label') || state.select.name || 'Dropdown options');

    Array.from(state.select.options).forEach((option, index) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'codeit-select__option';
      item.textContent = optionText(option);
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', option.selected ? 'true' : 'false');
      item.dataset.index = String(index);

      if (!option.value) {
        item.classList.add('is-placeholder');
      }

      if (option.selected) {
        item.classList.add('is-selected');
      }

      if (option.disabled) {
        item.setAttribute('aria-disabled', 'true');
        item.tabIndex = -1;
      }

      item.addEventListener('click', () => selectOption(state, index));
      list.appendChild(item);
    });

    list.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeActive();
        state.button.focus();
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        focusOption(list, 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        focusOption(list, -1);
      } else if (event.key === 'Enter' || event.key === ' ') {
        const item = event.target.closest('.codeit-select__option');
        if (item) {
          event.preventDefault();
          selectOption(state, Number(item.dataset.index));
        }
      }
    });

    return list;
  }

  function openSelect(state) {
    if (state.select.disabled) return;
    if (activeState === state) {
      closeActive();
      return;
    }

    closeActive();
    syncButton(state);
    state.list = buildList(state);
    document.body.appendChild(state.list);
    state.wrapper.classList.add('is-open');
    state.button.setAttribute('aria-expanded', 'true');
    activeState = state;
    positionList(state);

    const selected = state.list.querySelector('.codeit-select__option.is-selected:not([aria-disabled="true"])');
    const first = state.list.querySelector('.codeit-select__option:not([aria-disabled="true"])');
    (selected || first)?.focus({ preventScroll: true });
  }

  function refreshOpenList(state) {
    if (activeState !== state || !state.list) return;
    state.list.remove();
    state.list = buildList(state);
    document.body.appendChild(state.list);
    positionList(state);
  }

  function enhanceSelect(select) {
    if (!shouldEnhance(select)) return;

    const originalParent = select.parentElement;
    const wrapper = document.createElement('div');
    const button = document.createElement('button');
    const label = document.createElement('span');
    const listId = 'codeit-select-list-' + (++listIdCounter);

    wrapper.className = 'codeit-select';
    copySelectSizing(select, wrapper, originalParent);

    button.type = 'button';
    button.className = 'codeit-select__button';
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', listId);

    label.className = 'codeit-select__label';
    button.appendChild(label);

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(button);

    select.classList.add('codeit-select__native');
    select.setAttribute(enhancedAttr, 'true');

    const state = { select, wrapper, button, label, list: null, listId };
    registry.set(select, state);

    syncButton(state);

    button.addEventListener('click', event => {
      event.preventDefault();
      openSelect(state);
    });

    button.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openSelect(state);
      }
    });

    select.addEventListener('change', () => {
      syncButton(state);
      refreshOpenList(state);
    });

    select.addEventListener('invalid', () => {
      state.wrapper.classList.add('is-invalid');
      state.button.focus();
    });

    const observer = new MutationObserver(() => {
      syncButton(state);
      refreshOpenList(state);
    });

    observer.observe(select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled']
    });
  }

  function enhanceAll(root) {
    if (!root) return;
    if (root instanceof HTMLSelectElement) {
      enhanceSelect(root);
      return;
    }
    root.querySelectorAll?.('select').forEach(enhanceSelect);
  }

  function boot() {
    enhanceAll(document);

    const pageObserver = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => enhanceAll(node));
      });
    });

    pageObserver.observe(document.body, { childList: true, subtree: true });
  }

  document.addEventListener('click', event => {
    const label = event.target.closest('label[for]');
    if (!label) return;
    const select = document.getElementById(label.getAttribute('for'));
    const state = registry.get(select);
    if (!state) return;
    event.preventDefault();
    openSelect(state);
  });

  document.addEventListener('pointerdown', event => {
    if (!activeState) return;
    if (activeState.wrapper.contains(event.target) || activeState.list?.contains(event.target)) {
      return;
    }
    closeActive();
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeActive();
    }
  });

  window.addEventListener('resize', () => {
    if (activeState) positionList(activeState);
  });

  window.addEventListener('scroll', event => {
    if (!activeState) return;
    if (activeState.list && activeState.list.contains(event.target)) return;
    closeActive();
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
