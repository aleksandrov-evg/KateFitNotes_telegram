export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Moscow'}).format(new Date());
export function addDays(date, count) {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + count);
  return d.toISOString().slice(0,10);
}
export function weekStart(date) {
  const day = new Date(`${date}T12:00:00Z`).getUTCDay();
  return addDays(date, -(day + 6) % 7);
}
export const weekDays = date => Array.from({length:7}, (_, i) => addDays(weekStart(date), i));
export const formatDate = (date, options = {day:'numeric',month:'long'}) => new Intl.DateTimeFormat('ru-RU', {...options,timeZone:'UTC'}).format(new Date(`${date}T12:00:00Z`));
export const money = value => new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',minimumFractionDigits:0,maximumFractionDigits:2}).format(value ?? 0);
export const clientName = client => [client?.name,client?.surname].filter(x => x && x !== 'None').join(' ') || `Клиент №${client?.id ?? '—'}`;
export const phoneLabel = phone => `+7 ${String(phone).padStart(10,'0').replace(/(\d{3})(\d{3})(\d{2})(\d{2})/, '$1 $2-$3-$4')}`;
export function normalizePhone(value) {
  const phone = value.replace(/[\s()\-]/g,'');
  if (!/^(?:\+7|7|8)\d{10}$/.test(phone)) throw new Error('Введите телефон: +7 и 10 цифр, либо 11 цифр с 7 или 8.');
  return phone;
}
export function integer(value, label, minimum = 0) {
  if (!/^\d+$/.test(String(value)) || !Number.isSafeInteger(Number(value)) || Number(value) < minimum) throw new Error(`${label}: введите целое число от ${minimum}.`);
  return Number(value);
}
export const activePackages = (packages, client, type) => packages.filter(p => !p.is_complete && p.client_id === Number(client) && (type === undefined || p.type_train_id === Number(type)));
export function priceHint(packages, bookings, client, type) {
  const active = activePackages(packages,client,type);
  if (active.length > 1) return {blocked:true,message:'Найдено несколько открытых пакетов этого типа. Сначала необходимо исправить пакеты.'};
  if (active.length === 1) return {package:active[0], price:active[0].price_per_train};
  const last = bookings.filter(b => b.client === Number(client) && b.type_train_id === Number(type) && b.price != null).sort((a,b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))[0];
  return {price:last?.price};
}
export const slots = Array.from({length:17}, (_,i) => `${String(i+7).padStart(2,'0')}:00`);
export function bookingPayload(draft, group, hint) {
  if (!draft.type) throw new Error('Выберите тип тренировки.');
  if (!draft.date || !draft.time) throw new Error('Выберите дату и свободное время.');
  if (hint?.blocked) throw new Error(hint.message);
  const data = {type_train_id:integer(draft.type,'Тип',1), date:draft.date,time:draft.time,price:!group && hint?.package ? null : integer(draft.price,'Цена')};
  if (group) {
    if (!draft.clients.length) throw new Error('Выберите хотя бы одного участника.');
    data.client_ids = [...new Set(draft.clients.map(Number))];
  } else data.client_id = integer(draft.client,'Клиент',1);
  return data;
}
