import {relationId, studioPersonName} from './studio-domain.js';
import {analyticsMonth, analyticsMoney, shiftAnalyticsMonth} from './studio-analytics-domain.js';

const SOURCES = ['clients','packages','products','transactions','payments'];
const TRANSACTION_TYPES = ['GRANT','CONSUME','RESERVE','RELEASE','ADJUST','REFUND_VISIT','EXTEND'];
const TERMINAL_STATUSES = ['REFUNDED','CANCELLED','EXPIRED'];
const COUNT_FIELDS = ['openingVisits','grantedDuring','consumedDuring','adjustedDuring','remainingVisits','availableVisits','reservedVisits','expiredVisits','frozenVisits','paidRemainingVisits'];
const integer = value => Number.isSafeInteger(value) && value >= 0;
const timestamp = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const parsed = new Date(value);
  const calendarDay = new Date(value.slice(0,10)+'T12:00:00Z');
  return Number.isFinite(parsed.getTime()) && calendarDay.toISOString().slice(0,10) === value.slice(0,10) ? parsed.getTime() : null;
};
const dayTimestamp = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? timestamp(value+'T00:00:00+03:00') : null;
const ledgerBalance = entries => {
  let available = 0, reserved = 0, consumed = 0, granted = 0;
  for (const entry of [...entries].sort((left,right)=>timestamp(left.occurredAt)-timestamp(right.occurredAt) || Number(right.transactionType==='GRANT')-Number(left.transactionType==='GRANT') || String(left.id).localeCompare(String(right.id)))) {
    available += entry.visitDelta;
    if (entry.transactionType === 'GRANT') granted += entry.visitDelta;
    if (entry.transactionType === 'CONSUME') consumed -= entry.visitDelta;
    if (['RESERVE','RELEASE'].includes(entry.transactionType)) reserved -= entry.visitDelta;
    if (!integer(available) || !integer(reserved) || !integer(consumed) || !integer(granted)) return null;
  }
  return {available,reserved,consumed,granted,remaining:available+reserved};
};
const sum = (rows,field) => rows.some(row=>row[field]===null) ? null : rows.reduce((total,row)=>total+row[field],0);
const sumMoney = rows => rows.some(row=>row.moneyValueKopecks===null) ? null : rows.reduce((total,row)=>total+BigInt(row.moneyValueKopecks),0n).toString();
const totals = rows => ({...Object.fromEntries(COUNT_FIELDS.map(field=>[field,sum(rows,field)])),moneyValueKopecks:sumMoney(rows),knownMoneyValueKopecks:rows.reduce((total,row)=>total+BigInt(row.moneyValueKopecks ?? '0'),0n).toString(),unvaluedPackageCount:rows.filter(row=>row.moneyValueKopecks===null && (row.paidRemainingVisits===null || row.paidRemainingVisits>0)).length,debtKopecks:null});

