import {bindPhoneInput} from './phone-input.js';
import {escapeHtml as e, money, normalizePhone} from './domain.js';
import {StudioCalendar} from './studio-calendar.js';
import {setStudioSelectClients} from './studio-select.js';
import {studioPersonName, relationId, currencyAmount, eligibleProducts, personPackages, createOperationId, attendancePayload, PendingStudioOperation, calendarDate, paymentStartOfMoscowDay} from './studio-domain.js';

let fieldSequence = 0;
const field = (label, input) => {
  const labelId = 'studio-label-' + (++fieldSequence);
  return `<label class="field"><span id="${labelId}">${e(label)}</span>${input.replace(/<(input|select)/, `<$1 aria-labelledby="${labelId}"`)}</label>`;
};
const empty = text => `<div class="empty">${e(text)}</div>`;
const statuses = {ACTIVE:'Активен',EXHAUSTED:'Использован',EXPIRED:'Истёк',FROZEN:'Заморожен',PENDING_PAYMENT:'Ожидает оплаты',REFUNDED:'Возвращён',CANCELLED:'Отменён',ATTENDED:'Посетил',BOOKED:'Записан',CANCELLED_BY_STUDIO:'Отменено студией',GRANT:'Начисление',CONSUME:'Списание',RESERVE:'Резерв',RELEASE:'Возврат резерва'};
const status = value => statuses[value] || value || '—';
const date = value => value ? new Date(value).toLocaleString('ru-RU') : '—';
const visitMoment = value => {
  const moment = new Date(value);
  if (!value || !Number.isFinite(moment.getTime())) return {day:'—',time:'—'};
  return {
    day:new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Moscow'}).format(moment),
    time:new Intl.DateTimeFormat('ru-RU',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Europe/Moscow'}).format(moment),
  };
};
const options = (items, label) => '<option value="">Выберите…</option>' + items.map(item => `<option value="${e(item.id)}">${e(label(item))}</option>`).join('');
const table = (columns, rows) => rows.length ? `<p class="studio-table-hint">Проведите по таблице, чтобы увидеть остальные поля →</p><div class="table-wrap"><table><thead><tr>${columns.map(column=>`<th>${column}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>` : empty('Пока нет записей');

export class StudioUi {
  constructor({api, page, header, notify, errorBox, showDialog}) {
    Object.assign(this,{api,page,header,notify,errorBox,showDialog});
    this.pending = new PendingStudioOperation();
    this.calendar = new StudioCalendar(this);
    this.data = null; this.generation = 0; this.saving = false;
  }
  reset() { this.generation++; this.data=null; setStudioSelectClients([]); }
  deactivate() { this.generation++; }
  clientName(id) { return studioPersonName(this.data.clients.find(person=>person.id===id)); }
  product(id) { return this.data.products.find(product=>product.id===id); }
  membership(id) { return this.data.packages.find(membership=>membership.id===id); }
  async render(route, force = false) {
    const run = ++this.generation;
    this.route = route;
    this.page(this.header('Студия Gelios','Данные и списания из Twenty CRM') + '<p role="status">Загружаем данные студии…</p>');
    try {
      if (!this.data || force) {
        const configuration = await this.api.request('/studio/auth/status');
        if (!configuration.configured) throw new Error('CRM пока не подключена. На сервере нужны CRM_ENABLED, CRM_BASE_URL и CRM_API_KEY. Terfit продолжает работать.');
        const resources = ['clients','products','packages','bookings','sessions','transactions','events'];
        const lists = await Promise.all(resources.map(resource=>this.api.studioRecords(resource)));
        if (run !== this.generation) return;
        this.data = Object.fromEntries(resources.map((resource,index)=>[resource,lists[index]]));
      }
      if (run !== this.generation) return;
      setStudioSelectClients(this.data.clients);
      ({overview:()=>this.overview(),clients:()=>this.clients(),packages:()=>this.packages(),attendance:()=>this.attendance(),bookings:()=>this.bookings(),transactions:()=>this.transactions(),calendar:()=>this.calendar.render()})[route]();
      document.querySelector('.refresh').onclick=()=>this.render(this.route,true);
    } catch(error) {
      if(run!==this.generation)return;
      this.page(this.header('Студия Gelios','Не удалось загрузить данные')+`<section class="panel"><p class="error" role="alert">${e(error.message)}</p><button id="studio-retry" class="primary">Повторить загрузку</button> <a class="button secondary" href="#overview">Вернуться в Terfit</a></section>`);
      document.querySelector('#studio-retry').onclick=()=>this.render(route,true);
      document.querySelector('.refresh').onclick=()=>this.render(route,true);
    }
  }
  overview() {
    const active=this.data.packages.filter(membership=>membership.status==='ACTIVE');
    this.page(this.header('Обзор Gelios','Клиенты, оплаченные пакеты и подтверждённые посещения','<a class="button primary" href="#gelios/attendance">+ Внести тренировку</a>')+
      `<div class="metrics">${[['Клиентов',this.data.clients.length,'в CRM'],['Активных пакетов',active.length,'оплаченные пакеты'],['Посещений',this.data.bookings.filter(booking=>booking.status==='ATTENDED').length,'подтверждено'],['Списаний',this.data.transactions.filter(transaction=>transaction.transactionType==='CONSUME').length,'в журнале CRM']].map(([label,value,note])=>`<section class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></section>`).join('')}</div>
      <div class="overview-grid"><section class="panel"><h2>Последние посещения</h2>${this.bookingTable(this.data.bookings.filter(booking=>booking.status==='ATTENDED').sort((a,b)=>String(b.recordedAt||b.bookedAt).localeCompare(String(a.recordedAt||a.bookedAt))).slice(0,8))}</section>
      <aside class="stack"><section class="panel"><h2>Пакеты на исходе</h2>${active.filter(membership=>membership.visitsAvailable<=2).map(membership=>`<a class="package-alert" href="#gelios/packages"><span>${e(this.clientName(relationId(membership,'person')))}<small>${e(membership.name)}</small></span><span class="badge">${e(membership.visitsAvailable)} осталось</span></a>`).join('')||empty('Все пакеты в порядке')}</section><section class="note"><h3>Источник данных — CRM</h3><p>Остатки и списания вычисляет Twenty. Участники будущих тренировок — в календаре. Сплиты и проведение обычных бронирований пока выполняются в CRM.</p></section></aside></div>`);
  }
  clients() {
    this.page(this.header('Клиенты Gelios','Контакты студии · отдельная база CRM')+`<div class="clients-grid"><section class="panel"><label class="search"><span class="sr-only">Поиск клиентов Gelios</span><input id="studio-search" type="search" placeholder="Имя, телефон или email"></label><div id="studio-client-list"></div></section>
      <section class="panel"><h2>Новый клиент</h2><form id="studio-client-form">
      ${field('Имя','<input name="firstName" maxlength="100" required autocomplete="given-name">')}
      ${field('Фамилия','<input name="lastName" maxlength="100" autocomplete="family-name">')}
      ${field('Телефон','<input name="phone" type="tel" required value="+7" placeholder="+7 (921) 000-00-00" inputmode="tel" autocomplete="tel">')}
      ${field('Email','<input name="email" type="email" maxlength="254" autocomplete="email">')}
      <div id="studio-form-error" class="error" role="alert" hidden></div><button class="primary" type="submit">Добавить клиента</button></form></section></div>`);
    const draw=query=>{
      const clients=this.data.clients.filter(person=>[studioPersonName(person),person.phones?.primaryPhoneNumber,person.emails?.primaryEmail].join(' ').toLocaleLowerCase('ru').includes(query.toLocaleLowerCase('ru')));
      document.querySelector('#studio-client-list').innerHTML=table(['Клиент','Телефон','Email'],clients.map(person=>`<tr class="studio-client-row" data-studio-person="${e(person.id)}" tabindex="0" role="button" aria-label="Открыть карточку клиента ${e(studioPersonName(person))}"><td><strong>${e(studioPersonName(person))}</strong></td><td>${e(person.phones?.primaryPhoneCallingCode||'')} ${e(person.phones?.primaryPhoneNumber||'—')}</td><td>${e(person.emails?.primaryEmail||'—')}</td></tr>`));
      document.querySelectorAll('[data-studio-person]').forEach(row=>{
        const open=()=>this.clientDetails(row.dataset.studioPerson);
        row.onclick=open;
        row.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open();}};
      });
    };
    draw('');document.querySelector('#studio-search').oninput=event=>draw(event.target.value.trim());
    const form=document.querySelector('#studio-client-form');
    bindPhoneInput(form.elements.phone);
    this.restore('client',form,'/studio/clients');
    form.onsubmit=event=>{
      event.preventDefault();
      try {
        const body={...Object.fromEntries(new FormData(form)),clientId:createOperationId()};
        body.phone=normalizePhone(body.phone);
        this.submit('client',body,'/studio/clients');
      } catch(error) { this.errorBox(error,'#studio-form-error'); }
    };
  }
  clientDetails(id) {
    const person=this.data.clients.find(client=>client.id===id);
    const packages=personPackages(this.data.packages,id);
    this.showDialog(e(studioPersonName(person)),`<dl class="client-details"><dt>Телефон</dt><dd>${e(person.phones?.primaryPhoneNumber||'—')}</dd><dt>Email</dt><dd>${e(person.emails?.primaryEmail||'—')}</dd></dl><h3>Пакеты клиента</h3>${this.clientPackageCards(packages)}<div class="actions client-card-actions"><a class="button primary" href="#gelios/attendance?client=${encodeURIComponent(id)}">Внести тренировку</a><a class="button secondary" href="#gelios/packages?client=${encodeURIComponent(id)}">Оформить пакет</a></div>`);
    document.querySelectorAll('#confirm a').forEach(link=>link.onclick=()=>document.querySelector('#confirm').close());
  }
  clientPackageCards(packages) {
    if (!packages.length) return empty('У клиента пока нет пакетов.');
    return `<div class="client-package-table" role="table"><div class="client-package-table-head" role="row"><span>Пакет</span><span>Доступно</span><span>Резерв</span><span>Использовано</span></div>${packages.map(membership=>{
      const visits=this.packageVisitsFor(membership.id);
      return `<details class="client-package-row"><summary><span class="client-package-name" data-visits="${e(membership.visitsAvailable)} / ${e(membership.visitsGranted)}"><strong>${e(membership.name)}</strong><small>${e(status(membership.status))} · до ${e(membership.expiresOn||'без срока')}</small></span><span>${e(membership.visitsAvailable)} / ${e(membership.visitsGranted)}</span><span>${e(membership.visitsReserved)}</span><span>${e(membership.visitsConsumed)}</span><span class="client-package-expand">Развернуть</span></summary><div class="client-package-visits-panel">${visits.length?`<h4>Проведённые посещения</h4><div class="package-visits">${visits.map(({booking,session})=>{
        const moment=visitMoment(session?.startsAt||booking.recordedAt);
        return `<div class="package-visit"><time datetime="${e(session?.startsAt||booking.recordedAt||'')}">${e(moment.day)}</time><strong>${e(moment.time)}</strong><span>${e(session?.name||'Тренировка')}</span></div>`;
      }).join('')}</div>`:empty('В рамках этого пакета ещё нет проведённых посещений.')}</div></details>`;
    }).join('')}</div>`;
  }
  packageVisitsFor(membershipId) {
    return this.data.bookings
      .filter(booking=>relationId(booking,'membership')===membershipId&&booking.status==='ATTENDED')
      .map(booking=>({booking,session:this.data.sessions.find(session=>session.id===relationId(booking,'classSession'))}))
      .sort((left,right)=>String(right.session?.startsAt||right.booking.recordedAt).localeCompare(String(left.session?.startsAt||left.booking.recordedAt)));
  }
  packageTable(packages) {
    return table(['Клиент / пакет','Доступно','Резерв','Использовано','До','Статус'],packages.map(membership=>`<tr><td>${e(this.clientName(relationId(membership,'person')))}<small class="studio-subline">${e(membership.name)}</small></td><td>${e(membership.visitsAvailable)} / ${e(membership.visitsGranted)}</td><td>${e(membership.visitsReserved)}</td><td>${e(membership.visitsConsumed)}</td><td>${e(membership.expiresOn||'—')}</td><td><span class="badge">${e(status(membership.status))}</span></td></tr>`));
  }
  packages() {
    this.page(this.header('Пакеты и оплата','Оформление полученной оплаты и пакетов клиентов')+`<div class="studio-payment-layout"><section class="panel"><h2>Оформить оплаченный пакет</h2><form id="studio-payment-form">
      ${field('Клиент',`<select name="personId" required>${options(this.data.clients,studioPersonName)}</select>`)}
      ${field('Продукт',`<select name="productId" required>${options(eligibleProducts(this.data.products),product=>product.name+' · '+money(currencyAmount(product.price)))}</select>`)}
      <div class="two-fields">
      ${field('Когда оплачено','<input name="paidAt" type="datetime-local" required>')}
      ${field('Способ оплаты','<select name="paymentMethod"><option value="CASH">Наличные</option><option value="SBP">СБП</option><option value="CARD">Карта</option></select>')}
      </div>
      ${field('Номер чека (необязательно)','<input name="fiscalReceiptId" maxlength="200">')}
      <div id="studio-form-error" class="error" role="alert" hidden></div><button class="primary" type="submit">Подтвердить оплату и создать пакет</button></form></section>
      <aside class="studio-payment-summary" aria-label="Итог оформления"><h2>Итог оформления</h2><div id="studio-product-details" aria-live="polite"></div><div class="studio-summary-footer"><h3>Что произойдёт после оплаты</h3><p>В CRM появятся оплата и пакет, начислятся посещения. Операция будет записана в журнал событий.</p><small>Подтверждайте только уже полученную оплату.</small></div></aside></div>
      <section class="panel packages-panel studio-package-list"><div class="section-header"><h2>Пакеты клиентов</h2><select id="studio-package-filter" aria-label="Статус пакета"><option value="all">Все</option><option value="ACTIVE">Активные</option><option value="EXHAUSTED">Использованные</option></select></div><div id="studio-packages"></div></section>`);
    const form=document.querySelector('#studio-payment-form');
    form.personId.value=new URLSearchParams(location.hash.split('?')[1]||'').get('client')||'';
    form.paidAt.value=calendarDate(new Date())+'T00:00';
    form.paidAt.onchange=()=>{
      const day=form.paidAt.value.slice(0,10);
      if(day)form.paidAt.value=day+'T00:00';
    };
    const updateSummary=()=>{
      const product=this.product(form.productId.value);
      const method={CASH:'Наличные',SBP:'СБП',CARD:'Карта'}[form.paymentMethod.value];
      document.querySelector('#studio-product-details').innerHTML=product?`<h3 class="studio-summary-product">${e(product.name)}</h3><strong class="studio-summary-price">${e(money(currencyAmount(product.price)))}</strong><span class="studio-summary-method">${e(method)}</span><p class="studio-summary-visits">+${e(product.visitsIncluded)} посещений после оплаты</p><dl><dt>Клиент</dt><dd>${form.personId.value?e(this.clientName(form.personId.value)):'Не выбран'}</dd><dt>Срок пакета</dt><dd>${product.validityDays?e(product.validityDays)+' дней':'Без ограничения'}</dd></dl>`:'<p class="studio-summary-placeholder">Выберите клиента и продукт. Здесь появятся стоимость, посещения и срок пакета.</p>';
    };
    form.productId.onchange=updateSummary;form.personId.onchange=updateSummary;form.paymentMethod.onchange=updateSummary;updateSummary();
    const draw=()=>{const filter=document.querySelector('#studio-package-filter').value;document.querySelector('#studio-packages').innerHTML=this.packageTable(this.data.packages.filter(membership=>filter==='all'||membership.status===filter));};
    draw();document.querySelector('#studio-package-filter').onchange=draw;
    this.restore('payment',form,'/studio/package-payments/confirm');
    form.onsubmit=event=>{
      event.preventDefault();
      try {
      const values=Object.fromEntries(new FormData(form)),product=this.product(values.productId);
      if(!product)throw new Error('Выберите доступный продукт.');
      const paidAt=paymentStartOfMoscowDay(values.paidAt);
      if(!Number.isFinite(paidAt.getTime()))throw new Error('Укажите корректную дату оплаты.');
      if(paidAt>new Date())return this.errorBox(new Error('Оплата не может быть в будущем.'),'#studio-form-error');
      const body={personId:values.personId,productId:product.id,paidAt:paidAt.toISOString(),paymentMethod:values.paymentMethod,amount:currencyAmount(product.price),idempotencyKey:createOperationId(),...(values.fiscalReceiptId.trim()?{fiscalReceiptId:values.fiscalReceiptId.trim()}:{})};
      this.showDialog('Подтвердить оплату',`<p>${e(this.clientName(body.personId))}</p><p>${e(product.name)} · ${e(money(body.amount))} · ${product.visitsIncluded} посещений</p><p>Подтверждайте только уже полученную оплату.</p>`,()=>this.submit('payment',body,'/studio/package-payments/confirm',true));
      } catch(error) { this.errorBox(error,'#studio-form-error'); }
    };
  }
  attendance() {
    this.page(this.header('Внести прошедшую тренировку','Предпросмотр проверяет баланс и дату на стороне CRM')+`<div class="booking-grid"><section class="panel"><form id="studio-attendance-form">
      ${field('Клиент',`<select name="personId" required>${options(this.data.clients,studioPersonName)}</select>`)}
      ${field('Пакет','<select name="membershipId" required><option value="">Сначала выберите клиента</option></select>')}
      ${field('Начало занятия','<input name="startsAt" type="datetime-local" required>')}
      ${field('Завершённое занятие CRM (необязательно)','<select name="existingClassSessionId"><option value="">Создать историческое занятие</option></select>')}
      ${field('Источник','<select name="source"><option value="ATTENDANCE_LOG">Журнал посещений</option><option value="TRAINER">Тренер</option><option value="CLIENT">Клиент</option><option value="ADMIN">Администратор</option><option value="OTHER">Другое</option></select>')}
      ${field('Причина внесения','<input name="reason" required maxlength="2000" placeholder="По журналу посещений">')}
      ${field('Пояснение источника','<input name="sourceDetails" maxlength="2000">')}
      <div id="studio-form-error" class="error" role="alert" hidden></div><button class="primary" type="submit">Проверить списание</button></form></section>
      <section class="panel"><h2>Предпросмотр</h2><div id="studio-preview">${empty('Выберите клиента и пакет. До подтверждения посещение не списывается.')}</div></section></div>`);
    const form=document.querySelector('#studio-attendance-form');
    const linkedSessionId=new URLSearchParams(location.hash.split('?')[1]||'').get('session');
    const linkedSession=this.data.sessions.find(session=>session.id===linkedSessionId);
    if(linkedSession)form.startsAt.value=calendarDate(linkedSession.startsAt)+'T'+new Date(linkedSession.startsAt).toLocaleTimeString('en-GB',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'});
    const updateSession=()=>{
      const membership=this.membership(form.membershipId.value),product=this.product(relationId(membership,'product'));
      const startsAt=new Date(form.startsAt.value),duration=Number(product?.durationMinutes);
      const candidates=Number.isFinite(startsAt.getTime())&&duration>0?this.data.sessions.filter(session=>session.status==='COMPLETED'&&session.sessionFormat===product.sessionFormat&&new Date(session.startsAt).getTime()===startsAt.getTime()&&new Date(session.endsAt).getTime()===startsAt.getTime()+duration*60000):[];
      form.existingClassSessionId.innerHTML='<option value="">Создать историческое занятие</option>'+candidates.map(session=>`<option value="${e(session.id)}">${e(session.name||date(session.startsAt))}</option>`).join('');
      if(linkedSessionId&&candidates.some(session=>session.id===linkedSessionId))form.existingClassSessionId.value=linkedSessionId;
    };
    const update=()=>{const packages=personPackages(this.data.packages,form.personId.value).filter(membership=>membership.status==='ACTIVE'&&['GROUP_PACKAGE','PERSONAL'].includes(this.product(relationId(membership,'product'))?.category));form.membershipId.innerHTML=options(packages,membership=>membership.name+' · доступно '+membership.visitsAvailable);updateSession();};
    form.personId.value=new URLSearchParams(location.hash.split('?')[1]||'').get('client')||'';
    update();form.personId.onchange=update;
    form.membershipId.onchange=updateSession;form.startsAt.onchange=updateSession;
    form.oninput=()=>{document.querySelector('#studio-preview').innerHTML=empty('Данные изменены — выполните предпросмотр заново.');};
    this.restore('attendance',form,'/studio/attendance/record-past');
    form.onsubmit=async event=>{
      event.preventDefault(); const button=form.querySelector('[type=submit]');
      button.disabled=true;
      try {
        if(linkedSessionId&&form.existingClassSessionId.value!==linkedSessionId)throw new Error('Выберите пакет, соответствующий формату, времени и длительности выбранной тренировки.');
        const membership=this.membership(form.membershipId.value);
        const body=attendancePayload(Object.fromEntries(new FormData(form)),membership,this.product(relationId(membership,'product')),createOperationId());
        const snapshot=JSON.stringify(Object.fromEntries(new FormData(form)));
        const result=await this.api.request('/studio/attendance/preview',{method:'POST',body});
        if(!form.isConnected||snapshot!==JSON.stringify(Object.fromEntries(new FormData(form))))return;
        document.querySelector('#studio-preview').innerHTML=`<dl><dt>Клиент</dt><dd>${e(this.clientName(body.personId))}</dd><dt>Начало</dt><dd>${e(date(body.startsAt))}</dd><dt>Окончание</dt><dd>${e(date(body.endsAt))}</dd><dt>До списания</dt><dd>${e(result.visitsAvailable)}</dd><dt>После</dt><dd>${e(result.visitsAfter)}</dd></dl><p>Будет списано одно посещение.</p><button id="studio-record" class="primary">Подтвердить посещение и списание</button>`;
        document.querySelector('#studio-record').onclick=()=>this.submit('attendance',body,'/studio/attendance/record-past');
      }catch(error){if(form.isConnected)this.errorBox(error,'#studio-form-error');}
      finally{button.disabled=false;}
    };
  }
  bookingTable(bookings) {
    return table(['Клиент','Занятие','Пакет','Статус'],bookings.map(booking=>{
      const session=this.data.sessions.find(session=>session.id===relationId(booking,'classSession'));
      return `<tr><td>${e(this.clientName(relationId(booking,'person')))}</td><td>${e(date(session?.startsAt))}</td><td>${e(this.membership(relationId(booking,'membership'))?.name||'—')}</td><td><span class="badge">${e(status(booking.status))}</span></td></tr>`;
    }));
  }
  bookings() { this.page(this.header('Посещения Gelios','Записи CRM: подтверждённые, будущие и отменённые')+`<section class="panel">${this.bookingTable(this.data.bookings)}</section><p class="muted">Состав будущих тренировок можно менять в календаре. Проведение обычных бронирований пока выполняется в CRM.</p>`); }
  transactions() {
    this.page(this.header('Журнал списаний','Начисления, резервы, списания и возвраты посещений')+`<section class="panel"><label class="field"><span>Тип операции</span><select id="studio-transaction-filter"><option value="all">Все операции</option><option value="CONSUME">Только списания</option></select></label><div id="studio-ledger"></div></section>`);
    const draw=()=>{
      const filter=document.querySelector('#studio-transaction-filter').value;
      const entries=this.data.transactions.filter(transaction=>filter==='all'||transaction.transactionType===filter).sort((a,b)=>String(b.occurredAt).localeCompare(String(a.occurredAt)));
      document.querySelector('#studio-ledger').innerHTML=table(['Когда','Клиент / пакет','Операция','Посещения','Причина'],entries.map(transaction=>{
        const membership=this.membership(relationId(transaction,'membership'));
        return `<tr><td>${e(date(transaction.occurredAt))}</td><td>${e(this.clientName(relationId(membership,'person')))}<small class="studio-subline">${e(membership?.name||'—')}</small></td><td>${e(status(transaction.transactionType))}</td><td>${e(transaction.visitDelta)}</td><td>${e(transaction.reason||'—')}</td></tr>`;
      }));
    };draw();document.querySelector('#studio-transaction-filter').onchange=draw;
  }
  restore(kind, form, path) {
    const body=this.pending.get(kind);
    if(!body)return;
    form.querySelectorAll('input,select,button').forEach(element=>element.disabled=true);
    form.insertAdjacentHTML('afterend',`<section class="note" id="studio-pending"><h3>Незавершённая отправка</h3><p>Проверьте список и журнал: операция могла сохраниться. Повтор использует прежние данные и ключ.</p><p>Ключ: <code>${e(body.idempotencyKey||body.clientId)}</code></p><div class="actions"><button id="studio-pending-retry" class="primary">Повторить прежний запрос</button><button id="studio-pending-clear" class="secondary">Сбросить после проверки CRM</button></div></section>`);
    document.querySelector('#studio-pending-retry').onclick=()=>this.submit(kind,body,path);
    document.querySelector('#studio-pending-clear').onclick=()=>{
      if(!window.confirm('Вы проверили результат в CRM и разобрали незавершённую операцию? Сброс не отменяет запись или оплату. Новый запрос получит другой ключ и может создать ещё одну операцию.'))return;
      this.pending.clear(kind);this.render(this.route);
    };
  }
  async submit(kind, body, path, propagate = false) {
    if(this.saving)return;
    this.saving=true;
    const generation=this.generation, route=this.route;
    try {
      this.pending.save(kind,body);
      document.querySelectorAll('#page form input,#page form select,#page button').forEach(element=>element.disabled=true);
      const result=await this.api.request(path,{method:'POST',body});
      this.pending.clear(kind);this.data=null;
      this.notify(result.duplicate?'Операция уже сохранена в CRM. Повторного списания нет.':'Сохранено в CRM.');
      if(generation===this.generation)await this.render(route,true);
    } catch(error) {
      if(error.status>=400&&error.status<500)this.pending.clear(kind);
      if(generation===this.generation){await this.render(route);this.errorBox(error,'#page-error',{requestBody:body});}
      if(propagate)throw error;
    } finally {this.saving=false;}
  }
}
