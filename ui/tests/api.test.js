import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Api} from '../src/api.js';
const storage=()=>{const values=new Map();return {getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};};
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
test('загрузка не обрезается первой страницей API',async()=>{
  const offsets=[];
  const api=new Api({storage:storage(),fetcher:async path=>{const offset=Number(new URL(path,'http://test').searchParams.get('offset'));offsets.push(offset);return json({items:offset===0?[1,2]:[3],total:3});}});
  assert.deepEqual(await api.all('/clients'),[1,2,3]);assert.deepEqual(offsets,[0,2]);
});
test('401 удаляет JWT и возвращает к входу',async()=>{
  const store=storage();let exits=0;const api=new Api({storage:store,onUnauthorized:()=>exits++,fetcher:async()=>json({detail:'не авторизован'},401)});
  api.setToken('test');await assert.rejects(api.request('/clients'),{status:401});assert.equal(api.token,'');assert.equal(store.getItem('katefit-token'),undefined);assert.equal(exits,1);
});
test('ошибка логина не вызывает сброс интерфейса',async()=>{
  let exits=0;const api=new Api({storage:storage(),onUnauthorized:()=>exits++,fetcher:async()=>json({detail:'неверный пароль'},401)});
  await assert.rejects(api.request('/auth/login',{method:'POST',body:{username:'x',password:'y'}}),{message:'неверный пароль'});assert.equal(exits,0);
});
test('запрос записи содержит Bearer и JSON, повторной отправки при сбое нет',async()=>{
  let calls=0;const api=new Api({storage:storage(),fetcher:async(path,options)=>{calls++;assert.equal(options.headers.Authorization,'Bearer test');assert.deepEqual(JSON.parse(options.body),{price:1500});throw new TypeError('network');}});
  api.setToken('test');await assert.rejects(api.request('/bookings/personal',{method:'POST',body:{price:1500}}),/Перед повторной отправкой/);assert.equal(calls,1);
});
