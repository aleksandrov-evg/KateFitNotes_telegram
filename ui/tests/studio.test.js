import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Api} from '../src/api.js';
import {StudioUi} from '../src/studio.js';
import {studioNav,studioPersonName,relationId,currencyAmount,eligibleProducts,personPackages,attendancePayload,PendingStudioOperation} from '../src/studio-domain.js';

const storage=()=>{const values=new Map();return {getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};};
const json=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});

test('Gelios использует собственную навигацию и UUID, не числовые id Terfit',()=>{
  assert.ok(studioNav.every(([id])=>id.startsWith('gelios/')));
  assert.equal(studioPersonName({name:{firstName:'Катя',lastName:'Иванова'}}),'Катя Иванова');
  assert.equal(relationId({personId:'uuid'},'person'),'uuid');
  assert.equal(relationId({person:{id:'uuid'}},'person'),'uuid');
  assert.equal(currencyAmount({amountMicros:1500000000}),1500);
  assert.deepEqual(personPackages([{id:'one',personId:'uuid'},{id:'two',personId:'other'}],'uuid').map(item=>item.id),['one']);
});
test('продажа предлагает только активные групповые и персональные пакеты',()=>{
  assert.deepEqual(eligibleProducts([{id:'one',category:'GROUP_PACKAGE',isActive:true},{category:'SPLIT',isActive:true},{category:'PERSONAL',isActive:false}]).map(item=>item.id),['one']);
});
test('прошедшая тренировка получает длительность из продукта и тот же ключ',()=>{
  const body=attendancePayload({personId:'person',startsAt:'2020-01-01T10:00:00+03:00',reason:' Журнал ',source:'ADMIN'}, {id:'package',personId:'person'},{durationMinutes:55},'stable-key');
  assert.equal(body.startsAt,'2020-01-01T07:00:00.000Z');
  assert.equal(body.endsAt,'2020-01-01T07:55:00.000Z');
  assert.equal(body.idempotencyKey,'stable-key');
  assert.equal(body.reason,'Журнал');
  assert.equal(body.recordedBy,undefined);
  assert.equal(attendancePayload({personId:'person',startsAt:'2020-01-01T10:00:00Z',reason:'Журнал',source:'ADMIN',existingClassSessionId:'session'}, {id:'package',personId:'person'}, {durationMinutes:55}, 'key').existingClassSessionId,'session');
  assert.throws(()=>attendancePayload({personId:'other'}, {personId:'person'}, {durationMinutes:55},'key'),/этого клиента/);
});
test('незавершённая операция переживает перезагрузку и очищается явно',()=>{
  const store=storage(),pending=new PendingStudioOperation(store),body={idempotencyKey:'same',amount:100};
  pending.save('payment',body);
  assert.deepEqual(new PendingStudioOperation(store).get('payment'),body);
  pending.clearAll();assert.equal(pending.get('payment'),null);
});
test('выход очищает загруженные данные, но сохраняет ключ незавершённой оплаты',()=>{
  const studio=new StudioUi({});
  studio.pending=new PendingStudioOperation(storage());
  studio.pending.save('payment',{idempotencyKey:'stable'});
  studio.data={clients:[{id:'person'}]};
  studio.reset();
  assert.equal(studio.data,null);
  assert.equal(studio.pending.get('payment').idempotencyKey,'stable');
});
test('списки CRM загружаются по курсору, а не offset Terfit',async()=>{
  const paths=[];
  const api=new Api({storage:storage(),fetcher:async path=>{paths.push(path);return json(paths.length===1?{items:[{id:'one'}],next_cursor:'next'}:{items:[{id:'two'}],next_cursor:null});}});
  assert.deepEqual(await api.studioRecords('clients'),[{id:'one'},{id:'two'}]);
  assert.equal(paths[1],'/api/v1/studio/records/clients?cursor=next');
});
test('повторяющийся курсор останавливает загрузку CRM',async()=>{
  const api=new Api({storage:storage(),fetcher:async()=>json({items:[],next_cursor:'same'})});
  await assert.rejects(api.studioRecords('clients'),/повторила страницу/);
});
test('доменная ошибка и неизвестный результат не заменяются общим сообщением',async()=>{
  const api=new Api({storage:storage(),fetcher:async()=>new Response(JSON.stringify({detail:{code:'INSUFFICIENT_BALANCE',message:'Нет посещений'}}),{status:409})});
  await assert.rejects(api.request('/studio/attendance/preview',{method:'POST',body:{}}),/Нет посещений/);
  api.fetcher=async()=>new Response(JSON.stringify({detail:'Результат неизвестен. Используйте прежний ключ.'}),{status:502});
  await assert.rejects(api.request('/studio/attendance/record-past',{method:'POST',body:{}}),/прежний ключ/);
});
