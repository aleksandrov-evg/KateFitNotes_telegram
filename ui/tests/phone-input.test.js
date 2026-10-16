import {test} from 'node:test';
import assert from 'node:assert/strict';
import {bindPhoneInput,formatPhoneInput} from '../src/phone-input.js';
import {normalizePhone} from '../src/domain.js';

test('маска форматирует вставку номера и ограничивает десятью цифрами после +7',()=>{
  for(const value of ['9211234567','89211234567','+7 (921) 123-45-67'])assert.equal(formatPhoneInput(value),'+7 (921) 123-45-67');
  assert.equal(formatPhoneInput('+7 (921) 123-45-6789'),'+7 (921) 123-45-67');
  assert.equal(formatPhoneInput(''),'+7');
  for(const value of ['+7','+7 (921) 123-45-6','+7 (921) 123-45-678'])assert.throws(()=>normalizePhone(value));
});

test('последовательный ввод ставит разделители, неполный номер блокирует отправку',()=>{
  const handlers={};
  const input={value:'',selectionStart:0,selectionEnd:0,setCustomValidity(message){this.error=message;},addEventListener(name,handler){handlers[name]=handler;},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;}};
  bindPhoneInput(input);
  assert.equal(input.value,'+7');
  assert.ok(input.error);
  for(const digit of '9211234567'){
    input.value+=digit;input.selectionStart=input.selectionEnd=input.value.length;handlers.input();
  }
  assert.equal(input.value,'+7 (921) 123-45-67');
  assert.equal(input.error,'');
  input.value=input.value.slice(0,-1);handlers.input();
  assert.ok(input.error);
  input.value='+7 (921) ';input.selectionStart=input.selectionEnd=input.value.length;
  handlers.keydown({key:'Backspace'});
  input.value=input.value.slice(0,input.selectionStart-1)+input.value.slice(input.selectionEnd);
  input.selectionStart=input.selectionEnd=input.value.length;handlers.input();
  assert.equal(input.value,'+7 (92');
});
