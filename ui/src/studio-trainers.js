import {escapeHtml as e} from './domain.js';
import {calendarDate,createOperationId,relationId} from './studio-domain.js';
import {analyticsMoney,formatMinorMoney as money,parseMinorMoney} from './studio-money.js';
import {buildTrainerPayroll} from './studio-payroll-domain.js';

const RESOURCES=['trainers','trainerRates','trainerAssignments','trainerPayEntries','sessions'];
const table=(headers,rows)=>rows.length?`<div class="table-wrap" tabindex="0"><table><thead><tr>${headers.map(text=>`<th scope="col">${e(text)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'<p class="empty">Записей пока нет.</p>';
const action=(name,text,id='')=>`<button type="button" class="secondary" data-trainer-action="${name}" data-id="${e(id)}">${e(text)}</button>`;
const field=(label,control)=>`<label class="field"><span>${e(label)}</span>${control}</label>`;
const optionList=(rows,selected)=>`<option value="">Выберите…</option>`+rows.map(row=>`<option value="${e(row.id)}" ${row.id===selected?'selected':''}>${e(row.name)}</option>`).join('');
const date=value=>value?new Date(value).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}):'—';
const statuses={ATTENDED:'Посетил',NO_SHOW:'Неявка',LATE_CANCEL:'Поздняя отмена',CANCELLED_IN_TIME:'Отмена вовремя',CANCELLED_BY_STUDIO:'Отмена студией',BOOKED:'Записан'};

