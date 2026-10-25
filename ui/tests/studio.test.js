import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Api} from '../src/api.js';
import {StudioUi} from '../src/studio.js';
import {sessionCancellationPath,sessionPaymentProducts,sessionPaymentContext,sessionPaymentMatches,studioNav,studioPersonName,relationId,currencyAmount,eligibleProducts,personPackages,createOperationId,attendancePayload,PendingStudioOperation,calendarDate,paymentStartOfMoscowDay,studioCrmError,sessionParticipants,sessionCanAdd,sessionMemberships,sessionTimeState,sessionCreationPayload,calendarSessionLayout} from '../src/studio-domain.js';

const storage=()=>{const values=new Map();return {getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};};
const json=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});

test('ключ операции работает на HTTP без crypto.randomUUID и остаётся UUID v4',()=>{
  const cryptoProvider={getRandomValues:bytes=>globalThis.crypto.getRandomValues(bytes)};
  const keys=Array.from({length:1000},()=>createOperationId(cryptoProvider));
  assert.equal(new Set(keys).size,1000);
  assert.ok(keys.every(key=>/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(key)));
});
test('генерация использует native UUID либо явно сообщает об отсутствии криптографии',()=>{
  assert.equal(createOperationId({randomUUID:()=> 'native-id'}),'native-id');
  assert.throws(()=>createOperationId({}),/HTTPS/);
});
test('календарь группирует по Москве и считает только активных участников',()=>{
  assert.equal(calendarDate('2026-10-14T22:00:00Z'),'2026-10-15');
  const session={id:'session',status:'PLANNED',startsAt:'2099-01-01T10:00:00Z',capacity:1};
  const bookings=[{classSessionId:'session',status:'CANCELLED_BY_STUDIO'},{classSessionId:'other',status:'BOOKED'}];
  assert.equal(sessionParticipants(bookings,'session').length,0);
  assert.equal(sessionCanAdd(session,bookings),true);
  assert.equal(sessionCanAdd(session,[{classSessionId:'session',status:'BOOKED'}]),false);
  assert.equal(sessionCanAdd({...session,status:'COMPLETED'},[]),false);
  assert.equal(sessionCanAdd({...session,startsAt:'2020-01-01T10:00:00Z'},[]),false);
});
test('оплата пакета начинается в 00:00 по Москве выбранной даты',()=>{
  assert.equal(paymentStartOfMoscowDay('2026-10-16T17:25').toISOString(),'2026-10-15T21:00:00.000Z');
  assert.equal(paymentStartOfMoscowDay('2026-10-16').toISOString(),'2026-10-15T21:00:00.000Z');
  assert.equal(paymentStartOfMoscowDay('not-a-date'),null);
});
test('ошибка дубликата клиента отображается понятным текстом',()=>{
  const view=studioCrmError(
    'A duplicate entry was detected: unique constraint person.IDX_UNIQUE_42 was violated',
    {firstName:'Катя',phone:'9210000000'},
    {name:{firstName:'Катя'},phones:{primaryPhoneNumber:'9210000000'}},
  );
  assert.equal(view.title,'Клиент уже есть в CRM');
  assert.match(view.description,/проверьте журнал/i);
  assert.match(view.payload,/"firstName": "Катя"/);
  assert.equal(view.crmPayload.phones.primaryPhoneNumber,'9210000000');
});
test('карточка предлагает принадлежащий клиенту пакет подходящего формата и даты',()=>{
  const session={sessionFormat:'GROUP_REFORMER',startsAt:'2026-10-15T10:00:00Z'};
  const valid={id:'valid',personId:'person',productId:'product',status:'ACTIVE',visitsAvailable:1,activatedAt:'2026-10-01T10:00:00Z',expiresOn:'2026-10-31'};
  const packages=[valid,{...valid,id:'other',personId:'other'},{...valid,id:'expired',expiresOn:'2026-10-14'},{...valid,id:'empty',visitsAvailable:0}];
  assert.deepEqual(sessionMemberships(packages,[{id:'product',category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER'}],'person',session).map(item=>item.id),['valid']);
});
test('групповые и персональные пакеты не смешиваются, для прошлого совпадает длительность',()=>{
  const membership={id:'package',personId:'person',productId:'product',status:'ACTIVE',visitsAvailable:1,activatedAt:'2020-01-01T00:00:00Z'};
  const session={sessionFormat:'GROUP_REFORMER',startsAt:'2026-01-01T10:00:00Z'};
  assert.equal(sessionMemberships([membership],[{id:'product',category:'PERSONAL',sessionFormat:'GROUP_REFORMER'}],'person',session).length,0);
  const personal={...session,sessionFormat:'PERSONAL_EQUIPMENT'};
  assert.equal(sessionMemberships([membership],[{id:'product',category:'PERSONAL',sessionFormat:'PERSONAL_EQUIPMENT'}],'person',personal).length,1);
  assert.equal(sessionMemberships([membership],[{id:'product',category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER',durationMinutes:55}],'person',{...session,status:'COMPLETED',durationMinutes:60}).length,0);
});
test('создание будущего и прошедшего занятия использует московское время без списания',()=>{
  const now=new Date('2026-10-14T12:00:00Z');
  const values={name:' Тренировка ',sessionFormat:'GROUP_REFORMER',startsAt:'2026-10-15T10:00',durationMinutes:'55',capacity:'4'};
  const future=sessionCreationPayload(values,'stable',now);
  assert.equal(future.name,'Группа на реформере');
  assert.equal(future.startsAt,'2026-10-15T07:00:00.000Z');assert.equal(future.status,'PLANNED');
  assert.equal(future.personId,undefined);assert.equal(future.membershipId,undefined);
  assert.throws(()=>sessionCreationPayload({...values,startsAt:'2026-10-13T10:00'},'stable',now),/Подтвердите/);
  assert.equal(sessionCreationPayload({...values,startsAt:'2026-10-13T10:00',pastConfirmed:'on'},'stable',now).status,'COMPLETED');
  assert.equal(sessionTimeState('2026-10-14T11:30:00Z',60,now),'CONFIRMED');
});
test('временная сетка отображает длительность и раскладывает пересечения по полосам',()=>{
  const intervals=calendarSessionLayout([
    {id:'one',startsAt:'2026-10-14T09:00:00+03:00',endsAt:'2026-10-14T10:00:00+03:00'},
    {id:'two',startsAt:'2026-10-14T09:30:00+03:00',endsAt:'2026-10-14T10:30:00+03:00'},
  ],'2026-10-14');
  assert.equal(intervals[0].top,192);assert.equal(intervals[0].height,96);
  assert.equal(intervals[0].laneCount,2);assert.notEqual(intervals[0].lane,intervals[1].lane);
  const crossing=calendarSessionLayout([{id:'overnight',startsAt:'2026-10-13T23:00:00+03:00',endsAt:'2026-10-14T08:00:00+03:00'}],'2026-10-14');
  assert.equal(crossing[0].top,0);assert.equal(crossing[0].height,96);
});

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
test('доступные продукты отсортированы по названию, затем по стоимости',()=>{
  const products=[
    {id:'personal-4k',name:'Персональное',price:{amountMicros:4_000_000_000},category:'PERSONAL',isActive:true},
    {id:'group-16k',name:'Группа 8',price:{amountMicros:16_000_000_000},category:'GROUP_PACKAGE',isActive:true},
    {id:'personal-3k',name:'Персональное',price:{amountMicros:3_000_000_000},category:'PERSONAL',isActive:true},
    {id:'group-8k',name:'Группа 4',price:{amountMicros:8_800_000_000},category:'GROUP_PACKAGE',isActive:true},
  ];
  assert.deepEqual(eligibleProducts(products).map(product=>product.id),[
    'group-8k','group-16k','personal-3k','personal-4k',
  ]);
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

test('разовая оплата подходит к формату, длительности и московскому дню, персональный блок не продаётся как разовое',()=>{
  const session={sessionFormat:'GROUP_REFORMER',startsAt:'2026-10-24T21:30:00Z',durationMinutes:55,status:'COMPLETED'};
  const product={id:'single',name:'Разовая',category:'SINGLE',sessionFormat:'GROUP_REFORMER',durationMinutes:55,isActive:true,validFrom:'2026-10-25',validTo:'2026-10-25',price:{amountMicros:1000000000}};
  assert.deepEqual(sessionPaymentProducts([product,{...product,id:'wrong',durationMinutes:60}],session).map(product=>product.id),['single']);
  const participant={personId:'person',productId:'single',paymentId:'payment',paymentContext:sessionPaymentContext('person','single',session)};
  assert.equal(sessionPaymentMatches(participant,session),true);
  for(const change of [{startsAt:'2026-10-25T21:30:00Z'},{durationMinutes:60},{sessionFormat:'TRX'},{status:'PLANNED'}])assert.equal(sessionPaymentMatches(participant,{...session,...change}),false);
  const personal={...session,sessionFormat:'PERSONAL_EQUIPMENT'};
  assert.equal(sessionPaymentProducts([{...product,category:'PERSONAL',sessionFormat:'PERSONAL_EQUIPMENT',visitsIncluded:4}],personal).length,0);
});

test('отмена разовой записи использует команду отмены долга, пакетной — возврат резерва',()=>{
  assert.equal(sessionCancellationPath({membershipId:'package'}),'/studio/bookings/cancel');
  assert.equal(sessionCancellationPath({membershipId:null,paymentStatus:'EXPECTED'}),'/studio/bookings/cancel-pay-as-you-go');
});
