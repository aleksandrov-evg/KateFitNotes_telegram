import {escapeHtml as e,today,weekStart,weekDays,addDays,formatDate} from './domain.js';
import {relationId,calendarDate,sessionParticipants,sessionCanAdd,sessionMemberships,studioPersonName,createOperationId} from './studio-domain.js';

const time=value=>new Date(value).toLocaleTimeString('ru-RU',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit'});
const dateTime=value=>new Date(value).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'});
const statuses={PLANNED:'Запланирована',CONFIRMED:'Подтверждена',COMPLETED:'Завершена',CANCELLED:'Отменена',BOOKED:'Записан',ATTENDED:'Посетил',CANCELLED_BY_STUDIO:'Отменено студией',BOOKING_CREATED:'Клиент добавлен',BOOKING_CANCELLED:'Клиент убран',OPERATION_FAILED:'Операция не выполнена'};
const label=value=>statuses[value]||value||'—';
const field=(id,label,control)=>`<label class="field" for="${id}"><span>${label}</span></label>${control}`;

export class StudioCalendar {
  constructor(studio) {this.studio=studio;this.week=weekStart(today());this.selected=null;}
  render() {
    const {studio}=this,days=weekDays(this.week),data=studio.data;
    studio.page(studio.header('Календарь тренировок','Время студии — Москва · нажмите на тренировку для управления участниками')+
      `<section class="panel studio-calendar"><div class="week-toolbar"><h2>${e(formatDate(days[0]))} — ${e(formatDate(days[6]))}</h2><div class="actions"><button data-calendar-week="-7">← Неделя</button><button data-calendar-week="today">Сегодня</button><button data-calendar-week="7">Неделя →</button></div></div><div class="studio-calendar-grid">${days.map(day=>{
        const sessions=data.sessions.filter(session=>calendarDate(session.startsAt)===day).sort((a,b)=>new Date(a.startsAt)-new Date(b.startsAt));
        return `<section class="studio-calendar-day ${day===today()?'is-today':''}"><h3>${e(formatDate(day,{weekday:'short',day:'numeric',month:'short'}))}</h3>${sessions.map(session=>{
          const participants=sessionParticipants(data.bookings,session.id);
          return `<button class="studio-calendar-event ${session.status==='COMPLETED'?'is-completed':''}" data-session="${e(session.id)}"><time>${e(time(session.startsAt))} — ${e(time(session.endsAt))}</time><strong>${e(session.name||session.sessionFormat)}</strong><span>${e(label(session.status))}</span><small>${participants.length} / ${e(session.capacity)} участников</small></button>`;
        }).join('')||'<p class="muted">Нет тренировок</p>'}</section>`;
      }).join('')}</div></section><p class="muted">Удаление участника означает отмену студией с возвратом резерва. Завершённые посещения и сплиты не удаляются этим действием.</p>`);
    document.querySelectorAll('[data-calendar-week]').forEach(button=>button.onclick=()=>{
      if(studio.saving)return;
      this.week=button.dataset.calendarWeek==='today'?weekStart(today()):addDays(this.week,Number(button.dataset.calendarWeek));
      this.render();document.querySelector('.refresh').onclick=()=>studio.render('calendar',true);
    });
    document.querySelectorAll('[data-session]').forEach(button=>button.onclick=()=>this.open(button.dataset.session));
    const pending=studio.pending.get('booking')||studio.pending.get('cancellation');
    if(pending) {
      const id=pending.classSessionId||relationId(data.bookings.find(booking=>booking.id===pending.bookingId),'classSession');
      if(id)document.querySelector('.studio-calendar').insertAdjacentHTML('beforeend',`<section class="note"><p>Есть незавершённая операция. Проверьте её в карточке тренировки.</p><button id="calendar-recover">Открыть карточку</button></section>`);
      const recover=document.querySelector('#calendar-recover');if(recover)recover.onclick=()=>this.open(id);
    }
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
      studio.notify(result.duplicate?'Операция уже выполнена. Состав тренировки обновлён из CRM.':kind==='booking'?'Клиент добавлен. Резерв и событие сохранены в CRM.':'Клиент убран. Возврат резерва и событие сохранены в CRM.');
    }catch(caught){error=caught;if(caught.status===422)studio.pending.clear(kind);}
    finally{
      studio.saving=false;
      if(generation===studio.generation){
        studio.data=null;
        dialog.close();await studio.render('calendar',true);
        if(studio.data){this.open(sessionId);if(error)studio.errorBox(error,'#dialog-error');}
        else if(error)studio.errorBox(error);
      }
    }
  }
}
