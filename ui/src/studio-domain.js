export const studioNav = [
  ['gelios/overview','Обзор','grid'], ['gelios/clients','Клиенты','users'],
  ['gelios/packages','Пакеты и оплата','wallet'], ['gelios/attendance','Внести тренировку','plus'],
  ['gelios/calendar','Календарь тренировок','calendar'],
  ['gelios/bookings','Посещения','calendar'], ['gelios/transactions','Журнал списаний','chart'],
  ['gelios/analytics','Аналитика','chart'],
];

export const studioPersonName = person => [person?.name?.firstName,person?.name?.lastName].filter(Boolean).join(' ') || 'Клиент без имени';
export const relationId = (record, relation) => record?.[relation + 'Id'] || record?.[relation]?.id;
export const currencyAmount = value => Number(value?.amountMicros || 0) / 1000000;
export const studioCrmError = (value, requestBody, crmPayload) => {
  const technical = String(value || 'Неизвестная ошибка CRM.');
  let payload = '';
  if (requestBody !== undefined) {
    try { payload = JSON.stringify(requestBody, null, 2); }
    catch { payload = 'Не удалось показать payload запроса.'; }
  }
  if (/person\.id\w*_unique/i.test(technical)) {
    return {
      title: 'Клиент уже есть в CRM',
      description: 'CRM обнаружила совпадение по одному из уникальных полей клиента. Обновите список клиентов и проверьте журнал операций.',
      technical,
      payload,
      crmPayload,
    };
  }
  return {
    title: 'CRM не выполнила операцию',
    description: 'CRM отклонила запрос. Проверьте данные и повторите попытку после исправления причины.',
    technical,
    payload,
    crmPayload,
  };
};
const productNameCollator = new Intl.Collator('ru', {sensitivity:'base'});
export const eligibleProducts = products => products
  .filter(product => product.isActive && ['GROUP_PACKAGE','PERSONAL'].includes(product.category))
  .sort((left,right) =>
    productNameCollator.compare(left.name || '', right.name || '') ||
    currencyAmount(left.price) - currencyAmount(right.price) ||
    String(left.id || '').localeCompare(String(right.id || ''))
  );
