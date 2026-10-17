import {test} from 'node:test';
import assert from 'node:assert/strict';
import {weekStart,weekDays,addDays,normalizePhone,integer,priceHint,bookingPayload,escapeHtml} from '../src/domain.js';

test('неделя начинается с понедельника, включая границу года',()=>{
  assert.equal(weekStart('2026-10-18'),'2026-10-12');
  assert.deepEqual(weekDays('2027-01-01'),['2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01','2027-01-02','2027-01-03']);
  assert.equal(addDays('2028-02-28',1),'2028-02-29');
});
test('телефон и целочисленный ввод валидируются до отправки',()=>{
  assert.equal(normalizePhone('+7 (921) 000-00-00'),'+79210000000');
  assert.equal(normalizePhone('89210000000'),'89210000000');
  for(const value of ['9210000000','+19210000000','abc'])assert.throws(()=>normalizePhone(value));
  for(const value of ['-1','1.5','1e3','','9007199254740993'])assert.throws(()=>integer(value,'Цена'));
  assert.equal(integer('0','Цена'),0);
});
test('пакет имеет приоритет, несколько пакетов блокируют запись',()=>{
  const p={id:1,client_id:1,type_train_id:2,is_complete:false,price_per_train:1000/3};
  assert.equal(priceHint([p],[],1,2).price,1000/3);
  assert.equal(priceHint([p,{...p,id:2}],[],1,2).blocked,true);
  assert.equal(priceHint([{...p,is_complete:true}],[],1,2).package,undefined);
  assert.equal(priceHint([p],[],2,2).package,undefined);
});
test('берётся последняя цена именно клиента и типа',()=>{
  const rows=[{client:1,type_train_id:2,date:'2026-09-01',time:'09:00',price:100},{client:1,type_train_id:2,date:'2026-09-02',time:'10:00',price:200},{client:2,type_train_id:2,date:'2026-10-01',time:'09:00',price:300}];
  assert.equal(priceHint([],rows,1,2).price,200);
});
test('персональная запись передаёт null для серверного расчёта пакета; группа — общую цену',()=>{
  const d={client:'1',clients:[1,2,2],type:'2',date:'2026-10-13',time:'09:00',price:'1500'};
  assert.equal(bookingPayload(d,false,{package:{},price:1000/3}).price,null);
  const group=bookingPayload(d,true,{});assert.deepEqual(group.client_ids,[1,2]);assert.equal(group.price,1500);assert.equal(group.client_id,undefined);
  assert.throws(()=>bookingPayload({...d,time:''},false,{}));
  assert.throws(()=>bookingPayload({...d,clients:[]},true,{}));
  assert.throws(()=>bookingPayload(d,false,{blocked:true,message:'Несколько пакетов'}));
});
test('пользовательский текст экранируется',()=>{assert.equal(escapeHtml('<img onerror="x">&'), '&lt;img onerror=&quot;x&quot;&gt;&amp;');});