export class StudioTrainers {
  constructor(studio){this.studio=studio;this.data=null;this.generation=0;this.tab='salary';this.month=calendarDate(new Date()).slice(0,7);}
  deactivate(){this.generation++;}
  async load(force=false){
    if(!this.data||force){
      const lists=await Promise.all(RESOURCES.map(resource=>this.studio.api.studioRecords(resource)));
      this.data=Object.fromEntries(RESOURCES.map((resource,index)=>[resource,lists[index]]));
    }
    return this.data;
  }
  async render(force=false){
    const run=++this.generation;
    this.studio.page(this.studio.header('Тренеры и зарплата','Каталог, тарифы и начисления CRM')+'<p role="status">Загружаем тренеров…</p>');
    try{await this.load(force);if(run!==this.generation)return;this.paint();}
    catch(error){if(run!==this.generation)return;this.data=null;this.studio.page(this.studio.header('Тренеры и зарплата','Данные CRM')+`<p role="alert" class="error">${e(error.message)}</p>${action('reload','Повторить загрузку')}`);this.bind();}
  }
  model(){return buildTrainerPayroll(this.data||{},{month:this.month});}
  paint(){
    const tabs={salary:'Зарплата за месяц',catalog:'Тренеры',rates:'Тарифы',assignments:'Назначения тарифов',journal:'Журнал начислений'};
    const body=this.tab==='salary'?`<label class="field">Месяц<input id="trainer-month" type="month" value="${e(this.month)}" min="2000-01" max="2100-12"></label>${this.monthlyContent(this.model())}`:this.tab==='catalog'?this.catalog():this.tab==='rates'?this.rates():this.tab==='journal'?this.journal():this.assignments();
    this.studio.page(this.studio.header('Тренеры и зарплата','Зарплата начисляется один раз за проведённое занятие',action('new-trainer','+ Тренер'))+`<div class="analytics"><nav class="analytics-tabs" aria-label="Разделы тренеров">${Object.entries(tabs).map(([key,label])=>`<button type="button" data-trainer-tab="${key}" aria-current="${key===this.tab?'page':'false'}">${e(label)}</button>`).join('')}</nav><section class="panel analytics-panel">${body}</section></div>`);
    this.bind();
  }
  monthlyContent(report){
    if(!report.available)return `<p role="alert" class="analytics-notice error">${e(report.reasons.join(' '))}</p>`;
    return `<div class="analytics-metrics"><article class="analytics-metric"><span>Начислено тренерам</span><strong>${e(money(report.amountMinor))}</strong><small>${report.sessionCount} занятий · ${report.participantCount} фактических посещений</small></article></div>${report.warnings.map(text=>`<p class="analytics-notice" role="status">${e(text)}</p>`).join('')}<p>Относится к месяцу проведения занятия. Включено в начисленные затраты автоматически. Фактическая выплата зарплаты здесь не отмечается.</p>${table(['Тренер','Занятия','Посещения','Начислено','Детали'],report.trainers.map(trainer=>[`${e(trainer.name)}${trainer.active===false?' <small>(неактивен)</small>':''}`,e(trainer.sessionCount),e(trainer.participantCount),e(money(trainer.amountMinor)),action('salary-detail','Занятия',trainer.id)]))}`;
  }
  catalog(){return `<h2>Каталог тренеров</h2>${table(['Тренер','Статус','Действия'],this.data.trainers.filter(row=>!row.deletedAt).map(row=>[e(row.name),row.active?'Активен':'Неактивен',action('edit-trainer','Изменить',row.id)]))}`;}
  rates(){return `<div class="analytics-panel-heading"><h2>Четыре ступени оплаты группы</h2>${action('new-rate','+ Версия тарифа')}</div><p>Каждая сумма задаётся отдельно, включая оплату за четверых. Опубликованный тариф не редактируется — создайте следующую версию.</p>${table(['Тариф','Версия','1 человек','2 человека','3 человека','4 человека','Статус / действия'],this.data.trainerRates.filter(row=>!row.deletedAt).map(row=>{
    let published=null;try{published=row.publishedSnapshot?JSON.parse(row.publishedSnapshot):null;}catch{return [e(row.name),'—','—','—','—','—','Снимок повреждён — требуется сверка'];}
    const rate=published||row;
    return [e(rate.name),e(rate.version),...[1,2,3,4].map(count=>e(money(analyticsMoney(rate['amountFor'+count])))),published?'Опубликован':action('edit-rate','Изменить',row.id)+' '+action('publish-rate','Опубликовать',row.id)];
  }))}`;}
  assignments(){return `<div class="analytics-panel-heading"><h2>Периоды действия тарифов</h2>${action('new-assignment','+ Назначить тариф')}</div><p>Начало включается, окончание не включается. Периоды одного тренера не должны пересекаться.</p>${table(['Тренер','Тариф','С','До','Действия'],this.data.trainerAssignments.filter(row=>!row.deletedAt).map(row=>[e(this.data.trainers.find(item=>item.id===relationId(row,'trainer'))?.name||'Тренер'),e(this.data.trainerRates.find(item=>item.id===relationId(row,'payRate'))?.name||'Тариф'),e(date(row.validFrom)),e(date(row.validUntil)),action('edit-assignment','Изменить период',row.id)]))}`;}
  journal(){
    return `<h2>История начислений и исправлений</h2><p>Сторно сохраняет исходное начисление. Итог зарплаты и затрат берётся из последней завершённой ревизии каждого занятия.</p>${table(['Записано','Операция','Ревизия','Состояние','Сумма','Действия'],this.data.trainerPayEntries.filter(row=>!row.deletedAt).sort((a,b)=>String(b.recordedAt).localeCompare(String(a.recordedAt))).map(row=>[e(date(row.recordedAt)),e(row.entryType==='REVERSAL'?'Сторно':'Начисление'),e(row.revision),e(row.state==='POSTED'?'Проведено':'Не завершено'),e(money(analyticsMoney(row.amount))),action('journal-detail','Полная запись',row.id)]))}`;
  }
  journalDetails(id){
    const row=this.data.trainerPayEntries.find(item=>item.id===id);if(!row)return;
    let snapshot;try{snapshot=JSON.parse(row.snapshot);}catch{snapshot=row.snapshot;}
    this.studio.showDialog('Запись реестра зарплаты',`<p>${row.entryType==='REVERSAL'?'Сторно':'Начисление'} · ревизия ${e(row.revision)} · ${e(row.state)}</p><p>${e(date(row.recordedAt))} · ${e(row.recordedBy||'—')}</p><p>Сумма: ${e(money(analyticsMoney(row.amount)))}</p><p>Основание: ${e(row.reason||'Закрытие занятия')}</p><p>ID: ${e(row.id)}</p><p>Предыдущее начисление: ${e(row.previousEntryId||'—')}</p><p>Ключ операции: ${e(row.requestKey||'—')}</p><details><summary>Полный снимок расчёта</summary><pre class="payroll-snapshot">${e(typeof snapshot==='string'?snapshot:JSON.stringify(snapshot,null,2))}</pre></details>${row.state==='PENDING'?action('resume-session','Продолжить начисление',relationId(row,'classSession')):''}`);
    this.bindActions(document.querySelector('#confirm'));
  }
  bind(){
    document.querySelector('.refresh')?.addEventListener('click',()=>this.render(true));
    document.querySelectorAll('[data-trainer-tab]').forEach(button=>button.onclick=()=>{this.tab=button.dataset.trainerTab;this.paint();});
    document.querySelector('#trainer-month')?.addEventListener('change',event=>{if(/^\d{4}-(0[1-9]|1[0-2])$/.test(event.target.value)){this.month=event.target.value;this.paint();}});
    this.bindActions();
  }
  bindActions(root=document,report=null){root.querySelectorAll('[data-trainer-action]').forEach(button=>button.onclick=()=>this.action(button.dataset.trainerAction,button.dataset.id,report));}
  action(name,id,report=null){
    if(name==='reload')return this.render(true);
    if(name==='journal-detail')return this.journalDetails(id);
    if(name==='resume-session'){const session=this.data?.sessions.find(row=>row.id===id);if(session)return this.closeSession(session);}
    if(name==='new-trainer')return this.trainerForm();
    if(name==='edit-trainer')return this.trainerForm(this.data.trainers.find(row=>row.id===id));
    if(name==='new-rate')return this.rateForm();
    if(name==='edit-rate')return this.rateForm(this.data.trainerRates.find(row=>row.id===id));
    if(name==='publish-rate')return this.publishRate(id);
    if(name==='new-assignment')return this.assignmentForm();
    if(name==='edit-assignment')return this.assignmentForm(this.data.trainerAssignments.find(row=>row.id===id));
    if(name==='salary-detail')return this.details(id,report||this.model());
    if(name==='entry-detail')return this.entryDetails(id,report||this.model());
  }
  async changed(){this.data=null;this.studio.data=null;this.studio.analytics.data=null;if(this.studio.route==='trainers')await this.render(true);else if(this.studio.route==='calendar')await this.studio.render('calendar',true);}
  form(title,content,save){
    let unknown=false;
    this.studio.showDialog(title,`<form id="trainer-settings-form">${content}</form>`,async()=>{
      if(unknown)throw new Error('Результат неизвестен. Закройте окно и обновите каталог перед повтором.');
      const form=document.querySelector('#trainer-settings-form');if(!form.reportValidity())throw new Error('Проверьте заполнение полей.');
      this.studio.saving=true;
      try{await save(form);this.studio.notify('Сохранено в CRM.');try{await this.changed();}catch{this.studio.notify('Сохранено. Обновите данные для проверки.');}}
      catch(error){if(!error.status||error.status>=500)unknown=true;throw error;}
      finally{this.studio.saving=false;}
    });
    const form=document.querySelector('#trainer-settings-form');form.onsubmit=event=>{event.preventDefault();document.querySelector('#dialog-submit').click();};document.querySelector('#dialog-submit').textContent='Сохранить';
  }
  trainerForm(record){
    const trainerId=record?.id||createOperationId();
    this.form(record?'Изменить тренера':'Новый тренер',field('Имя тренера',`<input name="name" value="${e(record?.name||'')}" maxlength="200" required>`)+`<label><input name="active" type="checkbox" ${record?.active!==false?'checked':''}> Активен — доступен для назначения</label>`,form=>this.studio.api.request('/studio/trainers/save',{method:'POST',body:{trainerId,name:form.elements.name.value.trim(),active:form.elements.active.checked}}));
  }
  rateForm(record){
    const rateId=record?.id||createOperationId();
    this.form(record?'Черновик тарифа':'Новая версия тарифа',field('Название',`<input name="name" value="${e(record?.name||'')}" maxlength="200" required>`)+field('Версия',`<input name="version" type="number" min="1" step="1" value="${record?.version||1}" required>`)+[1,2,3,4].map(count=>field(`${count} участников, ₽`,`<input name="amount${count}" inputmode="decimal" value="${record?e(this.amountInput(analyticsMoney(record['amountFor'+count]))):''}" required>`)).join(''),form=>this.studio.api.request('/studio/trainer-rates/save',{method:'POST',body:{rateId,name:form.elements.name.value.trim(),version:Number(form.elements.version.value),amountsMinor:[1,2,3,4].map(count=>parseMinorMoney(form.elements['amount'+count].value))}}));
  }
  amountInput(value){return value===null?'':`${BigInt(value)/100n}.${String(BigInt(value)%100n).padStart(2,'0')}`;}
  publishRate(id){this.studio.showDialog('Опубликовать тариф?', '<p>Все четыре ступени будут зафиксированы. Для последующего изменения потребуется новая версия.</p>',async()=>{this.studio.saving=true;try{await this.studio.api.request('/studio/trainer-rates/publish',{method:'POST',body:{payRateId:id}});await this.changed();}finally{this.studio.saving=false;}});document.querySelector('#dialog-submit').textContent='Опубликовать';}
  assignmentForm(record){
    const assignmentId=record?.id||createOperationId();
    const asDay=value=>value?calendarDate(value):'';
    this.form('Назначение тарифа',field('Тренер',`<select name="trainerId" required>${optionList(this.data.trainers.filter(row=>row.active),relationId(record,'trainer'))}</select>`)+field('Опубликованный тариф',`<select name="payRateId" required>${optionList(this.data.trainerRates.filter(row=>row.publishedSnapshot),relationId(record,'payRate'))}</select>`)+field('Действует с (Москва)',`<input name="validFrom" type="date" value="${e(asDay(record?.validFrom)||calendarDate(new Date()))}" required>`)+field('Действует до, не включая (необязательно)',`<input name="validUntil" type="date" value="${e(asDay(record?.validUntil))}">`),form=>this.studio.api.request('/studio/trainer-assignments/save',{method:'POST',body:{assignmentId,trainerId:form.elements.trainerId.value,payRateId:form.elements.payRateId.value,validFrom:form.elements.validFrom.value+'T00:00:00+03:00',validUntil:form.elements.validUntil.value?form.elements.validUntil.value+'T00:00:00+03:00':null}}));
  }
  details(trainerId,report){
    const trainer=report.trainers.find(row=>row.id===trainerId);if(!trainer)return;
    this.studio.showDialog(e(trainer.name),`<p>${e(report.month||this.month)} · ${trainer.sessionCount} занятий · <strong>${e(money(trainer.amountMinor))}</strong></p>${table(['Занятие','Дата','Посетило','Начислено','Детали'],trainer.rows.map(row=>[e(row.name),e(date(row.snapshot.session.startsAt)),e(row.participantCount),e(money(row.amountMinor)),action('entry-detail','Расчёт',row.id)]))}`);this.bindActions(document.querySelector('#confirm'),report);
  }
  entryDetails(entryId,report){
    const row=(report.allRows||report.rows).find(item=>item.id===entryId);if(!row)return;
    this.studio.showDialog('Расчёт оплаты тренера',`<h3>${e(row.name)}</h3><p>${e(row.trainerName)} · ${e(date(row.snapshot.session.startsAt))}</p><p>Фактически посетило: ${row.participantCount}. Начислено: <strong>${e(money(row.amountMinor))}</strong></p><p>Тариф: ${e(row.snapshot.rate?.name||'—')}, версия ${e(row.snapshot.rate?.version||'—')}. Ревизия начисления ${row.entry.revision}.</p>${table(['Клиент','Отметка'],(row.snapshot.bookings||[]).map(booking=>[e([booking.person?.name?.firstName,booking.person?.name?.lastName].filter(Boolean).join(' ')||booking.name),e(statuses[booking.status]||booking.status)]))}<p>Основание: ${e(row.entry.reason||'Закрытие занятия')}</p><p class="muted">Изменение выполняется через исправление начисления в карточке тренировки.</p><details><summary>Полный снимок расчёта</summary><pre class="payroll-snapshot">${e(JSON.stringify(row.snapshot,null,2))}</pre></details>`);
  }
  async assignSession(session){
    try{await this.load(true);}catch(error){return this.studio.errorBox(error);}
    const requestKey=createOperationId();
    this.form('Назначить тренера',field('Тренер',`<select name="trainerId" required>${optionList(this.data.trainers.filter(row=>row.active),relationId(session,'trainer'))}</select>`),form=>this.studio.api.request('/studio/sessions/assign-trainer',{method:'POST',body:{classSessionId:session.id,trainerId:form.elements.trainerId.value,requestKey}}));
  }
  async closeSession(session){
    try{await this.load(true);}catch(error){return this.studio.errorBox(error);}
    const entries=this.data.trainerPayEntries.filter(row=>relationId(row,'classSession')===session.id&&row.entryType==='ACCRUAL').sort((a,b)=>b.revision-a.revision);
    const latest=entries[0];
    let snapshot;try{snapshot=latest?JSON.parse(latest.snapshot):null;}catch{return this.studio.errorBox(new Error('Снимок начисления повреждён. Требуется сверка в CRM.'));}
    let saved=latest?.state==='PENDING'?snapshot:null;
    const local=this.studio.pending.get('payroll');
    if(local&&local.classSessionId!==session.id)return this.studio.showDialog('Есть незавершённое начисление','<p>Сначала проверьте журнал исходной тренировки. Нельзя заменять ключ операции при неизвестном результате.</p>');
    let confirmed=local||null,preview=saved?{snapshot:saved,previewToken:latest.previewToken}:null;
    const requestKey=local?.requestKey||latest?.state==='PENDING'&&latest.requestKey||createOperationId();
    const previousEntryId=latest?.state==='PENDING'?(latest.previousEntryId||undefined):latest?.id;
    this.studio.showDialog(previousEntryId?'Исправить начисление':'Начислить оплату тренеру',`<div id="payroll-form">${field('Тренер',`<select name="trainerId" required>${optionList(this.data.trainers.filter(row=>row.active||row.id===(local?.trainerId||saved?.session?.trainer?.id)),local?.trainerId||saved?.session?.trainer?.id||relationId(session,'trainer'))}</select>`)}${field(previousEntryId?'Причина исправления (обязательно)':'Основание',`<textarea name="reason" maxlength="2000">${e(local?.reason||saved&&latest.reason||'')}</textarea>`)}${previousEntryId&&!saved?`<fieldset><legend>Фактическое посещение</legend>${(snapshot?.bookings||[]).filter(row=>['ATTENDED','NO_SHOW','LATE_CANCEL'].includes(row.status)).map(row=>field([row.person?.name?.firstName,row.person?.name?.lastName].filter(Boolean).join(' ')||row.name,`<select data-payroll-booking="${e(row.id)}">${['ATTENDED','NO_SHOW','LATE_CANCEL'].map(status=>`<option value="${status}" ${row.status===status?'selected':''}>${e(statuses[status])}</option>`).join('')}</select>`)).join('')}<p>Исправление присутствия не возвращает клиентскую оплату и не меняет списание пакета.</p></fieldset>`:''}<div id="payroll-preview"></div><p id="payroll-notice" role="status"></p><button type="button" id="payroll-submit" class="primary">${confirmed?'Проверить сохранённое начисление':preview?'Завершить начисление':'Проверить расчёт'}</button></div>`);
    const dialog=document.querySelector('#confirm'),form=dialog.querySelector('#payroll-form'),submit=dialog.querySelector('#payroll-submit');
    const paintPreview=()=>{const node=dialog.querySelector('#payroll-preview');node.innerHTML=preview?`<section class="note"><h3>Начислить ${e(money(analyticsMoney(preview.snapshot.amount)))}</h3><p>${e(preview.snapshot.session.trainer.name)} · ${preview.snapshot.participantCount} участников · тариф ${e(preview.snapshot.rate.name)}, версия ${preview.snapshot.rate.version}</p>${table(['Клиент','Отметка'],preview.snapshot.bookings.map(booking=>[e([booking.person?.name?.firstName,booking.person?.name?.lastName].filter(Boolean).join(' ')||booking.name),e(statuses[booking.status]||booking.status)]))}</section>`:'';};paintPreview();
    const correction=saved?.attendanceCorrections?.map(({bookingId,status})=>({bookingId,status}))||[];
    const build=()=>({classSessionId:session.id,trainerId:form.querySelector('[name=trainerId]').value,requestKey,...(previousEntryId?{previousEntryId}:{}),reason:form.querySelector('[name=reason]').value.trim(),attendanceCorrections:saved?correction:[...form.querySelectorAll('[data-payroll-booking]')].map(select=>({bookingId:select.dataset.payrollBooking,status:select.value}))});
    if(local||saved)form.querySelectorAll('input,select,textarea').forEach(control=>control.disabled=true);
    form.querySelectorAll('input,select,textarea').forEach(control=>control.addEventListener('input',()=>{preview=null;paintPreview();submit.textContent='Проверить расчёт';}));
    dialog.oncancel=event=>{if(this.studio.saving)event.preventDefault();};
    submit.onclick=async()=>{
      if(this.studio.saving)return;
      const body=confirmed||build();if(!body.trainerId||body.previousEntryId&&!body.reason)return this.studio.errorBox(new Error('Выберите тренера и укажите причину исправления.'),'#dialog-error');
      this.studio.saving=true;dialog.querySelectorAll('button').forEach(button=>button.disabled=true);
      try{
        if(!preview&&!confirmed){preview=await this.studio.api.request('/studio/compensation/close',{method:'POST',body:{...body,previewOnly:true}});paintPreview();submit.textContent='Подтвердить начисление';return;}
        confirmed=confirmed||{...body,previewOnly:false,previewToken:preview.previewToken};this.studio.pending.save('payroll',confirmed);
        const result=await this.studio.api.request('/studio/compensation/close',{method:'POST',body:confirmed});
        this.studio.pending.clear('payroll');
        try{await this.changed();}catch{this.studio.notify('Начисление сохранено. Обновите данные для проверки.');}
        form.innerHTML=`<p role="status">${result.duplicate?'Начисление уже сохранено.':'Начисление сохранено.'} ${e(money((BigInt(result.amountMicros)/10000n).toString()))}</p><p>Учтено в затратах и зарплате тренера. История доступна в разделе «Тренеры» и аналитике.</p>`;
      }catch(error){if(error.status===422||error.details?.code==='COMPENSATION_PREVIEW_CHANGED'){this.studio.pending.clear('payroll');confirmed=null;preview=null;submit.textContent='Проверить расчёт';paintPreview();}this.studio.errorBox(error,'#dialog-error');}
      finally{this.studio.saving=false;dialog.querySelectorAll('button').forEach(button=>button.disabled=false);}
    };
  }
}
