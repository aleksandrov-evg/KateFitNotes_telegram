import {relationId, calendarDate} from './studio-domain.js';

export const analyticsMonth = value => {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(value || '')) throw new Error('Укажите месяц в формате ГГГГ-ММ.');
  return value;
};
export const shiftAnalyticsMonth = (month, offset) => {
  analyticsMonth(month);
  const [year, number] = month.split('-').map(Number);
  return new Date(Date.UTC(year, number - 1 + offset, 1)).toISOString().slice(0, 7);
};
const daysInMonth = month => Number(new Date(Date.UTC(Number(month.slice(0,4)), Number(month.slice(5)), 0)).getUTCDate());
const dayAfter = day => new Date(new Date(`${day}T12:00:00Z`).getTime() + 86400000).toISOString().slice(0,10);
export const analyticsPeriod = (month, now = new Date()) => {
  analyticsMonth(month);
  const today = calendarDate(now), previous = shiftAnalyticsMonth(month, -1);
  const isPartial = today.slice(0,7) === month;
  const end = isPartial ? dayAfter(today) : `${shiftAnalyticsMonth(month,1)}-01`;
  const comparisonEnd = isPartial ? dayAfter(`${previous}-${String(Math.min(Number(today.slice(8)), daysInMonth(previous))).padStart(2,'0')}`) : `${month}-01`;
  return {start:`${month}-01`,end,comparisonStart:`${previous}-01`,comparisonEnd,isPartial,label:isPartial ? `1–${Number(today.slice(8))} ${month}; предыдущий месяц за сопоставимые дни` : month};
};
export const analyticsMoney = value => {
  if (!value || value.currencyCode !== 'RUB') return null;
  const raw = value.amountMicros;
  if ((typeof raw === 'number' && !Number.isSafeInteger(raw)) || !/^-?\d+$/.test(String(raw))) return null;
  const micros = BigInt(raw);
  return micros % 10000n === 0n ? (micros / 10000n).toString() : null;
};
const dated = value => {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const parsed = new Date(`${value}T12:00:00Z`);
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0,10) === value ? value : null;
  }
  if (!/^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  if (!dated(String(value).slice(0,10))) return null;
  return Number.isFinite(new Date(value).getTime()) ? calendarDate(value) : null;
};
const inside = (value, start, end) => { const day = dated(value); return day !== null && day >= start && day < end; };
const sumMoney = (records, field) => {
  let total = 0n;
  for (const record of records) { const amount = analyticsMoney(record[field]); if (amount === null) return null; total += BigInt(amount); }
  return total.toString();
};
const ratio = (numerator, denominator) => denominator ? numerator / denominator * 100 : null;
const GROUP_FORMATS = ['GROUP_REFORMER','MAT_PILATES','STRETCHING','TRX'];
const KNOWN_FORMATS = [...GROUP_FORMATS,'PERSONAL_EQUIPMENT','SPLIT_EQUIPMENT','INTRO_REFORMER'];
const groupSessions = session => GROUP_FORMATS.includes(session.sessionFormat);
const available = records => records.filter(record => !record.deletedAt);
const nameOf = record => [record?.name?.firstName,record?.name?.lastName].filter(Boolean).join(' ') || (typeof record?.name === 'string' ? record.name : 'Клиент без имени');
const nullMoney = {earnedRevenue:null,profit:null,margin:null,averageVisitRevenue:null,revenuePerClient:null};

