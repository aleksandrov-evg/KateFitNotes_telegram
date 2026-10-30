import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildTrainerPayroll} from '../src/studio-payroll-domain.js';
import {buildAnalytics} from '../src/studio-analytics-domain.js';
import {parseMinorMoney} from '../src/studio-money.js';

const options={month:'2026-10',now:new Date('2026-11-03T00:00:00Z')};
const money=value=>({amountMicros:String(BigInt(value)*10000n),currencyCode:'RUB'});
const entry=({id='a',revision=1,trainerId='t1',amount='165000',state='POSTED',entryType='ACCRUAL',previousEntryId='',startsAt='2026-10-28T09:00:00Z',sessionId='s1',count=4}={})=>({id,revision,state,entryType,previousEntryId,trainerId,participantCount:count,classSessionId:sessionId,amount:money(entryType==='REVERSAL'?'-'+amount:amount),snapshot:JSON.stringify({schemaVersion:1,calculationBasis:'ATTENDED',session:{id:sessionId,name:'Группа',startsAt,trainer:{id:trainerId,name:'Тренер '+trainerId}},participantCount:count,amount:money(amount),attendedBookingIds:Array.from({length:count},(_,i)=>'b'+i),bookings:Array.from({length:4},(_,i)=>({id:'b'+i,status:i<count?'ATTENDED':'NO_SHOW'})),rate:{name:'Групповой',version:1}})});
const build=(entries,extra={})=>buildTrainerPayroll({trainerPayEntries:entries,...extra},options);

test('четыре произвольные ступени и нулевая сумма сохраняют копейки',()=>{
  const report=build(['70000','110050','130000','165000'].map((amount,i)=>entry({id:'e'+i,sessionId:'s'+i,amount,count:i+1})));
  assert.equal(report.amountMinor,'475050');assert.equal(report.sessionCount,4);assert.equal(report.participantCount,10);
  assert.equal(build([entry({amount:'0'})]).amountMinor,'0');
  assert.equal(parseMinorMoney(' 1650,50 '),'165050');assert.throws(()=>parseMinorMoney('-1'));assert.throws(()=>parseMinorMoney('1.001'));
});
test('сторно и новое начисление заменяют сумму и тренера, а не удваивают затраты',()=>{
  const original=entry();
  const report=build([original,entry({id:'r',revision:2,entryType:'REVERSAL',previousEntryId:'a'}),entry({id:'b',revision:2,trainerId:'t2',amount:'130000',previousEntryId:'a',count:3})],{trainers:[{id:'t2',name:'Анна',active:false}],sessions:[{id:'s1',trainerId:'later-mutable-trainer'}]});
  assert.equal(report.available,true);assert.equal(report.amountMinor,'130000');assert.equal(report.expenses.length,1);assert.equal(report.trainers.length,1);assert.equal(report.trainers[0].id,'t2');assert.equal(report.trainers[0].active,false);
  assert.equal(report.expenses[0].paidOn,null);assert.equal(report.expenses[0].amount.amountMicros,'1300000000');
});
test('незавершённое исправление сохраняет последнюю проведённую сумму и предупреждение',()=>{
  const report=build([entry(),entry({id:'r',revision:2,entryType:'REVERSAL',previousEntryId:'a'}),entry({id:'b',revision:2,state:'PENDING',previousEntryId:'a',amount:'130000',count:3})]);
  assert.equal(report.available,true);assert.equal(report.amountMinor,'165000');assert.deepEqual(report.pendingSessionIds,['s1']);assert.match(report.warnings.join(' '),/предварительный/);
  const pending=build([entry({state:'PENDING'})]);assert.equal(pending.amountMinor,'0');assert.deepEqual(pending.pendingSessionIds,['s1']);
});
test('месяц определяется по дате занятия в Москве, даже при позднем исправлении',()=>{
  assert.equal(build([entry({startsAt:'2026-09-30T21:00:00Z'})]).sessionCount,1);
  assert.equal(build([entry({startsAt:'2026-10-31T21:00:00Z'})]).sessionCount,0);
});
test('неполный или противоречивый журнал не показывает нулевую зарплату',()=>{
  const invalid=[entry({startsAt:'2026-02-30T09:00:00Z'}),entry({amount:'1',revision:2}),{...entry(),amount:money('1')},{...entry(),snapshot:'broken'},entry({entryType:'REVERSAL'}),{...entry(),snapshot:entry({count:3}).snapshot}];
  for(const row of invalid){const report=build([row]);assert.equal(report.available,false);assert.equal(report.amountMinor,null);}
  assert.equal(buildTrainerPayroll({},options).available,false);
  assert.equal(build([], {incompleteSources:['trainerPayEntries']}).available,false);
  assert.equal(build([entry(),entry()]).sessionCount,1);
  assert.equal(build([entry(),{...entry(),reason:'different'}]).available,false);
});
test('незакрытая проведённая группа отмечается, зарплата не становится выплатой',()=>{
  const data=Object.fromEntries(['clients','products','packages','bookings','sessions','transactions','payments','expenses','trainerPayEntries'].map(key=>[key,[]]));
  data.sessions=[{id:'unclosed',status:'COMPLETED',sessionFormat:'GROUP_REFORMER',startsAt:'2026-10-15T09:00:00Z'}];
  data.trainerPayEntries=[entry()];data.expenses=[{accruedOn:'2026-10-01',paidOn:'2026-10-02',amount:money('10000'),category:'TRAINERS',costType:'VARIABLE'}];
  const report=buildAnalytics(data,options);
  assert.equal(report.metrics.expenses,'175000');assert.equal(report.metrics.expensePayments,'10000');assert.equal(report.metrics.cashFlow,'-10000');
  assert.deepEqual(report.payroll.unclosedSessionIds,['unclosed']);assert.equal(report.payroll.expenses.length,1);
  assert.equal(buildAnalytics({...data,trainerPayEntries:undefined},options).metrics.expenses,null);
});
