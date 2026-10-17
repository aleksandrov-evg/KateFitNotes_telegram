import {escapeHtml as e} from './domain.js';

const instances = new WeakMap();
let sequence = 0;
let opened;
let clients = new Map();
export function setStudioSelectClients(records) {
  clients = new Map(records.map(person => [person.id,person]));
}

export function enhanceStudioSelects(container = document) {
  if (!document.body.classList.contains('studio-mode')) return;
  container.querySelectorAll('select').forEach(select => {
    if (instances.has(select)) return instances.get(select).sync();
    const searchable = select.name === 'personId' || select.id === 'session-person' || select.id === 'calendar-person';
    const wrapper = document.createElement('div');
    wrapper.className = 'studio-select';
    const id = 'studio-select-' + (++sequence);
    const control = document.createElement(searchable ? 'input' : 'button');
    control.type = searchable ? 'search' : 'button';
    control.id = id;
    control.setAttribute('role', 'combobox');
    control.setAttribute('aria-expanded', 'false');
    control.setAttribute('aria-controls', id + '-list');
    control.setAttribute('aria-haspopup', 'listbox');
    if (searchable) {
      control.autocomplete = 'off';
      control.placeholder = 'Введите имя, телефон или email';
      control.setAttribute('aria-autocomplete', 'list');
      control.required = select.required;
    }
    for (const attribute of ['aria-label', 'aria-labelledby']) {
      if (select.hasAttribute(attribute)) control.setAttribute(attribute, select.getAttribute(attribute));
      select.removeAttribute(attribute);
    }
    for (const label of select.labels) if (label.htmlFor) label.htmlFor = id;
    const menu = document.createElement('div');
    menu.className = 'studio-select-menu';
    menu.id = id + '-list';
    menu.setAttribute('role', 'listbox');
    menu.hidden = true;
    select.before(wrapper);
    wrapper.append(control, menu, select);
    select.hidden = true;
    let active = -1;
    let editing = false;
    const buttons = () => [...menu.querySelectorAll('[role=option]')];
    const close = () => { menu.hidden = true; control.setAttribute('aria-expanded', 'false'); control.removeAttribute('aria-activedescendant'); if (opened === close) opened = null; };
    const sync = () => {
      control.disabled = select.disabled;
      if (searchable) control.setCustomValidity(select.required && !select.value ? 'Выберите клиента из списка.' : '');
      if (!editing) {
        const text = select.selectedOptions[0]?.textContent || '';
        if (searchable) control.value = select.value ? text : '';
        else control.textContent = text || 'Выберите…';
      }
      if (!menu.hidden) draw(searchable && editing ? control.value : '');
    };
    const draw = query => {
      const needle = query.trim().toLocaleLowerCase('ru');
      if (searchable) for (const option of select.options) {
        const person = clients.get(option.value);
        const caption = [person?.phones?.primaryPhoneNumber,person?.emails?.primaryEmail].filter(Boolean).join(' · ');
        option.dataset.search = option.textContent + ' ' + caption;
        option.dataset.caption = caption;
      }
      const matches = [...select.options].filter(option => !option.disabled && (!searchable || option.value) && (option.dataset.search || option.textContent).toLocaleLowerCase('ru').includes(needle));
      menu.innerHTML = matches.map((option,index) => `<button type="button" role="option" id="${id}-option-${index}" data-select-value="${e(option.value)}" aria-selected="${String(option.value === select.value)}">${e(option.textContent)}${option.dataset.caption?`<small>${e(option.dataset.caption)}</small>`:''}</button>`).join('') || '<p role="status">Ничего не найдено</p>';
      active = -1; control.removeAttribute('aria-activedescendant');
      buttons().forEach(button => {
        button.onmousedown = event => event.preventDefault();
        button.onclick = () => {
          select.value = button.dataset.selectValue;
          editing = false; close(); sync();
          select.dispatchEvent(new Event('change', {bubbles:true}));
          select.dispatchEvent(new Event('input', {bubbles:true}));
          sync(); control.focus();
        };
      });
    };
    const open = () => {
      if (control.disabled) return;
      if (opened && opened !== close) opened();
      opened = close;
      menu.hidden = false;
      control.setAttribute('aria-expanded', 'true');
      draw(searchable && editing ? control.value : '');
    };
    control.onclick = () => menu.hidden ? open() : (!searchable && close());
    if (searchable) control.oninput = event => {
      event.stopPropagation();
      editing = true;
      if (select.value) { select.value = ''; select.dispatchEvent(new Event('change', {bubbles:true})); }
      select.dispatchEvent(new Event('input', {bubbles:true}));
      open();
    };
    control.onkeydown = event => {
      if (event.key === 'Escape' && !menu.hidden) { event.preventDefault(); event.stopPropagation(); editing = false; close(); sync(); return; }
      if (event.key === 'Tab') { editing = false; close(); sync(); return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); if (menu.hidden) open();
        const options = buttons(); if (!options.length) return;
        active = (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options.forEach((button,index) => button.classList.toggle('is-highlighted',index === active));
        control.setAttribute('aria-activedescendant',options[active].id);
        options[active].scrollIntoView({block:'nearest'});
      }
      if (event.key === 'Enter' && !menu.hidden) { event.preventDefault(); buttons()[active < 0 ? 0 : active]?.click(); }
    };
    wrapper.addEventListener('focusout',event => { if (!wrapper.contains(event.relatedTarget)) { editing = false; close(); sync(); } });
    select.addEventListener('change',sync);
    select.addEventListener('invalid',event => { event.preventDefault(); control.focus(); open(); });
    instances.set(select,{sync}); sync();
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('pointerdown',event => { if (!event.target.closest('.studio-select')) opened?.(); });
  new MutationObserver(records => {
    if (records.some(record => record.target instanceof Element && (record.target.closest('select') || !record.target.closest('.studio-select')))) enhanceStudioSelects();
  }).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
}