// Monthly expense accruals are recorded as a month, so even a partial month includes the entire recorded amount.
export const buildAnalytics = (input = {}, {month, now = new Date()} = {}) => {
  const period = analyticsPeriod(month, now);
  const sources = ['clients','products','packages','bookings','sessions','transactions','payments','expenses'];
  const missingSources = sources.filter(key => !Array.isArray(input[key]) || input.incompleteSources?.includes(key));
  const hasSource = key => !missingSources.includes(key);
  const data = Object.fromEntries(['clients','products','packages','bookings','sessions','transactions','payments','expenses'].map(key => [key,available(Array.isArray(input[key]) ? input[key] : [])]));
  const sessionsById = new Map(data.sessions.map(session => [session.id,session]));
  const bookingDate = booking => sessionsById.get(relationId(booking,'classSession'))?.startsAt;
  const occurred = value => dated(value) && (/^\d{4}-\d{2}-\d{2}$/.test(value) ? dated(value) <= calendarDate(now) : new Date(value) <= now);
  const completedBookings = data.bookings.filter(booking => sessionsById.get(relationId(booking,'classSession'))?.status === 'COMPLETED' && occurred(bookingDate(booking)));
  const hasInvalidBookingDate = data.bookings.some(booking => !dated(bookingDate(booking)));
  const hasInvalidSessionDate = data.sessions.some(session => session.status === 'COMPLETED' && !dated(session.startsAt));
  const hasInvalidPaidDate = data.expenses.some(expense => expense.paidOn && !dated(expense.paidOn));
  const hasUndatedPayment = data.payments.some(payment => ['PAID','PARTIALLY_REFUNDED','REFUNDED'].includes(payment.status) && !dated(payment.paidAt));
  const hasUndatedExpense = data.expenses.some(expense => !dated(expense.accruedOn) || String(expense.accruedOn).slice(8,10) !== '01');
  const hasUndatedRefund = data.payments.some(payment => ['REFUNDED','PARTIALLY_REFUNDED'].includes(payment.status) || (analyticsMoney(payment.refundAmount) !== null && BigInt(analyticsMoney(payment.refundAmount)) > 0n));
  const metricsFor = (start,end) => {
    const payments = data.payments.filter(payment => ['PAID','PARTIALLY_REFUNDED','REFUNDED'].includes(payment.status) && occurred(payment.paidAt) && inside(payment.paidAt,start,end));
    const expenses = data.expenses.filter(expense => String(expense.accruedOn || '').slice(0,7) === start.slice(0,7));
    const paidExpenses = data.expenses.filter(expense => occurred(expense.paidOn) && inside(expense.paidOn,start,end));
    const sessions = data.sessions.filter(session => session.status === 'COMPLETED' && occurred(session.startsAt) && inside(session.startsAt,start,end));
    const bookings = data.bookings.filter(booking => occurred(bookingDate(booking)) && inside(bookingDate(booking),start,end));
    const visits = bookings.filter(booking => booking.status === 'ATTENDED' && sessionsById.get(relationId(booking,'classSession'))?.status === 'COMPLETED');
    const groups = sessions.filter(groupSessions);
    const capacityValid = sessions.every(session => KNOWN_FORMATS.includes(session.sessionFormat)) && groups.every(session => Number.isInteger(session.capacity) && session.capacity > 0);
    const capacity = groups.reduce((total,session) => total + Number(session.capacity || 0),0);
    const groupIds = new Set(groups.map(session => session.id));
    const groupVisits = visits.filter(booking => groupIds.has(relationId(booking,'classSession'))).length;
    const receipts = !hasSource('payments') || hasUndatedPayment ? null : sumMoney(payments,'amount'), expensePayments = !hasSource('expenses') || hasInvalidPaidDate ? null : sumMoney(paidExpenses,'amount');
    const refunds = !hasSource('payments') || hasUndatedRefund ? null : '0';
    const attendanceAvailable = hasSource('bookings') && hasSource('sessions') && !hasInvalidBookingDate && !hasInvalidSessionDate;
    return {...nullMoney,receipts,refunds,expenses:!hasSource('expenses') || hasUndatedExpense ? null : sumMoney(expenses,'amount'),expensePayments,cashFlow:receipts !== null && expensePayments !== null && refunds !== null ? (BigInt(receipts)-BigInt(expensePayments)-BigInt(refunds)).toString() : null,visits:attendanceAvailable ? visits.length : null,sessions:hasSource('sessions') && !hasInvalidSessionDate ? sessions.length : null,activeClients:attendanceAvailable ? new Set(visits.map(booking=>relationId(booking,'person')).filter(Boolean)).size : null,occupancy:attendanceAvailable && capacityValid ? ratio(groupVisits,capacity) : null,cancellations:attendanceAvailable ? bookings.filter(booking=>['CANCELLED_IN_TIME','LATE_CANCEL','CANCELLED_BY_STUDIO'].includes(booking.status)).length : null,noShows:attendanceAvailable ? bookings.filter(booking=>booking.status==='NO_SHOW').length : null};
  };
  const attendanceAvailable = hasSource('bookings') && hasSource('sessions') && !hasInvalidBookingDate && !hasInvalidSessionDate;
  const clientsAvailable = attendanceAvailable && hasSource('clients');
  const metrics = metricsFor(period.start,period.end);
  const currentSessions = data.sessions.filter(session=>session.status==='COMPLETED' && occurred(session.startsAt) && inside(session.startsAt,period.start,period.end));
  const currentBookings = completedBookings.filter(booking=>inside(bookingDate(booking),period.start,period.end));
  const formats = [...new Set(currentSessions.map(session=>session.sessionFormat))].map(format => {
    const sessions = currentSessions.filter(session=>session.sessionFormat===format), ids=new Set(sessions.map(session=>session.id));
    const visits=attendanceAvailable ? currentBookings.filter(booking=>booking.status==='ATTENDED' && ids.has(relationId(booking,'classSession'))).length : null;
    const capacity=KNOWN_FORMATS.includes(format) && sessions.every(session=>Number.isInteger(session.capacity)&&session.capacity>0) ? sessions.reduce((total,session)=>total+session.capacity,0) : null;
    return {format,sessions:sessions.length,visits,capacity,freeSeats:capacity===null || visits===null ? null : Math.max(0,capacity-visits),occupancy:capacity===null || visits===null ? null : ratio(visits,capacity),revenue:null};
  });
  const expenses=data.expenses.filter(expense=>String(expense.accruedOn || '').slice(0,7)===month);
  const breakdown = field => [...new Set(expenses.map(expense=>expense[field] || 'UNKNOWN'))].map(value=>{const records=expenses.filter(expense=>(expense[field]||'UNKNOWN')===value);return {[field]:value,amount:hasUndatedExpense || !hasSource('expenses') ? null : sumMoney(records,'amount'),count:records.length};});
  const firstAttendance=new Map();
  for(const booking of completedBookings.filter(booking=>booking.status==='ATTENDED')) {const personId=relationId(booking,'person'),day=dated(bookingDate(booking));if(personId&&day&&(!firstAttendance.has(personId)||day<firstAttendance.get(personId)))firstAttendance.set(personId,day);}
  const previousFullStart = `${shiftAnalyticsMonth(month,-1)}-01`;
  const previousAttended = completedBookings.filter(booking=>booking.status==='ATTENDED' && inside(bookingDate(booking),previousFullStart,period.start));
  const previousFullIds = new Set(previousAttended.map(booking=>relationId(booking,'person')).filter(Boolean));
  const previousComparableIds = new Set(previousAttended.filter(booking=>inside(bookingDate(booking),period.comparisonStart,period.comparisonEnd)).map(booking=>relationId(booking,'person')).filter(Boolean));
  const activeIds=new Set(currentBookings.filter(booking=>booking.status==='ATTENDED').map(booking=>relationId(booking,'person')).filter(Boolean));
  const active=[...activeIds].map(id=>({id,name:nameOf(data.clients.find(client=>client.id===id)),visits:currentBookings.filter(booking=>booking.status==='ATTENDED'&&relationId(booking,'person')===id).length,firstVisit:firstAttendance.get(id)}));
  const availability={earnedRevenue:'В CRM нет денежной стоимости каждого списания и неизменяемой истории стоимости посещения. Доход по занятиям пока недоступен.',profit:'Для расчёта прибыли нужен подтверждённый доход по проведённым занятиям.',margin:'Для расчёта рентабельности нужен подтверждённый доход.',prepayments:'Исторический остаток предоплат нельзя восстановить из текущих остатков пакетов.',debts:'Не хватает истории начислений и погашений задолженности на конец месяца.'};
  if(missingSources.length)availability.sources=`Не полностью загружены источники: ${missingSources.join(', ')}. Связанные показатели недоступны.`;
  if(currentSessions.some(session=>!KNOWN_FORMATS.includes(session.sessionFormat)))availability.occupancy='Есть занятия с неизвестным форматом. Групповая загрузка недоступна.';
  if(hasInvalidBookingDate || hasInvalidSessionDate)availability.attendance='Есть занятия или записи без корректной даты. Итоги посещений неполны.';
  if(hasInvalidPaidDate)availability.expensePayments='Есть расходы с некорректной датой выплаты. Итоги выплат недоступны.';
  if(hasUndatedPayment)availability.receipts='Есть проведённые оплаты без даты. Поступления по месяцам нельзя определить достоверно.';
  if(hasUndatedExpense)availability.expenses='Есть расходы без корректного месяца начисления (первое число месяца). Итоги начисленных расходов неполны.';
  if(hasUndatedRefund)availability.refunds='CRM хранит накопленную сумму возврата без даты. Возвраты и денежный поток по месяцам недоступны.';
  const warnings=[...Object.values(availability),'Расходы включают только внесённые записи. Начисления учитываются за весь месяц без пропорционального деления, в том числе в текущем неполном месяце.','Когорты клиентов определяются по первому посещению в доступной истории CRM.'];
  if(data.expenses.some(expense=>!expense.accruedOn||String(expense.accruedOn).slice(8,10)!=='01'))warnings.push('Есть расходы без корректного месяца начисления (первое число месяца). Проверьте записи CRM.');
  return {month,period,metrics,previous:metricsFor(period.comparisonStart,period.comparisonEnd),series:Array.from({length:6},(_,index)=>{const seriesMonth=shiftAnalyticsMonth(month,index-5);const bounds=analyticsPeriod(seriesMonth,now);return {month:seriesMonth,...metricsFor(bounds.start,bounds.end)};}),formats,expenseCategories:breakdown('category'),expenseTypes:breakdown('costType'),clients:{available:clientsAvailable,active,new:active.filter(client=>client.firstVisit>=period.start),returning:active.filter(client=>client.firstVisit<previousFullStart && !previousFullIds.has(client.id)),retained:active.filter(client=>previousFullIds.has(client.id)),inactive:data.clients.filter(client=>!activeIds.has(client.id)&&previousComparableIds.has(client.id)).map(client=>({id:client.id,name:nameOf(client),firstVisit:firstAttendance.get(client.id)}))},balances:{prepayments:null,debts:null},expenses,warnings,availability,missingSources};
};