export const personPackages = (packages, personId) => packages.filter(record => relationId(record,'person') === personId);
export const calendarDate = value => new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow'}).format(new Date(value));
export const paymentStartOfMoscowDay = value => {
  const day = String(value || '').slice(0,10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const paidAt = new Date(`${day}T00:00:00+03:00`);
  return Number.isFinite(paidAt.getTime()) && calendarDate(paidAt) === day ? paidAt : null;
};
export const sessionParticipants = (bookings, sessionId) => bookings.filter(booking => relationId(booking,'classSession') === sessionId && ['BOOKED','CONFIRMED','ATTENDED'].includes(booking.status));
export const sessionCanAdd = (session, bookings, now = new Date()) => ['PLANNED','CONFIRMED'].includes(session.status) && new Date(session.startsAt) > now && sessionParticipants(bookings,session.id).length < Number(session.capacity);
export const sessionFormats = [['GROUP_REFORMER','Группа на реформере'],['INTRO_REFORMER','Intro на реформере'],['PERSONAL_EQUIPMENT','Персональное на оборудовании'],['SPLIT_EQUIPMENT','Сплит на оборудовании'],['MAT_PILATES','Пилатес на коврике'],['STRETCHING','Стрейчинг'],['TRX','TRX']];
export const sessionTimeState = (startsAt, durationMinutes, now = new Date()) => {
  const start=new Date(startsAt),end=new Date(start.getTime()+Number(durationMinutes)*60000);
  if(!Number.isFinite(start.getTime())||!Number.isInteger(Number(durationMinutes))||durationMinutes<1||durationMinutes>1440)throw new Error('Укажите корректное время и длительность 1–1440 минут.');
  return end<=now?'COMPLETED':start<=now?'CONFIRMED':'PLANNED';
};
export const sessionCreationPayload = (values, key, now = new Date()) => {
  const startsAt=new Date(values.startsAt+':00+03:00').toISOString();
  const durationMinutes=Number(values.durationMinutes),capacity=Number(values.capacity),status=sessionTimeState(startsAt,durationMinutes,now);
  const name=sessionFormats.find(([format])=>format===values.sessionFormat)?.[1];
  if(!name||!Number.isInteger(capacity)||capacity<1||capacity>100)throw new Error('Проверьте формат и вместимость.');
  if(status==='COMPLETED'&&values.pastConfirmed!=='on')throw new Error('Подтвердите, что прошедшая тренировка состоялась.');
  return {name,sessionFormat:values.sessionFormat,startsAt,durationMinutes,capacity,status,pastConfirmed:status==='COMPLETED',idempotencyKey:key};
};
export const calendarSessionLayout = (sessions, day) => {
  const start=new Date(day+'T07:00:00+03:00').getTime(),end=new Date(day+'T23:00:00+03:00').getTime();
  const intervals=sessions.map(session=>({session,start:Math.max(start,new Date(session.startsAt).getTime()),end:Math.min(end,new Date(session.endsAt).getTime())})).filter(interval=>interval.end>interval.start).sort((a,b)=>a.start-b.start||a.end-b.end);
  const lanes=[];
  for(const interval of intervals){
    let lane=lanes.findIndex(lastEnd=>lastEnd<=interval.start);
    if(lane<0)lane=lanes.length;
    lanes[lane]=interval.end;
    interval.lane=lane;
  }
  return intervals.map(interval=>({...interval,top:(interval.start-start)/60000/30*48,height:(interval.end-interval.start)/60000/30*48,laneCount:lanes.length}));
};
export const sessionMemberships = (packages, products, personId, session) => personPackages(packages,personId).filter(membership => {
  const product=products.find(product=>product.id===relationId(membership,'product'));
  const category=session.sessionFormat==='PERSONAL_EQUIPMENT'?'PERSONAL':'GROUP_PACKAGE';
  return session.sessionFormat!=='SPLIT_EQUIPMENT' && membership.status==='ACTIVE' && membership.visitsAvailable>0 && product?.category===category && product.sessionFormat===session.sessionFormat && membership.activatedAt && new Date(membership.activatedAt)<=new Date(session.startsAt) && (!membership.expiresOn || membership.expiresOn>=session.startsAt.slice(0,10)) && (session.status!=='COMPLETED' || product.durationMinutes===session.durationMinutes);
});
export const createOperationId = (cryptoProvider = globalThis.crypto) => {
  if (typeof cryptoProvider?.randomUUID === 'function') return cryptoProvider.randomUUID();
  if (typeof cryptoProvider?.getRandomValues !== 'function') throw new Error('Браузер не поддерживает безопасное создание ключа операции. Откройте UI через HTTPS или обновите браузер.');
  // HTTP LAN addresses lack randomUUID, but still support cryptographic random bytes.
  const bytes = cryptoProvider.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2,'0')).join('');
  return [hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
};
export const attendancePayload = (values, membership, product, key) => {
  const startsAt = new Date(values.startsAt);
  const duration = Number(product?.durationMinutes);
  if (!membership || relationId(membership,'person') !== values.personId) throw new Error('Выберите пакет этого клиента.');
  if (!Number.isInteger(duration) || duration <= 0 || !Number.isFinite(startsAt.getTime())) throw new Error('Проверьте время и длительность продукта.');
  const endsAt = new Date(startsAt.getTime() + duration * 60000);
  if (endsAt >= new Date()) throw new Error('Можно внести только полностью прошедшую тренировку.');
  return {personId:values.personId,membershipId:membership.id,startsAt:startsAt.toISOString(),endsAt:endsAt.toISOString(),reason:values.reason.trim(),source:values.source,...(values.sourceDetails?.trim()?{sourceDetails:values.sourceDetails.trim()}:{}),...(values.existingClassSessionId?{existingClassSessionId:values.existingClassSessionId}:{}),idempotencyKey:key};
};

export class PendingStudioOperation {
  constructor(storage = globalThis.sessionStorage) { this.storage = storage; }
  get(kind) {
    try { return JSON.parse(this.storage.getItem('gelios-pending-' + kind) || 'null'); }
    catch { return null; }
  }
  save(kind, body) { this.storage.setItem('gelios-pending-' + kind, JSON.stringify(body)); }
  clear(kind) { this.storage.removeItem('gelios-pending-' + kind); }
  clearAll() { for (const kind of ['client','payment','attendance','booking','cancellation','session']) this.clear(kind); }
}