// Current counters are useful even when imported packages have no complete transaction journal.
export const buildClientBalances = (input = {}, {month,now=new Date()} = {}) => {
  analyticsMonth(month);
  const monthStart = new Date(`${month}-01T00:00:00+03:00`).getTime();
  const nextMonthStart = new Date(`${shiftAnalyticsMonth(month,1)}-01T00:00:00+03:00`).getTime();
  const cutoff = Math.min(now.getTime(),nextMonthStart-1);
  const isFuture = monthStart > now.getTime();
  const isCurrent = now.getTime() >= monthStart && now.getTime() < nextMonthStart;
  const isSnapshot = isCurrent || isFuture;
  const missingSources = SOURCES.filter(key=>!Array.isArray(input[key]) || input.incompleteSources?.includes(key));
  const complete = key => !missingSources.includes(key);
  const data = Object.fromEntries(SOURCES.map(key=>[key,(Array.isArray(input[key]) ? input[key] : []).filter(row=>!row.deletedAt)]));
  const rows = [];
  for (const membership of data.packages) {
    const soldAt = timestamp(membership.soldAt);
    if (soldAt!==null && soldAt>cutoff) continue;
    const reasons = [];
    const ledger = data.transactions.filter(entry=>relationId(entry,'membership')===membership.id);
    const entriesValid = ledger.every(entry=>TRANSACTION_TYPES.includes(entry.transactionType) && Number.isSafeInteger(entry.visitDelta) && timestamp(entry.occurredAt)!==null && (entry.transactionType!=='EXTEND' || entry.visitDelta===0));
    const nowLedger = entriesValid ? ledgerBalance(ledger.filter(entry=>timestamp(entry.occurredAt)<=now.getTime())) : null;
    const countersValid = ['visitsAvailable','visitsReserved','visitsConsumed','visitsGranted'].every(field=>integer(membership[field]));
    const ledgerVerified = complete('transactions') && soldAt!==null && ledger.some(entry=>entry.transactionType==='GRANT') && entriesValid && nowLedger!==null && countersValid && nowLedger.available===membership.visitsAvailable && nowLedger.reserved===membership.visitsReserved && nowLedger.consumed===membership.visitsConsumed && nowLedger.granted===membership.visitsGranted;
    if (!ledgerVerified) reasons.push('Полный журнал не подтверждён текущими счётчиками пакета. Исторические остатки и движения недоступны.');
    const selectedLedger = ledgerVerified ? ledger.filter(entry=>timestamp(entry.occurredAt)<=cutoff) : [];
    const selectedBalance = ledgerVerified ? ledgerBalance(selectedLedger) : null;
    const openingBalance = ledgerVerified ? ledgerBalance(ledger.filter(entry=>timestamp(entry.occurredAt)<Math.min(monthStart,cutoff+1))) : null;
    const periodEntries = selectedLedger.filter(entry=>timestamp(entry.occurredAt)>=monthStart);
    const snapshot = isSnapshot && countersValid ? {available:membership.visitsAvailable,reserved:membership.visitsReserved,remaining:membership.visitsAvailable+membership.visitsReserved} : selectedBalance;
    const expiredOn = dayTimestamp(membership.expiresOn);
    const expired = isSnapshot ? membership.status==='EXPIRED' || (expiredOn!==null && cutoff>=expiredOn+86400000) : null;
    const terminal = isSnapshot && (TERMINAL_STATUSES.includes(membership.status) || expired);
    const remainingVisits = snapshot ? snapshot.remaining : null;
    const availableVisits = snapshot ? terminal || (isSnapshot && ['FROZEN','PENDING_PAYMENT'].includes(membership.status)) ? 0 : snapshot.available : null;
    const reservedVisits = snapshot ? terminal ? 0 : snapshot.reserved : null;
    if (!isSnapshot && TERMINAL_STATUSES.includes(membership.status)) reasons.push('Дата перехода пакета в текущий закрытый статус отсутствует. Остаток журнала не подтверждает право на занятия в прошлом.');
    const payments = data.payments.filter(payment=>relationId(payment,'membership')===membership.id);
    const price = analyticsMoney(membership.purchasePrice);
    const paymentHistoryValid = complete('payments') && payments.every(payment=>!['PAID','PARTIALLY_REFUNDED','REFUNDED'].includes(payment.status) || (timestamp(payment.paidAt)!==null && analyticsMoney(payment.amount)!==null));
    const refunds = payments.some(payment=>['PARTIALLY_REFUNDED','REFUNDED'].includes(payment.status) || (analyticsMoney(payment.refundAmount)!==null && BigInt(analyticsMoney(payment.refundAmount))!==0n)) || (analyticsMoney(membership.refundAmount)!==null && BigInt(analyticsMoney(membership.refundAmount))!==0n);
    const paidAmount = paymentHistoryValid ? payments.filter(payment=>['PAID','PARTIALLY_REFUNDED','REFUNDED'].includes(payment.status) && timestamp(payment.paidAt)<=cutoff).reduce((total,payment)=>total+BigInt(analyticsMoney(payment.amount)),0n) : null;
    const paid = paymentHistoryValid && price!==null && !refunds ? paidAmount>=BigInt(price) : null;
    if(paid===null)reasons.push('Оплата или датированная история возвратов не подтверждены. Оплаченный остаток недоступен.');
    const paidRemainingVisits = terminal || remainingVisits===0 || paid===false ? 0 : paid===null || remainingVisits===null ? null : remainingVisits;
    const grants = ledger.filter(entry=>entry.transactionType==='GRANT');
    const monetaryBasisReliable = ledgerVerified && grants.length===1 && grants[0].visitDelta>0 && !ledger.some(entry=>['ADJUST','REFUND_VISIT'].includes(entry.transactionType)) && !refunds && paid===true && price!==null;
    let moneyValueKopecks = paidRemainingVisits===0 ? '0' : null;
    if (monetaryBasisReliable && paidRemainingVisits!==null && paidRemainingVisits>0) {
      const numerator = BigInt(price)*BigInt(paidRemainingVisits), denominator=BigInt(grants[0].visitDelta);
      if(numerator%denominator===0n)moneyValueKopecks=(numerator/denominator).toString();
    }
    if(moneyValueKopecks===null)reasons.push('Денежная оценка остатка не подтверждена неизменяемой базой стоимости; это не сумма доступного возврата.');
    const personId = relationId(membership,'person') || null;
    const person = data.clients.find(client=>client.id===personId);
    const product = data.products.find(record=>record.id===relationId(membership,'product'));
    rows.push({id:membership.id,personId,ownerName:person ? studioPersonName(person) : personId ? 'Клиент недоступен' : relationId(membership,'pair') ? 'Общий пакет пары' : 'Владелец не указан',productName:product?.name || membership.name || 'Пакет',format:product?.sessionFormat || null,status:isSnapshot ? membership.status : null,currentStatus:membership.status,expiresOn:membership.expiresOn || null,openingVisits:isFuture ? null : openingBalance?.remaining ?? null,grantedDuring:ledgerVerified && !isFuture ? periodEntries.filter(entry=>entry.transactionType==='GRANT').reduce((total,entry)=>total+entry.visitDelta,0) : null,consumedDuring:ledgerVerified && !isFuture ? -periodEntries.filter(entry=>entry.transactionType==='CONSUME').reduce((total,entry)=>total+entry.visitDelta,0) : null,adjustedDuring:ledgerVerified && !isFuture ? periodEntries.filter(entry=>['ADJUST','REFUND_VISIT'].includes(entry.transactionType)).reduce((total,entry)=>total+entry.visitDelta,0) : null,remainingVisits,availableVisits,reservedVisits,expiredVisits:isSnapshot ? expired ? remainingVisits : 0 : null,frozenVisits:isSnapshot ? membership.status==='FROZEN' ? remainingVisits : 0 : null,paidRemainingVisits,paid,moneyValueKopecks,debtKopecks:null,moneyValueLabel:'Оценка остатка по цене покупки',ledgerVerified,reasons});
  }
  const clients = [...new Set(rows.map(row=>row.personId || `package:${row.id}`))].map(id=>{const packages=rows.filter(row=>(row.personId || `package:${row.id}`)===id);return {id,name:packages[0].ownerName,packages,...totals(packages),reasons:[...new Set(packages.flatMap(row=>row.reasons))]};});
  const availability = {debt:'В CRM нет журнала начислений и погашений денежного долга. Неоплаченный пакет не считается долгом за оказанные услуги.'};
  if(missingSources.length)availability.sources=`Не полностью загружены источники: ${missingSources.join(', ')}.`;
  if(!isSnapshot)availability.historicalStatus='История истечения, заморозки и закрытия пакетов отсутствует. Исторические остатки отражают журнал посещений, а не обещание возврата денег.';
  if(isFuture)availability.future='Показаны известные остатки на сегодня. Будущие посещения и оплаты неизвестны; это не фактический баланс будущего месяца.';
  const resultTotals = totals(rows);
  if(!complete('packages'))for(const field of [...COUNT_FIELDS,'moneyValueKopecks','unvaluedPackageCount'])resultTotals[field]=null;
  return {month,asOf:new Date(cutoff).toISOString(),isCurrent,isFuture,clients,packages:rows,totals:resultTotals,missingSources,availability,warnings:[...Object.values(availability),'Остатки включают все пакеты клиентов независимо от посещений в выбранном месяце. Резерв входит в остаток и показывается отдельно. Денежная оценка не является доступной суммой возврата.']};
};
