import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildAnalytics as buildRawAnalytics,analyticsMoney,analyticsPeriod,shiftAnalyticsMonth} from '../src/studio-analytics-domain.js';
const completeData = data => Object.assign(Object.fromEntries(['clients','products','packages','bookings','sessions','transactions','payments','expenses'].map(key=>[key,[]])),data);
const buildAnalytics = (data,options) => buildRawAnalytics(completeData(data),options);
const money = amount => ({amountMicros:amount,currencyCode:'RUB'});
const options={month:'2026-10',now:new Date('2026-11-02T00:00:00Z')};
test('деньги сохраняют копейки и большие суммы без float',()=>{
  assert.equal(analyticsMoney(money('1234560000')),'123456');
  assert.equal(analyticsMoney(money('90071992547409910000')),'9007199254740991');
  assert.equal(analyticsMoney(money(9007199254740992)),null);
  assert.equal(analyticsMoney(money('10001')),null);
  assert.equal(analyticsMoney({amountMicros:'10000',currencyCode:'USD'}),null);
});
test('Москва определяет границу месяца поступлений',()=>{
  const report=buildAnalytics({payments:[{status:'PAID',paidAt:'2026-09-30T21:00:00Z',amount:money('1234560000')},{status:'PAID',paidAt:'2026-10-31T21:00:00Z',amount:money('1000000')}]},options);
  assert.equal(report.metrics.receipts,'123456');
  assert.equal(report.metrics.earnedRevenue,null);
  assert.equal(report.metrics.expenses,'0');
});
test('неполный месяц сравнивается с теми же днями и ограничивается длиной прошлого месяца',()=>{
  assert.deepEqual(analyticsPeriod('2026-03',new Date('2026-03-30T21:30:00Z')),{start:'2026-03-01',end:'2026-04-01',comparisonStart:'2026-02-01',comparisonEnd:'2026-03-01',isPartial:true,label:'1–31 2026-03; предыдущий месяц за сопоставимые дни'});
  assert.equal(shiftAnalyticsMonth('2026-01',-1),'2025-12');
  assert.throws(()=>analyticsPeriod('2026-13'));
});
test('начисления всего месяца не смешиваются с выплатами',()=>{
  const data={expenses:[{id:'expense',accruedOn:'2026-10-01',paidOn:'2026-11-02',amount:money('1234560000'),category:'RENT',costType:'FIXED'}]};
  const report=buildAnalytics(data,{month:'2026-10',now:new Date('2026-10-15T00:00:00Z')});
  assert.equal(report.metrics.expenses,'123456');
  assert.equal(report.metrics.expensePayments,'0');
  assert.equal(report.expenseCategories[0].amount,'123456');
  assert.equal(buildAnalytics(data,{...options,month:'2026-11'}).metrics.expensePayments,'123456');
});
test('неизвестная сумма не становится нулём, накопленные возвраты не датируются оплатой',()=>{
  const report=buildAnalytics({payments:[{status:'PARTIALLY_REFUNDED',paidAt:'2026-10-02',amount:money('1000000'),refundAmount:money('100000')}],expenses:[{accruedOn:'2026-10-01',amount:null}]},options);
  assert.equal(report.metrics.receipts,'100');
  assert.equal(report.metrics.expenses,null);
  assert.equal(report.metrics.refunds,null);
  assert.equal(report.metrics.cashFlow,null);
  assert.deepEqual(report.balances,{prepayments:null,debts:null});
});
test('посещения, свободные места и когорты считаются по состоявшимся занятиям',()=>{
  const report=buildAnalytics({clients:[{id:'a',name:{firstName:'Анна'}},{id:'b',name:{firstName:'Вера'}}],sessions:[{id:'old',status:'COMPLETED',startsAt:'2026-09-15T10:00:00Z',capacity:4,sessionFormat:'GROUP_REFORMER'},{id:'group',status:'COMPLETED',startsAt:'2026-10-15T10:00:00Z',capacity:4,sessionFormat:'GROUP_REFORMER'}],bookings:[{id:'old-b',personId:'a',classSessionId:'old',status:'ATTENDED'},{id:'a',personId:'a',classSessionId:'group',status:'ATTENDED'},{id:'b',personId:'b',classSessionId:'group',status:'ATTENDED'},{id:'n',personId:'c',classSessionId:'group',status:'NO_SHOW'},{id:'cancel',personId:'d',classSessionId:'group',status:'LATE_CANCEL'}]},options);
  assert.equal(report.metrics.visits,2);
  assert.equal(report.metrics.occupancy,50);
  assert.equal(report.metrics.noShows,1);
  assert.equal(report.metrics.cancellations,1);
  assert.equal(report.formats[0].freeSeats,2);
  assert.deepEqual(report.clients.new.map(client=>client.id),['b']);
  assert.deepEqual(report.clients.retained.map(client=>client.id),['a']);
  assert.deepEqual(report.clients.returning,[]);
  assert.equal(report.series.length,6);
  assert.doesNotThrow(()=>JSON.stringify(report));
});
test('журнал резервов и списаний не удваивает выручку',()=>{
  const report=buildAnalytics({transactions:[{transactionType:'GRANT',visitDelta:8},{transactionType:'RESERVE',visitDelta:-1},{transactionType:'CONSUME',visitDelta:-1}],payments:[{status:'PAID',paidAt:'2026-10-02',amount:money('8000000000')}],packages:[{purchasePrice:money('8000000000'),visitsGranted:8}]},options);
  assert.equal(report.metrics.receipts,'800000');
  assert.equal(report.metrics.earnedRevenue,null);
});
test('оплаты и расходы без дат делают месячный итог неизвестным',()=>{
  const report=buildAnalytics({payments:[{status:'PAID',amount:money('1000000')}],expenses:[{amount:money('1000000')}]},options);
  assert.equal(report.metrics.receipts,null);
  assert.equal(report.metrics.expenses,null);
  assert.ok(report.availability.receipts);
});
test('в сопоставимом периоде не учитываются поздние оплаты прошлого месяца',()=>{
  const report=buildAnalytics({payments:[{status:'PAID',paidAt:'2026-09-10',amount:money('1000000')},{status:'PAID',paidAt:'2026-09-20',amount:money('2000000')}],expenses:[{accruedOn:'2026-09-01',amount:money('5000000'),costType:'FIXED'}]},{month:'2026-10',now:new Date('2026-10-15T00:00:00Z')});
  assert.equal(report.previous.receipts,'100');
  assert.equal(report.previous.expenses,'500');
});
test('неизвестный формат не добавляет групповую вместимость',()=>{
  const report=buildAnalytics({sessions:[{id:'unknown',sessionFormat:'FUTURE_FORMAT',status:'COMPLETED',capacity:100,startsAt:'2026-10-01T10:00:00Z'}]},options);
  assert.equal(report.metrics.sessions,1);
  assert.equal(report.metrics.occupancy,null);
  assert.equal(report.formats[0].capacity,null);
  assert.ok(report.availability.occupancy);
});
test('сохранившиеся, вернувшиеся и переставшие посещать клиенты разделены',()=>{
  const clients=['retained','returned','inactive','ancient','new'].map(id=>({id,name:id}));
  const rows=[['2026-08-01','returned'],['2026-08-02','ancient'],['2026-09-10','retained'],['2026-09-11','inactive'],['2026-10-05','retained'],['2026-10-06','returned'],['2026-10-07','new']];
  const report=buildAnalytics({clients,sessions:rows.map(([day],index)=>({id:String(index),status:'COMPLETED',sessionFormat:'PERSONAL_EQUIPMENT',capacity:1,startsAt:day+'T10:00:00Z'})),bookings:rows.map(([,personId],index)=>({id:String(index),personId,classSessionId:String(index),status:'ATTENDED'}))},options);
  assert.deepEqual(report.clients.retained.map(client=>client.id),['retained']);
  assert.deepEqual(report.clients.returning.map(client=>client.id),['returned']);
  assert.deepEqual(report.clients.inactive.map(client=>client.id),['inactive']);
  assert.deepEqual(report.clients.new.map(client=>client.id),['new']);
});
test('некорректное число начисления и невозможные даты блокируют итоги',()=>{
  const report=buildAnalytics({expenses:[{accruedOn:'2026-10-15',paidOn:'2026-02-30',amount:money('1000000'),category:'RENT'}],payments:[{paidAt:'2026-02-30T12:00:00Z',amount:money('1000000'),status:'PAID'}]},options);
  assert.equal(report.metrics.expenses,null);
  assert.equal(report.metrics.expensePayments,null);
  assert.equal(report.metrics.receipts,null);
  assert.equal(report.expenseCategories[0].amount,null);
});
test('неполные и отсутствующие источники не дают известных нулей',()=>{
  const report=buildRawAnalytics({payments:[],sessions:[],expenses:[],incompleteSources:['payments','expenses']},options);
  assert.equal(report.metrics.receipts,null);
  assert.equal(report.metrics.expenses,null);
  assert.equal(report.metrics.visits,null);
  assert.equal(report.metrics.activeClients,null);
  assert.equal(report.clients.available,false);
  assert.ok(report.missingSources.includes('bookings'));
});
test('оплаты и занятия позже текущего момента не попадают в текущий месяц',()=>{
  const report=buildAnalytics({payments:[{status:'PAID',paidAt:'2026-10-15T20:00:00Z',amount:money('1000000')}],sessions:[{id:'future',sessionFormat:'GROUP_REFORMER',status:'COMPLETED',capacity:4,startsAt:'2026-10-15T20:00:00Z'}],bookings:[{classSessionId:'future',personId:'a',status:'ATTENDED'}]},{month:'2026-10',now:new Date('2026-10-15T10:00:00Z')});
  assert.equal(report.metrics.receipts,'0');
  assert.equal(report.metrics.sessions,0);
  assert.equal(report.metrics.visits,0);
  assert.equal(report.clients.active.length,0);
});
