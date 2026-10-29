import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildClientBalances} from '../src/studio-analytics-balances.js';
const money = amount => ({currencyCode:'RUB',amountMicros:amount});
const entry = (id,type,delta,date) => ({id,membershipId:'package',transactionType:type,visitDelta:delta,occurredAt:date});
const fixture = () => ({clients:[{id:'inactive',name:{firstName:'Анна'}}],products:[{id:'product',name:'8 занятий',sessionFormat:'GROUP_REFORMER'}],packages:[{id:'package',personId:'inactive',productId:'product',status:'ACTIVE',soldAt:'2026-08-01T09:00:00Z',visitsGranted:8,visitsConsumed:2,visitsAvailable:5,visitsReserved:1,purchasePrice:money('8000000000')}],transactions:[entry('g','GRANT',8,'2026-08-01T09:00:00Z'),entry('c','CONSUME',-2,'2026-09-01T09:00:00Z'),entry('r','RESERVE',-1,'2026-09-02T09:00:00Z')],payments:[{id:'payment',membershipId:'package',status:'PAID',paidAt:'2026-08-01T09:00:00Z',amount:money('8000000000'),refundAmount:{amountMicros:null,currencyCode:'RUB'}}]});
const options = {month:'2026-10',now:new Date('2026-10-25T10:00:00Z')};
test('предоплаты клиентов без посещений переносятся между месяцами',()=>{
  const october=buildClientBalances(fixture(),options);
  const november=buildClientBalances(fixture(),{...options,month:'2026-11'});
  assert.equal(october.clients[0].id,'inactive');
  assert.equal(october.clients[0].openingVisits,6);
  assert.equal(october.totals.remainingVisits,6);
  assert.equal(october.totals.paidRemainingVisits,6);
  assert.equal(november.totals.remainingVisits,6);
  assert.equal(november.isFuture,true);
  assert.ok(november.availability.future);
  assert.equal(october.totals.moneyValueKopecks,'600000');
});
test('резерв не считается потреблением, release и consume списывают только один раз',()=>{
  const data=fixture();
  data.transactions.push(entry('release','RELEASE',1,'2026-10-03T10:00:00Z'),entry('consume','CONSUME',-1,'2026-10-03T10:00:01Z'));
  Object.assign(data.packages[0],{visitsConsumed:3,visitsReserved:0,visitsAvailable:5});
  const report=buildClientBalances(data,options);
  assert.equal(report.packages[0].ledgerVerified,true);
  assert.equal(report.totals.openingVisits,6);
  assert.equal(report.totals.consumedDuring,1);
  assert.equal(report.totals.remainingVisits,5);
  assert.equal(report.totals.reservedVisits,0);
});
test('исторический cutoff использует ledger и исключает будущие покупки',()=>{
  const data=fixture();
  data.packages.push({...data.packages[0],id:'later',soldAt:'2026-10-02T10:00:00Z'});
  const report=buildClientBalances(data,{...options,month:'2026-08'});
  assert.equal(report.packages.length,1);
  assert.equal(report.totals.openingVisits,0);
  assert.equal(report.totals.grantedDuring,8);
  assert.equal(report.totals.consumedDuring,0);
  assert.equal(report.totals.remainingVisits,8);
  assert.equal(report.totals.reservedVisits,0);
});
test('текущие counters видны без ledger, но история и money остаются неизвестными',()=>{
  const data=fixture(); data.transactions=[];
  const current=buildClientBalances(data,options);
  assert.equal(current.totals.remainingVisits,6);
  assert.equal(current.totals.openingVisits,null);
  assert.equal(current.totals.moneyValueKopecks,null);
  const past=buildClientBalances(data,{...options,month:'2026-09'});
  assert.equal(past.totals.remainingVisits,null);
});
test('неполные источники не превращаются в нулевые оплаченные остатки',()=>{
  const data=fixture(); data.incompleteSources=['payments','transactions'];
  const report=buildClientBalances(data,options);
  assert.equal(report.totals.remainingVisits,6);
  assert.equal(report.totals.paidRemainingVisits,null);
  assert.equal(report.totals.openingVisits,null);
  assert.equal(report.totals.moneyValueKopecks,null);
  assert.equal(report.totals.debtKopecks,null);
  assert.ok(report.availability.sources);
  assert.equal(buildClientBalances({},options).totals.remainingVisits,null);
});
test('истёкший и возвращённый пакет не выдаются за оплаченный доступный остаток',()=>{
  for(const status of ['EXPIRED','REFUNDED','CANCELLED']) {
    const data=fixture(); data.packages[0].status=status;
    const report=buildClientBalances(data,options);
    assert.equal(report.totals.availableVisits,0);
    assert.equal(report.totals.paidRemainingVisits,0);
    assert.equal(report.packages[0].currentStatus,status);
    if(status==='EXPIRED')assert.equal(report.totals.expiredVisits,6);
  }
});
test('замороженные посещения остаются обязательством, но недоступны для записи',()=>{
  const data=fixture(); data.packages[0].status='FROZEN';
  const report=buildClientBalances(data,options);
  assert.equal(report.totals.remainingVisits,6);
  assert.equal(report.totals.paidRemainingVisits,6);
  assert.equal(report.totals.frozenVisits,6);
  assert.equal(report.totals.availableVisits,0);
});
test('сверка журнала и корректировки защищают денежную оценку',()=>{
  const data=fixture(); data.packages[0].visitsAvailable=4;
  assert.equal(buildClientBalances(data,options).packages[0].ledgerVerified,false);
  const adjusted=fixture(); adjusted.transactions.push(entry('adjust','ADJUST',1,'2026-10-01T10:00:00Z')); adjusted.packages[0].visitsAvailable=6;
  const report=buildClientBalances(adjusted,options);
  assert.equal(report.packages[0].ledgerVerified,true);
  assert.equal(report.totals.adjustedDuring,1);
  assert.equal(report.totals.moneyValueKopecks,null);
});
test('накопленный возврат без даты не оценивается задним числом',()=>{
  const data=fixture(); data.payments[0].status='PARTIALLY_REFUNDED'; data.payments[0].refundAmount=money('1000000000');
  const report=buildClientBalances(data,{...options,month:'2026-08'});
  assert.equal(report.totals.remainingVisits,8);
  assert.equal(report.totals.paidRemainingVisits,null);
  assert.equal(report.totals.moneyValueKopecks,null);
});
test('будущий месяц не выдаёт известные остатки за историю будущего месяца',()=>{
  const data=fixture(); data.transactions.push(entry('future','CONSUME',-1,'2026-10-30T10:00:00Z'));
  const report=buildClientBalances(data,{...options,month:'2026-11'});
  assert.equal(report.asOf,options.now.toISOString());
  assert.equal(report.totals.remainingVisits,6);
  assert.equal(report.totals.openingVisits,null);
  assert.equal(report.totals.grantedDuring,null);
  assert.equal(report.totals.consumedDuring,null);
});
test('закрытые пакеты с возвратом не скрывают оценку действующих предоплат',()=>{
  const data=fixture();
  data.packages.push({...data.packages[0],id:'refunded',status:'REFUNDED',refundAmount:money('8000000000')});
  data.payments.push({...data.payments[0],id:'refunded-payment',membershipId:'refunded',status:'REFUNDED',refundAmount:money('8000000000')});
  const report=buildClientBalances(data,options);
  assert.equal(report.packages.find(row=>row.id==='refunded').paidRemainingVisits,0);
  assert.equal(report.packages.find(row=>row.id==='refunded').moneyValueKopecks,'0');
  assert.equal(report.totals.moneyValueKopecks,'600000');
  assert.equal(report.totals.knownMoneyValueKopecks,'600000');
  assert.equal(report.totals.unvaluedPackageCount,0);
});
test('нулевой остаток и неоплаченный пакет не создают неизвестную предоплату или долг',()=>{
  const data=fixture();
  data.packages.push({...data.packages[0],id:'empty',visitsAvailable:0,visitsReserved:0});
  data.packages.push({...data.packages[0],id:'unpaid',status:'PENDING_PAYMENT'});
  const report=buildClientBalances(data,options);
  assert.equal(report.packages.find(row=>row.id==='empty').moneyValueKopecks,'0');
  assert.equal(report.packages.find(row=>row.id==='unpaid').moneyValueKopecks,'0');
  assert.equal(report.packages.find(row=>row.id==='unpaid').availableVisits,0);
  assert.equal(report.packages.find(row=>row.id==='unpaid').debtKopecks,null);
  assert.equal(report.totals.moneyValueKopecks,'600000');
});
test('подтверждённая часть оценки доступна при положительных несверенных остатках',()=>{
  const data=fixture();
  data.packages.push({...data.packages[0],id:'unverified'});
  data.payments.push({...data.payments[0],id:'second-payment',membershipId:'unverified'});
  const report=buildClientBalances(data,options);
  assert.equal(report.totals.moneyValueKopecks,null);
  assert.equal(report.totals.knownMoneyValueKopecks,'600000');
  assert.equal(report.totals.unvaluedPackageCount,1);
  const missing=buildClientBalances({...fixture(),incompleteSources:['payments']},options);
  assert.equal(missing.totals.moneyValueKopecks,null);
  assert.equal(missing.totals.paidRemainingVisits,null);
  assert.equal(missing.totals.unvaluedPackageCount,1);
});
