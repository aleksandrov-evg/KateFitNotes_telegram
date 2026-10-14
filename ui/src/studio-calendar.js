import {escapeHtml as e,today,weekStart,weekDays,addDays,formatDate} from './domain.js';
import {relationId,calendarDate,sessionParticipants,sessionCanAdd,sessionMemberships,studioPersonName,createOperationId,sessionFormats,sessionTimeState,sessionCreationPayload,calendarSessionLayout} from './studio-domain.js';

const time=value=>new Date(value).toLocaleTimeString('ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'});
const dateTime=value=>new Date(value).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'});
const statuses={PLANNED:'Запланирована',CONFIRMED:'Идёт / подтверждена',COMPLETED:'Завершена',CANCELLED:'Отменена',BOOKED:'Записан',ATTENDED:'Посетил',CANCELLED_BY_STUDIO:'Отменено студией',BOOKING_CREATED:'Клиент добавлен',BOOKING_CANCELLED:'Клиент убран',SESSION_CREATED:'Тренировка создана',OPERATION_FAILED:'Операция не выполнена'};
const label=value=>statuses[value]||value||'—';
const field=(id,label,control)=>`<label class="field" for="${id}"><span>${label}</span></label>${control}`;

export class StudioCalendar {
  constructor(studio) {this.studio=studio;this.week=weekStart(today());this.selected=null;}
  render() {
    const {studio}=this,days=weekDays(this.week),data=studio.data;
    const slots=Array.from({length:32},(_,index)=>{const minutes=7*60+index*30;return String(Math.floor(minutes/60)).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0');});
    const visibleIds=new Set(days.flatMap(day=>calendarSessionLayout(data.sessions,day).map(({session})=>session.id)));
    const outside=data.sessions.filter(session=>days.includes(calendarDate(session.startsAt))&&!visibleIds.has(session.id));
    studio.page(studio.header('Календарь тренировок','Москва · нажмите на свободное время для создания или на тренировку для просмотра','<button id="calendar-new" class="primary">+ Новая тренировка</button>')+
      `<section class="panel studio-calendar"><div class="week-toolbar"><h2>${e(formatDate(days[0]))} — ${e(formatDate(days[6]))}</h2><div class="actions"><button data-calendar-week="-7">← Неделя</button><button data-calendar-week="today">Сегодня</button><button data-calendar-week="7">Неделя →</button></div></div>
      <p class="muted">Сетка 07:00–23:00, шаг 30 минут. Любое другое время можно задать в форме. На телефоне сетка прокручивается по горизонтали.</p>
      <div class="calendar-time-scroll" tabindex="0" aria-label="Временная сетка недели"><div class="calendar-time-head"><span>МСК</span>${days.map(day=>`<strong class="${day===today()?'is-today':''}">${e(formatDate(day,{weekday:'short',day:'numeric',month:'short'}))}</strong>`).join('')}</div>
      <div class="calendar-time-body"><div class="calendar-time-axis">${slots.map(slot=>`<span>${slot}</span>`).join('')}</div>${days.map(day=>`<div class="calendar-time-day">${slots.map(slot=>`<button class="calendar-free-slot" data-calendar-slot="${day}T${slot}" aria-label="Создать тренировку: ${e(formatDate(day))}, ${slot}"><span class="sr-only">${slot}</span></button>`).join('')}${calendarSessionLayout(data.sessions,day).map(({session,top,height,lane,laneCount})=>`<button class="calendar-grid-event ${session.status==='COMPLETED'?'is-completed':''} ${session.status==='CANCELLED_BY_STUDIO'?'is-cancelled':''}" data-grid-top="${top}" data-grid-height="${height}" data-grid-left="${lane/laneCount*100}" data-grid-width="${100/laneCount}" data-session="${e(session.id)}" aria-label="${e(session.name)} · ${e(dateTime(session.startsAt))}"><time>${e(time(session.startsAt))}–${e(time(session.endsAt))}</time><strong>${e(session.name||session.sessionFormat)}</strong><small>${sessionParticipants(data.bookings,session.id).length}/${e(session.capacity)} · ${e(label(session.status))}</small></button>`).join('')}</div>`).join('')}</div></div>
      ${outside.length?`<h3>Вне основной сетки</h3>${outside.map(session=>`<button data-session="${e(session.id)}">${e(dateTime(session.startsAt))} · ${e(session.name)}</button>`).join('')}`:''}</section><p class="muted">Создание тренировки не списывает посещения. Удаление участника — отмена студией с возвратом резерва.</p>`);
    document.querySelector('#calendar-new').onclick=()=>{if(!studio.saving)this.openCreate();};
    document.querySelectorAll('.calendar-grid-event').forEach(button=>{button.style.top=button.dataset.gridTop+'px';button.style.height=button.dataset.gridHeight+'px';button.style.left='calc('+button.dataset.gridLeft+'% + 2px)';button.style.width='calc('+button.dataset.gridWidth+'% - 4px)';});
    document.querySelectorAll('[data-calendar-slot]').forEach(button=>button.onclick=()=>{if(!studio.saving)this.openCreate(button.dataset.calendarSlot);});
    document.querySelectorAll('[data-calendar-week]').forEach(button=>button.onclick=()=>{
      if(studio.saving)return;
      this.week=button.dataset.calendarWeek==='today'?weekStart(today()):addDays(this.week,Number(button.dataset.calendarWeek));
      this.render();document.querySelector('.refresh').onclick=()=>studio.render('calendar',true);
    });
    document.querySelectorAll('[data-session]').forEach(button=>button.onclick=event=>{event.stopPropagation();if(!studio.saving)this.open(button.dataset.session);});
    const pendingSession=studio.pending.get('session');
    if(pendingSession){
      document.querySelector('.studio-calendar').insertAdjacentHTML('beforeend','<section class="note"><p>Создание тренировки не подтверждено. Не создавайте новую: восстановите прежний запрос.</p><button id="calendar-session-recover">Продолжить создание</button></section>');
      document.querySelector('#calendar-session-recover').onclick=()=>this.openCreate();
    }
    const pending=studio.pending.get('booking')||studio.pending.get('cancellation');
    if(pending) {
      const id=pending.classSessionId||relationId(data.bookings.find(booking=>booking.id===pending.bookingId),'classSession');
      if(id)document.querySelector('.studio-calendar').insertAdjacentHTML('beforeend',`<section class="note"><p>Есть незавершённая операция. Проверьте её в карточке тренировки.</p><button id="calendar-recover">Открыть карточку</button></section>`);
      const recover=document.querySelector('#calendar-recover');if(recover)recover.onclick=()=>this.open(id);
    }
  }
  openCreate(slot) {
    const {studio}=this,pending=studio.pending.get('session');
    const pendingStart=pending?calendarDate(pending.startsAt)+'T'+time(pending.startsAt):null;
    const values=pending?{...pending,startsAt:pendingStart,pastConfirmed:pending.pastConfirmed?'on':''}:slot?{startsAt:slot}:this.creationDraft||{};
    studio.showDialog('Новая тренировка',`<form id="calendar-create-form">
      ${field('session-name','Название','<input id="session-name" name="name" maxlength="200" required>')}
      ${field('session-format','Формат',`<select id="session-format" name="sessionFormat">${sessionFormats.map(([value,text])=>`<option value="${value}">${e(text)}</option>`).join('')}</select>`)}
      ${field('session-start','Дата и начало (Москва)','<input id="session-start" name="startsAt" type="datetime-local" required>')}
      ${field('session-duration','Длительность, минут','<input id="session-duration" name="durationMinutes" type="number" min="1" max="1440" required>')}
      ${field('session-capacity','Количество мест','<input id="session-capacity" name="capacity" type="number" min="1" max="100" required>')}
      <section class="session-participant-picker"><h3>Участники</h3><p id="session-participant-help" class="muted"></p>
      ${field('session-person','Доступный клиент','<select id="session-person"><option value="">Выберите клиента</option></select>')}
      ${field('session-membership','Пакет клиента','<select id="session-membership"><option value="">Сначала выберите клиента</option></select>')}
      <button id="session-participant-add" type="button" class="secondary">Добавить в список</button><div id="session-selected-people"></div></section>
      <p id="session-time-note" class="note"></p><label id="session-past-confirmation" class="session-confirmation"><input name="pastConfirmed" type="checkbox"> Подтверждаю, что тренировка состоялась</label>
      ${field('session-attendance-reason','Основание внесения посещений (для прошедшей тренировки)','<input id="session-attendance-reason" name="attendanceReason" maxlength="2000">')}
      <p class="muted">Будущее: резерв по одному посещению участника. Прошедшее: после проверки CRM списание по одному фактическому посещению. Пустое занятие ничего не списывает.</p><div id="session-create-error" class="error" role="alert" hidden></div><button id="session-create-submit" type="submit" class="primary">Сохранить тренировку</button></form><div id="session-create-pending"></div>`);
    const dialog=document.querySelector('#confirm');dialog.classList.add('calendar-dialog');
    const form=dialog.querySelector('#calendar-create-form');
    form.elements.name.value=values.name||'';
    form.sessionFormat.value=values.sessionFormat||'GROUP_REFORMER';
    form.startsAt.value=values.startsAt||today()+'T09:00';
    form.durationMinutes.value=values.durationMinutes||55;form.capacity.value=values.capacity||4;
    form.pastConfirmed.checked=values.pastConfirmed==='on';
    form.attendanceReason.value=values.attendanceReason||'';
    let selected=(values.participants||[]).map(participant=>({...participant}));
    const personSelect=dialog.querySelector('#session-person'),membershipSelect=dialog.querySelector('#session-membership');
    const sessionDraft=()=>({startsAt:new Date(form.startsAt.value+':00+03:00').toISOString(),sessionFormat:form.sessionFormat.value,durationMinutes:Number(form.durationMinutes.value),status:sessionTimeState(form.startsAt.value+':00+03:00',form.durationMinutes.value)});
    const matching=personId=>sessionMemberships(studio.data.packages,studio.data.products,personId,sessionDraft());
    const renderPeople=()=>{
      let eligible=[];try{eligible=studio.data.clients.filter(person=>matching(person.id).length>0);}catch{}
      const chosen=personSelect.value,chosenPackage=membershipSelect.value;
      personSelect.innerHTML='<option value="">Выберите клиента</option>'+eligible.filter(person=>!selected.some(participant=>participant.personId===person.id)).map(person=>`<option value="${e(person.id)}">${e(studioPersonName(person))}</option>`).join('');
      personSelect.value=eligible.some(person=>person.id===chosen&&!selected.some(participant=>participant.personId===chosen))?chosen:'';
      const packages=personSelect.value?matching(personSelect.value):[];
      membershipSelect.innerHTML='<option value="">Выберите пакет</option>'+packages.map(membership=>`<option value="${e(membership.id)}">${e(membership.name)} · доступно ${e(membership.visitsAvailable)}</option>`).join('');
      membershipSelect.value=packages.some(membership=>membership.id===chosenPackage)?chosenPackage:packages[0]?.id||'';
      const personal=form.sessionFormat.value==='PERSONAL_EQUIPMENT';
      dialog.querySelector('#session-participant-help').textContent=(personal?'Персональная: один клиент с персональным пакетом.':'Групповая: несколько клиентов с групповыми пакетами.')+` Подходящих клиентов: ${eligible.length}. Выбрано: ${selected.length}/${form.capacity.value}. Пакет должен покрывать дату, формат и для прошлой даты — длительность занятия.`;
      dialog.querySelector('#session-selected-people').innerHTML=selected.map(participant=>`<div class="calendar-participant"><div><strong>${e(studio.clientName(participant.personId))}</strong><small>${e(studio.membership(participant.membershipId)?.name||'Пакет')}</small></div><button type="button" data-remove-selected="${e(participant.personId)}">Убрать из списка</button></div>`).join('');
      dialog.querySelectorAll('[data-remove-selected]').forEach(button=>button.onclick=()=>{selected=selected.filter(participant=>participant.personId!==button.dataset.removeSelected);update();});
      dialog.querySelector('#session-participant-add').disabled=Boolean(pending)||selected.length>=Number(form.capacity.value)||!personSelect.value||!membershipSelect.value;
    };
    const update=()=>{
      this.creationDraft={...Object.fromEntries(new FormData(form)),participants:selected};
      try{
        form.capacity.readOnly=form.sessionFormat.value==='PERSONAL_EQUIPMENT';
        const status=sessionTimeState(form.startsAt.value+':00+03:00',form.durationMinutes.value);
        dialog.querySelector('#session-past-confirmation').hidden=status!=='COMPLETED';
        form.pastConfirmed.required=status==='COMPLETED';
        form.attendanceReason.required=status==='COMPLETED'&&selected.length>0;
        dialog.querySelector('#session-create-submit').textContent=status==='COMPLETED'?'Внести прошедшую тренировку':status==='PLANNED'?'Запланировать тренировку':'Сохранить текущую тренировку';
        dialog.querySelector('#session-time-note').textContent=status==='COMPLETED'?`Прошедшая дата: выбранные участники считаются посетившими занятие. Будет списано по одному посещению: ${selected.length}.`:status==='PLANNED'?`Будущая дата: запланированное занятие. По одному посещению будет зарезервировано: ${selected.length}.`:'Занятие уже идёт: участников можно внести после его окончания.';
      }catch(error){dialog.querySelector('#session-time-note').textContent=error.message;}
      renderPeople();
    };
    form.sessionFormat.onchange=()=>{form.capacity.value=form.sessionFormat.value==='PERSONAL_EQUIPMENT'?1:4;update();};
    dialog.querySelector('#session-participant-add').onclick=()=>{if(selected.length>=Number(form.capacity.value)||!personSelect.value||!membershipSelect.value)return;selected.push({personId:personSelect.value,membershipId:membershipSelect.value});update();};
    update();form.oninput=update;
    form.onsubmit=event=>{
      event.preventDefault();
      try{
        this.creationDraft={...Object.fromEntries(new FormData(form)),participants:selected};
        const body=sessionCreationPayload(this.creationDraft,createOperationId());
        if(body.sessionFormat==='PERSONAL_EQUIPMENT'&&(body.capacity!==1||selected.length>1))throw new Error('Персональная тренировка: только один клиент и одно место.');
        if(selected.length>body.capacity||selected.some(participant=>!matching(participant.personId).some(membership=>membership.id===participant.membershipId)))throw new Error('Проверьте выбранных участников: вместимость или доступность пакетов изменилась.');
        if(selected.length&&['CONFIRMED'].includes(body.status))throw new Error('Участники текущей тренировки вносятся после её окончания.');
        this.send('session',{...body,participants:selected,attendanceReason:form.attendanceReason.value.trim()},'/studio/sessions/create');
      }
      catch(error){studio.errorBox(error,'#session-create-error');}
    };
    if(pending){
      form.querySelectorAll('input,select,button').forEach(control=>control.disabled=true);
      dialog.querySelector('#session-create-pending').innerHTML=`<section class="note"><h3>Незавершённое создание</h3><p>Проверьте календарь и журнал. Повтор сохраняет данные и ключ ${e(pending.idempotencyKey)}.</p><button id="session-create-retry">Повторить прежний запрос</button><button id="session-create-clear">Сбросить после проверки CRM</button></section>`;
      dialog.querySelector('#session-create-retry').onclick=()=>this.send('session',pending,'/studio/sessions/create');
      dialog.querySelector('#session-create-clear').onclick=()=>{if(studio.saving||!window.confirm('Вы проверили создание в CRM? Сброс ничего не отменяет.'))return;studio.pending.clear('session');this.openCreate();};
    }
    dialog.oncancel=event=>{if(studio.saving)event.preventDefault();};
  }
  open(sessionId) {
    const {studio}=this,data=studio.data,session=data.sessions.find(session=>session.id===sessionId);
    if(!session)return;
    this.selected=sessionId;
    const bookings=data.bookings.filter(booking=>relationId(booking,'classSession')===sessionId);
    const active=sessionParticipants(bookings,sessionId),canAdd=sessionCanAdd(session,bookings);
    const events=(data.events||[]).filter(event=>event.classSessionId===sessionId||bookings.some(booking=>booking.id===event.bookingId)).sort((a,b)=>String(b.occurredAt).localeCompare(String(a.occurredAt)));
    studio.showDialog('Тренировка',`<div class="calendar-session-details"><h3>${e(session.name||session.sessionFormat)}</h3><dl><dt>Когда</dt><dd>${e(dateTime(session.startsAt))} — ${e(time(session.endsAt))}</dd><dt>Статус</dt><dd>${e(label(session.status))}</dd><dt>Места</dt><dd>${active.length} / ${e(session.capacity)}</dd></dl><h3>Участники</h3><div class="calendar-participants">${bookings.map(booking=>`<div class="calendar-participant"><div><strong>${e(studio.clientName(relationId(booking,'person')))}</strong><small>${e(label(booking.status))} · ${e(studio.membership(relationId(booking,'membership'))?.name||'Без пакета')}</small></div>${['BOOKED','CONFIRMED'].includes(booking.status)&&['REGULAR','PERSONAL'].includes(booking.bookingType)&&new Date(session.startsAt)>new Date()?`<button class="secondary" data-remove-booking="${e(booking.id)}">Убрать клиента</button>`:''}</div>`).join('')||'<p class="muted">Участников пока нет</p>'}</div>
      ${canAdd?`<h3>Добавить клиента</h3><form id="calendar-add-form">${field('calendar-person','Клиент',`<select id="calendar-person" name="personId" required><option value="">Выберите клиента…</option>${data.clients.filter(person=>!active.some(booking=>relationId(booking,'person')===person.id)).map(person=>`<option value="${e(person.id)}">${e(studioPersonName(person))}</option>`).join('')}</select>`)}${field('calendar-membership','Пакет', '<select id="calendar-membership" name="membershipId" required><option value="">Сначала выберите клиента</option></select>')}<p class="muted">Одно посещение будет зарезервировано, не списано как посещённое.</p><div id="calendar-error" class="error" role="alert" hidden></div><button type="submit" class="primary">Добавить клиента в тренировку</button></form>`:'<p class="note">Добавление недоступно: занятие прошло, отменено или мест больше нет. История сохраняется в CRM.</p>'}
      ${session.status==='COMPLETED'&&new Date(session.endsAt)<=new Date()?`<a class="button primary" href="#gelios/attendance?session=${encodeURIComponent(sessionId)}">Внести фактическое посещение</a>`:''}
      <div id="calendar-pending"></div><h3>Журнал CRM</h3><div class="calendar-history">${events.map(event=>`<p><strong>${e(label(event.eventType))}</strong><small>${e(dateTime(event.occurredAt))} · ${e(event.outcome==='SUCCESS'?'Успешно':'Ошибка')}</small></p>`).join('')||'<p class="muted">Событий этой тренировки пока нет</p>'}</div></div>`);
    const dialog=document.querySelector('#confirm');
    dialog.classList.add('calendar-dialog');
    const form=dialog.querySelector('#calendar-add-form');
    if(form) {
      form.personId.onchange=()=>{
        const packages=sessionMemberships(data.packages,data.products,form.personId.value,session);
        form.membershipId.innerHTML='<option value="">Выберите пакет…</option>'+packages.map(membership=>`<option value="${e(membership.id)}">${e(membership.name)} · доступно ${e(membership.visitsAvailable)}</option>`).join('');
        if(!packages.length)form.membershipId.innerHTML='<option value="">Нет подходящего активного пакета</option>';
      };
      form.onsubmit=event=>{
        event.preventDefault();
        try {this.send('booking',{...Object.fromEntries(new FormData(form)),classSessionId:sessionId,idempotencyKey:createOperationId()},'/studio/bookings/create',sessionId);}
        catch(error){studio.errorBox(error,'#calendar-error');}
      };
    }
    dialog.querySelectorAll('[data-remove-booking]').forEach(button=>button.onclick=()=>{
      if(studio.saving||!window.confirm('Убрать клиента из тренировки? Это отмена студией: резерв посещения вернётся в пакет. Запись и событие останутся в CRM.'))return;
      try {this.send('cancellation',{bookingId:button.dataset.removeBooking,cancelledAt:new Date().toISOString(),idempotencyKey:createOperationId()},'/studio/bookings/cancel',sessionId);}
      catch(error){studio.errorBox(error,'#dialog-error');}
    });
    for(const kind of ['booking','cancellation']){
      const body=studio.pending.get(kind);if(!body)continue;
      dialog.querySelectorAll('form input,form select,form button,[data-remove-booking]').forEach(control=>control.disabled=true);
      dialog.querySelector('#calendar-pending').insertAdjacentHTML('beforeend',`<section class="note"><h3>Незавершённая операция</h3><p>Проверьте участников и журнал. Повтор сохраняет прежний ключ: <code>${e(body.idempotencyKey)}</code>.</p><button data-retry-calendar="${kind}">Повторить прежний запрос</button><button data-clear-calendar="${kind}">Сбросить после проверки CRM</button></section>`);
      dialog.querySelector(`[data-retry-calendar="${kind}"]`).onclick=()=>this.send(kind,body,kind==='booking'?'/studio/bookings/create':'/studio/bookings/cancel',body.classSessionId||relationId(data.bookings.find(booking=>booking.id===body.bookingId),'classSession'));
      dialog.querySelector(`[data-clear-calendar="${kind}"]`).onclick=()=>{
        if(studio.saving||!window.confirm('Результат проверен в CRM? Сброс не отменяет серверное действие.'))return;
        studio.pending.clear(kind);this.open(sessionId);
      };
    }
    dialog.oncancel=event=>{if(studio.saving)event.preventDefault();};
  }
  async send(kind,body,path,sessionId) {
    const {studio}=this;if(studio.saving)return;
    studio.saving=true;const generation=studio.generation;
    const dialog=document.querySelector('#confirm');
    let error;
    try{
      studio.pending.save(kind,body);
      dialog.querySelectorAll('button,input,select').forEach(control=>control.disabled=true);
      const result=await studio.api.request(path,{method:'POST',body});
      studio.pending.clear(kind);studio.data=null;
      if(kind==='session'){sessionId=result.classSessionId;this.week=weekStart(calendarDate(body.startsAt));this.creationDraft=null;}
      studio.notify(result.duplicate?'Операция уже выполнена. Данные обновлены из CRM.':kind==='session'?'Тренировка и событие создания сохранены в CRM.':kind==='booking'?'Клиент добавлен. Резерв и событие сохранены в CRM.':'Клиент убран. Возврат резерва и событие сохранены в CRM.');
    }catch(caught){error=caught;if(caught.status===422)studio.pending.clear(kind);}
    finally{
      studio.saving=false;
      if(generation===studio.generation){
        studio.data=null;
        dialog.close();await studio.render('calendar',true);
        if(studio.data){if(kind==='session'&&error)this.openCreate();else this.open(sessionId);if(error)studio.errorBox(error,'#dialog-error');}
        else if(error)studio.errorBox(error);
      }
    }
  }
}
