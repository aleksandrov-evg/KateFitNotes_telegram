import {Api} from './api.js';
import './studio-select.js';
import {StudioUi} from './studio.js';
import {studioNav, studioCrmError} from './studio-domain.js';
import {escapeHtml as e, today, addDays, weekStart, weekDays, formatDate, money, clientName, phoneLabel, normalizePhone, integer, activePackages, priceHint, slots, bookingPayload} from './domain.js';

const root = document.querySelector('#app');
const dialog = document.querySelector('#confirm');
const nav = [['overview','Обзор','grid'],['schedule','Расписание','calendar'],['clients','Клиенты','users'],['personal','Перс. запись','user'],['group','Группа','users'],['prepaid','Предоплата','wallet'],['reports','Отчёт','chart']];
const state = {clients:[],types:[],bookings:[],packages:[],reports:[],ready:false,page:'overview',week:weekStart(today()),year:today().slice(0,4),month:today().slice(0,7),query:'',packageFilter:'active',draft:null};
let terfitLoaded = false;
let generation = 0, slotGeneration = 0, saving = false, noticeTimer;
const api = new Api({onUnauthorized:() => logout('Сессия завершена. Войдите снова.')});
const studio = new StudioUi({api,page,header,notify,errorBox,showDialog});
const isStudio = () => location.hash.startsWith('#gelios/');
const modeSelector = () => `<label class="workspace-switch"><span>Рабочее пространство</span><select id="workspace-mode" aria-label="Рабочее пространство"><option value="terfit" ${!isStudio()?'selected':''}>Terfit · персональный учёт</option><option value="gelios" ${isStudio()?'selected':''}>Студия Gelios · CRM</option></select></label>`;
function icon(name) {
  const paths = {grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',calendar:'M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4',users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-4 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',user:'M20 21v-2a7 7 0 0 0-14 0v2 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',wallet:'M3 5h17v16H3z M3 5V3h14 M15 11h6v5h-6z',chart:'M4 3v18h17 M8 17v-5 M13 17V7 M18 17V3',exit:'M9 4H4v16h5 M9 12h12 M17 8l4 4-4 4',menu:'M4 6h16 M4 12h16 M4 18h16',plus:'M12 5v14 M5 12h14',arrow:'M5 12h14 M14 7l5 5-5 5'};
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.grid}"/></svg>`;
}
const link = (page,label,cls='secondary') => `<a class="button ${cls}" href="#${page}">${label}</a>`;
const empty = (text='Пока нет записей') => `<div class="empty">${e(text)}</div>`;
const person = id => state.clients.find(c=>c.id===Number(id));
const type = id => state.types.find(t=>t.id===Number(id));
const name = id => clientName(person(id) || {id});
const typeName = id => type(id)?.type_train || 'Тренировка';
const field = (label,html) => `<label class="field"><span>${label}</span>${html}</label>`;
function notify(message) {
  clearTimeout(noticeTimer); const box = document.querySelector('#notice'); box.textContent = message; box.classList.add('visible');
  noticeTimer = setTimeout(()=>box.classList.remove('visible'),6000);
}
function errorBox(error, target = '#page-error', context = {}) {
  const box = document.querySelector(target);
  if (!box) return;
  const message = error.message || String(error);
  if (target === '#page-error' && isStudio()) {
    const view = studioCrmError(message, context.requestBody, error.details?.crmPayload);
    box.classList.add('crm-error');
    const crmPayload = view.crmPayload ? JSON.stringify(view.crmPayload, null, 2) : '';
    box.innerHTML = `<div class="crm-error-icon" aria-hidden="true">!</div><div><strong>${e(view.title)}</strong><p>${e(view.description)}</p><details><summary>Технические детали</summary><span>Ответ CRM</span><code>${e(view.technical)}</code>${crmPayload?`<span>Запрос, отправленный в CRM</span><pre>${e(crmPayload)}</pre>`:''}${view.payload?`<span>${crmPayload?'Исходный запрос UI':'Отправленный запрос'}</span><pre>${e(view.payload)}</pre>`:''}</details></div>`;
  } else {
    box.classList.remove('crm-error');
    box.textContent = message;
  }
  box.hidden = false;
  box.scrollIntoView({block:'nearest'});
}
function logout(message = '') {
  generation++; slotGeneration++; api.setToken(''); state.ready=false; terfitLoaded=false; studio.reset();
  for (const key of ['clients','bookings','packages','types','reports']) state[key]=[];
  state.draft=null; dialog.close(); renderLogin(); if(message) notify(message);
}
function renderLogin() {
  document.body.classList.remove('studio-mode');
  root.innerHTML = `<div class="login"><section class="brand-panel"><span class="eyebrow">персональный учёт</span><h1>Клиенты, записи и пакеты — в одном месте.</h1><p>Больше внимания клиентам.<br>Меньше времени на учёт.</p><span class="brand-bottom">KATEFIT <b>NOTES</b></span></section><main class="login-area"><form id="login-form" class="login-form"><div class="brand">KateFit Notes<span>рабочий стол тренера</span></div><h2>С возвращением</h2><p>Войдите, чтобы управлять тренировками, клиентами и предоплатами.</p>${field('Логин','<input name="username" autocomplete="username" required autofocus>')}${field('Пароль','<input name="password" type="password" autocomplete="current-password" required>')}<div id="login-error" class="error" role="alert" hidden></div><button class="primary" type="submit">Войти ${icon('arrow')}</button><small>Ваше расписание. Ваш ритм.</small></form></main></div>`;
  document.querySelector('#login-form').onsubmit=async event=>{
    event.preventDefault(); const form=event.currentTarget, button=form.querySelector('button'); button.disabled=true; button.textContent='Входим…';
    try { const data=await api.request('/auth/login',{method:'POST',body:Object.fromEntries(new FormData(form))}); api.setToken(data.access_token); await load(); }
    catch(error) { errorBox(error,'#login-error'); }
    finally {button.disabled=false; button.innerHTML=`Войти ${icon('arrow')}`;}
  };
}
async function load() {
  const run=++generation;
  if(isStudio()){state.ready=true;render();return;}
  root.innerHTML='<div class="loading" role="status"><div class="brand">KateFit Notes</div><p>Загружаем рабочий стол…</p></div>';
  try {
    const [clients,types,bookings,packages,reports]=await Promise.all([api.all('/clients'),api.request('/train-types'),api.all('/bookings'),api.all('/prepaid'),api.request('/reports/monthly')]);
    if(run!==generation) return;
    Object.assign(state,{clients,types,bookings,packages,reports,ready:true}); terfitLoaded=true; render();
  } catch(error) {
    if(run!==generation) return;
    root.innerHTML=`<main class="loading"><h1>Не удалось загрузить данные</h1><p class="error">${e(error.message)}</p><button class="primary" id="retry">Повторить</button><button id="exit">Выйти</button></main>`;
    document.querySelector('#retry').onclick=load; document.querySelector('#exit').onclick=()=>logout();
  }
}
function currentPage() { const page=location.hash.slice(1).split('?')[0]; const items=isStudio()?studioNav:nav; return items.some(n=>n[0]===page)?page:isStudio()?'gelios/overview':'overview'; }
function render() {
  if(!api.token) return renderLogin();
  if(!state.ready) return;
  if(!isStudio()&&!terfitLoaded){studio.deactivate();return load();}
  const activeNav=isStudio()?studioNav:nav;
  document.body.classList.toggle('studio-mode',isStudio());
  const page=currentPage(); if(page!==state.page) {state.draft=null;state.query='';} state.page=page;
  root.innerHTML=`<div class="app-shell ${isStudio()?'studio-shell':''}"><aside class="sidebar"><a href="${isStudio()?'#gelios/overview':'#overview'}" class="brand">${isStudio()?'Studio Gelios':'KateFit Notes'}<span>${isStudio()?'Рабочее место оператора':'рабочий стол тренера'}</span></a>${modeSelector()}<nav aria-label="Основная навигация">${activeNav.map(([id,label,glyph])=>`<a href="#${id}" class="nav-item ${page===id?'active':''}" ${page===id?'aria-current="page"':''}>${icon(glyph)}${label}</a>`).join('')}</nav><div class="account"><span class="avatar accent">К</span><div>Катя<small>${isStudio()?'Оператор студии':'один аккаунт'}</small></div><button id="logout" class="icon-button" aria-label="Выйти">${icon('exit')}</button></div></aside><div class="mobile-header"><a class="brand" href="${isStudio()?'#gelios/overview':'#overview'}">${isStudio()?'Studio Gelios':'KATEFIT <b>NOTES</b>'}</a><button id="menu-toggle" class="icon-button" aria-label="Открыть меню" aria-expanded="false">${icon('menu')}</button></div><main id="main" tabindex="-1"><div id="page-error" class="error" role="alert" hidden></div><div id="page"></div></main></div>`;
  document.querySelector('#logout').onclick=()=>logout();
  document.querySelector('#workspace-mode').onchange=event=>{if(saving||studio.saving){event.target.value=isStudio()?'gelios':'terfit';return notify('Дождитесь ответа сервера.');} studio.deactivate();location.hash=event.target.value==='gelios'?'gelios/overview':'overview';};
  document.querySelector('#menu-toggle').onclick=event=>{const open=root.querySelector('.app-shell').classList.toggle('menu-open');event.currentTarget.setAttribute('aria-expanded',String(open));};
  if(isStudio())return studio.render(page.split('/')[1]);
  studio.deactivate();
  ({overview:renderOverview,schedule:renderSchedule,clients:renderClients,personal:renderBooking,group:renderBooking,prepaid:renderPrepaid,reports:renderReports})[page]();
}
function header(title,subtitle,actions='') {return `<header class="page-header"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="actions">${actions}${isStudio()?'<nav class="workspace-tabs" aria-label="Режим рабочего стола"><a href="#overview">Terfit</a><a href="#gelios/overview" aria-current="true">Studio Gelios</a></nav>':''}<button class="icon-button refresh" title="Обновить данные" aria-label="Обновить данные">↻</button></div></header>`;}
function page(html) {document.querySelector('#page').innerHTML=html;const refresh=document.querySelector('.refresh');if(refresh)refresh.onclick=()=>{state.draft=null;load();};}
function metrics(report, count, detail='занятий в этом месяце') {
  return `<div class="metrics">${[['Прибыль',money(report?.income),'за вычетом аренды'],['Выручка',money(report?.total_sum),'сумма занятий'],['Аренда',money(report?.sum_rent),'расходы на студию'],['Занятий',count,detail]].map(([label,value,caption])=>`<section class="metric"><span>${label}</span><strong>${e(value)}</strong><small>${caption}</small></section>`).join('')}</div>`;
}
function bookingTitle(b) {return b.is_group?`Группа · ${(b.participants||[]).length} чел.`:name(b.client);}
function bookingRows(bookings) {
  return bookings.length?`<div class="booking-list">${bookings.map(b=>`<button class="booking-row" data-booking="${b.id}"><time>${e(b.time.slice(0,5))}</time><div><strong>${e(bookingTitle(b))}</strong><small>${e(typeName(b.type_train_id))} · ${e(formatDate(b.date))}</small></div><span class="badge">${b.accounting_id?'по пакету':e(money(b.price))}</span></button>`).join('')}</div>`:empty('Занятий пока нет. Добавьте первую запись.');
}
function wireBookingDetails() {
  document.querySelectorAll('[data-booking]').forEach(button=>button.onclick=()=>{
    const b=state.bookings.find(b=>b.id===Number(button.dataset.booking));if(!b)return;
    showDialog('Запись на тренировку',`<dl><dt>Когда</dt><dd>${e(formatDate(b.date))} · ${e(b.time.slice(0,5))}</dd><dt>Тип</dt><dd>${e(typeName(b.type_train_id))}</dd><dt>Участники</dt><dd>${e((b.participants?.length?b.participants:[b.client]).map(name).join(', '))}</dd><dt>Оплата</dt><dd>${e(money(b.price))}${b.accounting_id?' · по пакету':''}</dd><dt>Аренда</dt><dd>${e(money(b.rent_debt))}</dd></dl>`);
    dialog.querySelector('.dialog-actions').insertAdjacentHTML('afterbegin','<button id="delete-booking" class="danger" type="button">Удалить тренировку</button>');
    dialog.querySelector('#delete-booking').onclick=()=>{
      showDialog('Удалить тренировку?',`<p>${e(formatDate(b.date))} · ${e(b.time.slice(0,5))} · ${e(typeName(b.type_train_id))}</p><p class="deletion-note">${b.is_group?'Будет удалена вся групповая тренировка со всеми участниками.':'Запись будет удалена из расписания.'} ${b.accounting_id?'Посещение вернётся в остаток связанного пакета. Возврата денег эта операция не делает.':'Денежный возврат эта операция не выполняет.'} Отменить удаление нельзя.</p>`,async()=>{
        await api.request('/bookings/'+b.id,{method:'DELETE'});
        await load();notify('Тренировка удалена. Данные обновлены.');
      });
      const confirm=dialog.querySelector('#dialog-submit');confirm.textContent='Удалить тренировку';confirm.className='danger';
    };
  });
}
function renderOverview() {
  const date=today(), month=date.slice(0,7), monthBookings=state.bookings.filter(b=>b.date.startsWith(month));
  const sessions=state.bookings.filter(b=>b.date===date).sort((a,b)=>a.time.localeCompare(b.time));
  const low=state.packages.filter(p=>!p.is_complete&&p.remaining!=null&&p.remaining<=5).sort((a,b)=>a.remaining-b.remaining);
  page(header('Обзор',e(formatDate(date,{weekday:'long',day:'numeric',month:'long',year:'numeric'})),`${link('personal','+ Перс. запись','ghost')}${link('group','+ Группа','ghost')}${link('prepaid','Предоплата','primary')}`)+metrics(state.reports.find(r=>r.month?.startsWith(month)),monthBookings.length)+`<div class="overview-grid"><section class="panel today-panel"><div class="section-header"><h2>Сегодня</h2><small>${sessions.length} занятий</small></div>${bookingRows(sessions)}<div class="mobile-book">${link('personal','Добавить запись','primary')}</div></section><aside class="stack"><section class="panel"><h2>Пакеты на исходе</h2>${low.length?low.map(p=>`<a href="#prepaid" class="package-alert"><span>${e(name(p.client_id))}<small>${e(typeName(p.type_train_id))}</small></span><span class="badge">осталось ${p.remaining}</span></a>`).join(''):empty('Все пакеты в порядке')}</section><section class="note"><h3>Правило отчёта</h3><p>Прибыль = сумма цен занятий минус аренда. Продажи пакетов сюда не складываются.</p></section></aside></div>`);
  wireBookingDetails();
}
function weekControls() {return `<div class="week-toolbar"><h2>${e(formatDate(state.week))} — ${e(formatDate(addDays(state.week,6)))}</h2><div class="actions"><button data-week="-7" class="secondary">← <span>неделя</span></button><button data-week="today" class="secondary">Эта неделя</button><button data-week="7" class="secondary"><span>неделя</span> →</button></div></div>`;}
function wireWeek(callback) {document.querySelectorAll('[data-week]').forEach(button=>button.onclick=()=>{state.week=button.dataset.week==='today'?weekStart(today()):addDays(state.week,Number(button.dataset.week));callback();});}
function renderSchedule() {
  page(header('Расписание недели','Все занятия и свободные дни',link('personal','+ Записать','primary'))+`<section class="panel">${weekControls()}<div class="schedule-grid">${weekDays(state.week).map(date=>{
    const items=state.bookings.filter(b=>b.date===date).sort((a,b)=>a.time.localeCompare(b.time));
    return `<section class="schedule-day ${date===today()?'is-today':''}"><h3>${e(formatDate(date,{weekday:'short',day:'numeric'}))}</h3>${items.length?items.map(b=>`<button class="schedule-event ${b.is_group?'group-event':''}" data-booking="${b.id}"><time>${e(b.time.slice(0,5))}</time><strong>${e(bookingTitle(b))}</strong><small>${e(typeName(b.type_train_id))}</small></button>`).join(''):'<small class="free-day">Свободно</small>'}</section>`;
  }).join('')}</div></section>`);
  wireWeek(renderSchedule);wireBookingDetails();
}
function renderClients() {
  page(header('Клиенты',`${state.clients.length} в базе · поиск по имени и телефону`,'<button class="primary" id="new-client">+ Новый клиент</button>')+`<div class="clients-grid"><section class="panel"><label class="search"><span class="sr-only">Поиск клиентов</span><input id="client-search" type="search" placeholder="Поиск по имени или телефону" value="${e(state.query)}"></label><div id="client-list"></div></section><section class="panel" id="new-client-panel"><h2>Новый клиент</h2><p class="muted">Добавьте контакт, чтобы записывать клиента на тренировки.</p><form id="client-form">${field('Имя','<input name="name" autocomplete="given-name" maxlength="100" required>')}${field('Фамилия','<input name="surname" autocomplete="family-name" maxlength="100">')}${field('Телефон','<input name="phone" type="tel" autocomplete="tel" placeholder="+7 921 000-00-00" required>')}<div class="error" id="client-error" role="alert" hidden></div><button class="primary" type="submit">Сохранить</button></form></section></div>`);
  renderClientList();
  document.querySelector('#client-search').oninput=event=>{state.query=event.target.value;renderClientList();};
  document.querySelector('#new-client').onclick=()=>{document.querySelector('#new-client-panel').scrollIntoView({behavior:'smooth'});document.querySelector('[name=name]').focus();};
  document.querySelector('#client-form').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');if(button.disabled)return;
    try {const data=Object.fromEntries(new FormData(form));data.phone=normalizePhone(data.phone);data.name=data.name.trim();data.surname=data.surname.trim();if(!data.name)throw new Error('Введите имя клиента.');button.disabled=true;
      const client=await api.request('/clients',{method:'POST',body:data});state.clients.push(client);notify('Клиент добавлен');renderClients();
    } catch(error) {errorBox(error,'#client-error');} finally {button.disabled=false;}
  };
}
function renderClientList() {
  const needle=state.query.trim().toLocaleLowerCase('ru'),digits=needle.replace(/\D/g,'');
  const clients=state.clients.filter(c=>`${clientName(c)} ${phoneLabel(c.phone)}`.toLocaleLowerCase('ru').includes(needle)||(digits.length>=3&&String(c.phone).includes(digits.replace(/^[78](?=\d{10}$)/,''))));
  document.querySelector('#client-list').innerHTML=clients.length?`<div class="table-wrap"><table><thead><tr><th>Клиент</th><th>Пакет</th><th>Последняя</th></tr></thead><tbody>${clients.map(c=>{
    const packages=activePackages(state.packages,c.id), last=state.bookings.filter(b=>(b.client===c.id||b.participants?.includes(c.id))&&b.date<=today()).sort((a,b)=>b.date.localeCompare(a.date))[0];
    return `<tr><td><button class="client-name" data-client="${c.id}"><span class="avatar">${e(clientName(c).split(' ').slice(0,2).map(n=>n[0]).join(''))}</span><span><strong>${e(clientName(c))}</strong><small>${e(phoneLabel(c.phone))}${c.inactive?' · неактивен':''}</small></span></button></td><td>${packages.length?packages.map(p=>`<span class="badge" title="${e(typeName(p.type_train_id))}">осталось ${p.remaining??'—'}/${p.count_train}</span>`).join(' '):'<span class="muted">нет пакета</span>'}</td><td>${last?e(formatDate(last.date,{day:'numeric',month:'short'})):'—'}</td></tr>`;
  }).join('')}</tbody></table></div>`:empty('Клиенты не найдены');
  document.querySelectorAll('[data-client]').forEach(button=>button.onclick=()=>{
    const id=Number(button.dataset.client),c=person(id),bookings=state.bookings.filter(b=>b.client===id||b.participants?.includes(id)).sort((a,b)=>b.date.localeCompare(a.date));
    showDialog(e(clientName(c)),`<p>${e(phoneLabel(c.phone))}</p><h3>Последние записи</h3>${bookings.slice(0,5).map(b=>`<div class="summary-row"><span>${e(formatDate(b.date))} · ${e(b.time.slice(0,5))}</span><span>${e(typeName(b.type_train_id))}</span></div>`).join('')||empty('Записей пока нет')}<div class="actions">${link(`personal?client=${id}`,'Записать','primary')}${link(`prepaid?client=${id}`,'Добавить пакет')}</div>`);
    dialog.querySelectorAll('a').forEach(a=>a.onclick=()=>dialog.close());
  });
}
function createDraft() {
  const client=new URLSearchParams(location.hash.split('?')[1]||'').get('client')||'';
  return {client:person(client)?client:'',clients:[],type:'',date:today(),time:'',price:'',summ:'',count:'',available:[],slotsLoaded:false};
}
function clientLabel(client) {return `${clientName(client)} · ${phoneLabel(client.phone)}`;}
function clientMatches(client, query) {
  const normalized=query.trim().toLocaleLowerCase('ru'),digits=normalized.replace(/\D/g,'');
  if(!normalized)return true;
  return clientLabel(client).toLocaleLowerCase('ru').includes(normalized)||(digits.length>=3&&String(client.phone).includes(digits.replace(/^[78](?=\d{10}$)/,'')));
}
function clientPicker(selected, id='client-picker') {
  const chosen=person(selected);
  return `<div class="client-picker" id="${id}"><span class="sr-only">Поиск клиента</span><input id="${id}-search" type="search" autocomplete="off" placeholder="Начните вводить имя или телефон" value="${chosen?e(clientLabel(chosen)):''}" aria-label="Поиск клиента" aria-controls="${id}-options" aria-expanded="false"><input type="hidden" name="client" value="${chosen?.id||''}"><div class="client-options" id="${id}-options" role="listbox" hidden>${state.clients.map(client=>`<button type="button" role="option" data-client-option="${client.id}"><strong>${e(clientName(client))}</strong><small>${e(phoneLabel(client.phone))}</small></button>`).join('')||empty('Сначала добавьте клиентов')}</div></div>`;
}
function wireClientPicker(id, onChange) {
  const picker=document.querySelector(`#${id}`),search=picker.querySelector('input[type=search]'),value=picker.querySelector('[name=client]'),options=picker.querySelector('[role=listbox]');
  const filter=query=>{
    let visible=0;
    options.querySelectorAll('[data-client-option]').forEach(option=>{
      const client=person(option.dataset.clientOption),matches=Boolean(client&&clientMatches(client,query));
      option.hidden=!matches;if(matches)visible++;
    });
    options.hidden=visible===0;
    search.setAttribute('aria-expanded',String(visible>0));
    return visible;
  };
  const choose=option=>{
    const client=person(option.dataset.clientOption);if(!client)return;
    value.value=String(client.id);search.value=clientLabel(client);options.hidden=true;
    search.setAttribute('aria-expanded','false');onChange(value.value);
  };
  search.addEventListener('focus',()=>filter(search.value));
  search.addEventListener('input',()=>{
    if(value.value){value.value='';onChange('');}
    filter(search.value);
  });
  search.addEventListener('keydown',event=>{
    if(event.key==='Escape'){options.hidden=true;search.setAttribute('aria-expanded','false');return;}
    if(event.key!=='Enter')return;
    const option=[...options.querySelectorAll('[data-client-option]')].find(item=>!item.hidden);
    if(!option)return;
    event.preventDefault();choose(option);
  });
  options.querySelectorAll('[data-client-option]').forEach(option=>option.addEventListener('mousedown',event=>{
    event.preventDefault();choose(option);
  }));
}
function typeSelect(selected,group=false) {return `<select name="type" required><option value="">Выберите тип</option>${state.types.filter(t=>t.group_train===group).map(t=>`<option value="${t.id}" ${Number(selected)===t.id?'selected':''}>${e(t.type_train)}${t.location==='home'?' · Дом':t.location==='ter_fit'?' · Студия':''}</option>`).join('')}</select>`;}
function renderBooking() {
  const group=state.page==='group';state.draft??=createDraft();const d=state.draft;
  page(header(group?'Групповая запись':'Персональная запись',group?'Выберите участников, свободное время и общую цену занятия.':'Клиент → тип → дата → свободное время → подтверждение')+`<form id="booking-form"><div class="booking-grid"><section class="panel"><h2>${group?'Участники':'Параметры'}</h2>${group?`<label class="search"><span class="sr-only">Поиск участников</span><input type="search" id="participant-search" placeholder="Найти клиента"></label><div class="participant-list">${state.clients.map(c=>`<label class="participant" data-search="${e(`${clientName(c)} ${c.phone}`.toLowerCase())}"><input type="checkbox" name="participants" value="${c.id}" ${d.clients.includes(c.id)?'checked':''}><span>${e(clientName(c))}</span></label>`).join('')||empty('Сначала добавьте клиентов')}<p id="selected-count" class="muted">Выбрано: ${d.clients.length}</p></div>`:field('Клиент',clientPicker(d.client,'booking-client-picker'))}${field('Тип тренировки',typeSelect(d.type,group))}<div id="price-field"></div><div class="error" id="booking-error" role="alert" hidden></div><div class="actions">${link('overview','Отмена')}<button type="submit" class="primary">${group?'Создать группу':'Записать'}</button></div></section><section class="panel slot-panel">${weekControls()}<div class="days">${weekDays(state.week).map(date=>`<button type="button" class="day ${d.date===date?'selected':''}" data-date="${date}"><span>${e(formatDate(date,{weekday:'short'}))}</span><strong>${e(formatDate(date,{day:'numeric'}))}</strong></button>`).join('')}</div>${field('Дата занятия',`<input type="date" name="date" value="${d.date}" required>`)}<h3>Свободное время · ${e(formatDate(d.date))}</h3><div id="slots" role="group" aria-label="Время занятия"></div><p class="muted">Серым отмечено занятое время. Время занятий — московское.</p></section></div></form>`);
  const form=document.querySelector('#booking-form');
  form.querySelectorAll('[data-week]').forEach(b=>b.type='button');
  form.querySelector('[name=type]').onchange=event=>{d.type=event.target.value;d.price='';renderPrice();};
  if(!group)wireClientPicker('booking-client-picker',client=>{d.client=client;d.price='';renderPrice();});
  else {
    document.querySelector('#participant-search').oninput=event=>{const q=event.target.value.toLowerCase();document.querySelectorAll('.participant').forEach(row=>row.hidden=!row.dataset.search.includes(q));};
    form.querySelectorAll('[name=participants]').forEach(input=>input.onchange=()=>{d.clients=[...form.querySelectorAll('[name=participants]:checked')].map(i=>Number(i.value));document.querySelector('#selected-count').textContent=`Выбрано: ${d.clients.length}`;renderPrice();});
  }
  const changeDate=date=>{if(!date)return;d.date=date;d.time='';d.slotsLoaded=false;state.week=weekStart(date);renderBooking();};
  form.querySelector('[name=date]').onchange=event=>changeDate(event.target.value);
  form.querySelectorAll('[data-date]').forEach(button=>button.onclick=()=>changeDate(button.dataset.date));
  wireWeek(renderBooking);renderPrice();renderSlots();fetchSlots();
  form.onsubmit=async event=>{
    event.preventDefault();
    const submit=form.querySelector('[type=submit]');
    if(submit.disabled)return;
    submit.disabled=true;
    try {
    if(!group && d.client) {
      const fresh=await api.all('/prepaid',{client_id:d.client,active:true});
      if(state.draft!==d)return;
      state.packages=[...state.packages.filter(p=>p.client_id!==Number(d.client)||p.is_complete),...fresh];
      renderPrice();
    }
    const hint=group?{}:priceHint(state.packages,state.bookings,d.client,d.type);
    const payload=bookingPayload(d,group,hint);
    if(!d.slotsLoaded||!d.available.includes(d.time))throw new Error('Выберите свободный слот после загрузки времени.');
    showDialog('Подтвердить запись?',`<p>Проверьте детали перед сохранением.</p><dl><dt>${group?'Участники':'Клиент'}</dt><dd>${e(group?d.clients.map(name).join(', '):name(d.client))}</dd><dt>Тип</dt><dd>${e(typeName(d.type))}</dd><dt>Когда</dt><dd>${e(formatDate(d.date))} · ${e(d.time)}</dd><dt>Оплата</dt><dd>${e(money(hint.package?hint.price:payload.price))}${hint.package?' · по пакету':''}</dd></dl>${hint.package?`<p class="note">После записи останется занятий: ${Math.max(0,(hint.package.remaining??hint.package.count_train)-1)}.</p>`:''}`,async()=>{
      await api.request(`/bookings/${group?'group':'personal'}`,{method:'POST',body:payload});
      notify('Тренировка добавлена');state.draft=null;location.hash='schedule';await load();
    },async error=>{if(error.status===409){dialog.close();errorBox(error,'#booking-error');d.time='';d.slotsLoaded=false;await fetchSlots();}});
  }catch(error){errorBox(error,'#booking-error');}
    finally {submit.disabled=Boolean(!group&&priceHint(state.packages,state.bookings,d.client,d.type).blocked);}
  };
}
function renderPrice() {
  const d=state.draft,group=state.page==='group',hint=group?{}:priceHint(state.packages,state.bookings,d.client,d.type);
  if(d.price===''&&hint.price!=null&&!hint.package)d.price=String(hint.price);
  document.querySelector('#price-field').innerHTML=hint.blocked?`<p class="error">${e(hint.message)}</p>`:hint.package?`<div class="note"><strong>${e(money(hint.price))} · с пакета</strong><p>Осталось ${hint.package.remaining??'—'} из ${hint.package.count_train} занятий</p></div>`:field(group?'Цена всего занятия, ₽':'Цена, ₽',`<input name="price" type="number" inputmode="numeric" min="0" step="1" value="${e(d.price)}" required>${hint.price!=null?'<small>Подставлена цена последнего занятия</small>':''}`)+(group?`<p id="group-price-note" class="muted">${d.clients.length?`${e(money(Number(d.price||0)/d.clients.length))} с человека · `:''}Группа не списывается с пакета.</p>`:'');
  const input=document.querySelector('[name=price]');if(input)input.oninput=event=>{d.price=event.target.value;const note=document.querySelector('#group-price-note');if(note)note.textContent=`${d.clients.length?money(Number(d.price||0)/d.clients.length)+' с человека · ':''}Группа не списывается с пакета.`;};
  document.querySelector('#booking-form [type=submit]').disabled=Boolean(hint.blocked);
}
function renderSlots() {
  const box=document.querySelector('#slots');if(!box||!state.draft)return;const d=state.draft;
  box.innerHTML=!d.slotsLoaded?'<p role="status">Загрузка свободного времени…</p>':`<div class="slots">${slots.map(time=>`<button type="button" class="time-chip ${d.time===time?'selected':''}" data-time="${time}" ${!d.available.includes(time)?'disabled':''} aria-pressed="${d.time===time}">${time}</button>`).join('')}</div>${d.available.length?'':empty('На эту дату свободных слотов нет')}`;
  box.querySelectorAll('[data-time]').forEach(button=>button.onclick=()=>{d.time=button.dataset.time;renderSlots();});
}
async function fetchSlots() {
  const d=state.draft;if(!d)return;const run=++slotGeneration,date=d.date;
  try {const result=await api.request(`/slots?date=${date}`);if(run!==slotGeneration||state.draft!==d||date!==d.date)return;d.available=result.slots;d.slotsLoaded=true;if(!d.available.includes(d.time))d.time='';renderSlots();}
  catch(error){if(run!==slotGeneration||state.draft!==d)return;const box=document.querySelector('#slots');if(box){box.innerHTML=`<p class="error">${e(error.message)}</p><button type="button" id="retry-slots">Повторить</button>`;document.querySelector('#retry-slots').onclick=fetchSlots;}}
}
function renderPrepaid() {
  state.draft??=createDraft();const d=state.draft;
  page(header('Предоплата','Пакеты персональных тренировок и остаток занятий')+`<div class="prepaid-grid"><section class="panel"><h2>Добавить пакет</h2><form id="prepaid-form">${field('Клиент',clientPicker(d.client,'prepaid-client-picker'))}${field('Тип тренировки',typeSelect(d.type))}<div class="two-fields">${field('Сумма, ₽',`<input name="summ" type="number" inputmode="numeric" min="1" step="1" value="${e(d.summ)}" required>`)}${field('Занятий',`<input name="count" type="number" inputmode="numeric" min="1" step="1" value="${e(d.count)}" required>`)}</div><div class="error" id="prepaid-error" role="alert" hidden></div><button class="primary" type="submit">Оформить пакет</button></form></section><section class="note payment-summary" id="payment-summary"></section></div><section class="panel packages-panel"><div class="section-header"><h2>Пакеты клиентов</h2><label><span class="sr-only">Статус пакетов</span><select id="package-filter"><option value="active">Активные</option><option value="complete">Завершённые</option><option value="all">Все</option></select></label></div><div id="packages-list"></div></section>`);
  const form=document.querySelector('#prepaid-form');
  wireClientPicker('prepaid-client-picker',client=>{d.client=client;renderPaymentSummary();});
  form.querySelectorAll('input,select').forEach(input=>{
    if(!input.name)return;
    input.oninput=()=>{d[input.name]=input.value;renderPaymentSummary();};
  });
  renderPaymentSummary();renderPackages();document.querySelector('#package-filter').value=state.packageFilter;
  document.querySelector('#package-filter').onchange=event=>{state.packageFilter=event.target.value;renderPackages();};
  form.onsubmit=event=>{event.preventDefault();try{
    const payload={client_id:integer(d.client,'Клиент',1),type_train_id:integer(d.type,'Тип',1),summ:integer(d.summ,'Сумма',1),count:integer(d.count,'Занятий',1)};
    if(activePackages(state.packages,d.client,d.type).length)throw new Error('У клиента уже есть открытый пакет этого типа.');
    showDialog('Оформить пакет?',`<dl><dt>Клиент</dt><dd>${e(name(d.client))}</dd><dt>Тип</dt><dd>${e(typeName(d.type))}</dd><dt>Сумма</dt><dd>${e(money(payload.summ))}</dd><dt>Занятий</dt><dd>${payload.count}</dd></dl>`,async()=>{await api.request('/prepaid',{method:'POST',body:payload});notify('Пакет добавлен');state.draft=null;await load();});
  }catch(error){errorBox(error,'#prepaid-error');}};
}
function renderPaymentSummary() {
  const d=state.draft;document.querySelector('#payment-summary').innerHTML=`<h3>К оплате</h3><strong class="payment-total">${e(money(Number(d.summ||0)))}</strong><p>${Number(d.count)>0?`${e(money(Number(d.summ||0)/Number(d.count)))} за тренировку`:'Укажите сумму и количество занятий'}</p><dl><dt>Клиент</dt><dd>${d.client?e(name(d.client)):'—'}</dd><dt>Тип</dt><dd>${d.type?e(typeName(d.type)):'—'}</dd><dt>Списание</dt><dd>при персональной записи</dd></dl>${activePackages(state.packages,d.client,d.type).length?'<p class="error">У клиента уже есть открытый пакет этого типа.</p>':''}`;
}
function renderPackages() {
  const packages=state.packages.filter(p=>state.packageFilter==='all'||(state.packageFilter==='active'?!p.is_complete:p.is_complete));
  document.querySelector('#packages-list').innerHTML=packages.length?`<div class="table-wrap"><table><thead><tr><th>Клиент</th><th>Тип</th><th>Сумма</th><th>Остаток</th><th>Статус</th></tr></thead><tbody>${packages.map(p=>`<tr><td>${e(name(p.client_id))}</td><td>${e(typeName(p.type_train_id))}</td><td>${e(money(p.summ))}</td><td>${p.remaining??'—'} / ${p.count_train}</td><td><span class="badge">${p.is_complete?'Завершён':'Активен'}</span></td></tr>`).join('')}</tbody></table></div>`:empty('Пакетов с таким статусом пока нет');
}
function renderReports() {
  const years=[...new Set([today().slice(0,4),...state.reports.filter(r=>r.month).map(r=>r.month.slice(0,4))])].sort().reverse();
  const reports=state.reports.filter(r=>r.month?.startsWith(state.year)).sort((a,b)=>b.month.localeCompare(a.month));
  const selected=state.reports.find(r=>r.month?.startsWith(state.month));
  const bookings=state.bookings.filter(b=>b.date.startsWith(state.month)),groups=bookings.filter(b=>b.is_group).length;
  page(header('Отчёт по тренировкам','Прибыль = стоимость занятий − аренда',`<label><span class="sr-only">Год отчёта</span><select id="report-year">${years.map(y=>`<option ${y===state.year?'selected':''}>${y}</option>`).join('')}</select></label><button class="secondary" id="export">Скачать CSV</button>`)+`<div class="report-month">${field('Месяц',`<input id="report-month" type="month" value="${state.month}">`)}</div>`+metrics(selected,bookings.length,`перс. ${bookings.length-groups} · групп ${groups}`)+`<section class="panel"><div class="table-wrap"><table><thead><tr><th>Месяц</th><th>Выручка</th><th>Аренда</th><th>Прибыль</th><th>Занятий</th></tr></thead><tbody>${reports.map(r=>`<tr class="${r.month.startsWith(state.month)?'selected-row':''}"><td><button class="text-button" data-month="${r.month.slice(0,7)}">${e(formatDate(r.month,{month:'long',year:'numeric'}))}</button></td><td>${e(money(r.total_sum))}</td><td>${e(money(r.sum_rent))}</td><td><strong>${e(money(r.income))}</strong></td><td>${state.bookings.filter(b=>b.date.startsWith(r.month.slice(0,7))).length}</td></tr>`).join('')}</tbody></table>${reports.length?'':empty('За этот год занятий пока нет')}</div></section><p class="muted report-note">Поступления от продажи пакетов не прибавляются к выручке повторно.</p>`);
  document.querySelector('#report-year').onchange=event=>{state.year=event.target.value;state.month=state.reports.filter(r=>r.month?.startsWith(state.year)).sort((a,b)=>b.month.localeCompare(a.month))[0]?.month.slice(0,7)||`${state.year}-01`;renderReports();};
  document.querySelector('#report-month').onchange=event=>{if(event.target.value){state.month=event.target.value;state.year=state.month.slice(0,4);renderReports();}};
  document.querySelectorAll('[data-month]').forEach(button=>button.onclick=()=>{state.month=button.dataset.month;renderReports();});
  document.querySelector('#export').onclick=()=>{const rows=[['Месяц','Выручка','Аренда','Прибыль','Занятий'],...reports.map(r=>[r.month,r.total_sum,r.sum_rent,r.income,state.bookings.filter(b=>b.date.startsWith(r.month.slice(0,7))).length])];const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row=>row.join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`katefit-${state.year}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
}
function showDialog(title,body,onConfirm,onError) {
  if(dialog.open)dialog.close();
  dialog.classList.remove('calendar-dialog');
  const content=`${body}<div id="dialog-error" class="error" role="alert" hidden></div>`;
  dialog.innerHTML=`<h2 id="dialog-title">${title}</h2>${isStudio()?`<div class="studio-dialog-body">${content}</div>`:content}<div class="dialog-actions"><button id="dialog-cancel" class="secondary">${onConfirm?'Отменить':'Закрыть'}</button>${onConfirm?'<button id="dialog-submit" class="primary">Добавить</button>':''}</div>`;
  dialog.querySelector('#dialog-cancel').onclick=()=>dialog.close();
  dialog.oncancel=event=>{if(saving)event.preventDefault();};
  if(onConfirm)dialog.querySelector('#dialog-submit').onclick=async()=>{
    if(saving)return;saving=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{await onConfirm();dialog.close();}
    catch(error){errorBox(error,'#dialog-error');if(onError)await onError(error);}
    finally{saving=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}
  };
  dialog.showModal();
}
root.addEventListener('click',event=>{
  if((saving||studio.saving)&&event.target.closest('a,#logout')){
    event.preventDefault();event.stopPropagation();notify('Дождитесь результата сохранения.');
  }
},true);
window.addEventListener('hashchange',()=>{if(dialog.open&&!saving)dialog.close();render();});
window.addEventListener('keydown',event=>{if(event.key==='Escape'){root.querySelector('.app-shell')?.classList.remove('menu-open');document.querySelector('#menu-toggle')?.setAttribute('aria-expanded','false');}});
if(api.token)load();else renderLogin();
