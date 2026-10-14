export const studioNav = [
  ['gelios/overview','Обзор','grid'], ['gelios/clients','Клиенты','users'],
  ['gelios/packages','Пакеты и оплата','wallet'], ['gelios/attendance','Внести тренировку','plus'],
  ['gelios/bookings','Посещения','calendar'], ['gelios/transactions','Журнал списаний','chart'],
];

export const studioPersonName = person => [person?.name?.firstName,person?.name?.lastName].filter(Boolean).join(' ') || 'Клиент без имени';
export const relationId = (record, relation) => record?.[relation + 'Id'] || record?.[relation]?.id;
export const currencyAmount = value => Number(value?.amountMicros || 0) / 1000000;
export const eligibleProducts = products => products.filter(product => product.isActive && ['GROUP_PACKAGE','PERSONAL'].includes(product.category));
export const personPackages = (packages, personId) => packages.filter(record => relationId(record,'person') === personId);
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
  clearAll() { for (const kind of ['client','payment','attendance']) this.clear(kind); }
}
