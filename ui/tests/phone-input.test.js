import {test} from 'node:test';
import assert from 'node:assert/strict';
import {bindPhoneInput,formatPhoneInput} from '../src/phone-input.js';
import {normalizePhone} from '../src/domain.js';

function phoneField() {
  const handlers={};
  const input={value:'',selectionStart:4,selectionEnd:4,setCustomValidity(message){this.error=message;},addEventListener(name,handler){handlers[name]=handler;},setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;}};
  bindPhoneInput(input);
  const type=(data,inputType='insertText')=>handlers.beforeinput({data,inputType,preventDefault(){}});
  return {input,handlers,type};
}

test('полная маска видна до ввода и при частичном заполнении',()=>{
  assert.equal(formatPhoneInput(''),'+7 (___) ___-__-__');
  assert.equal(formatPhoneInput('+7 9211'),'+7 (921) 1__-__-__');
  for(const value of ['9211234567','89211234567','+7 (921) 123-45-67'])assert.equal(formatPhoneInput(value),'+7 (921) 123-45-67');
});

test('цифры заполняют маску, лишние не вводятся, неполный номер блокирует отправку',()=>{
  const {input,type}=phoneField();
  assert.ok(input.error);
  for(const digit of '9211234567')type(digit);
  assert.equal(input.value,'+7 (921) 123-45-67');
  assert.equal(input.error,'');
  assert.equal(normalizePhone(input.value),'+79211234567');
  type('89');assert.equal(input.value,'+7 (921) 123-45-67');
  type(null,'deleteContentBackward');
  assert.equal(input.value,'+7 (921) 123-45-6_');
  assert.ok(input.error);
  assert.throws(()=>normalizePhone(input.value));
});

test('удаление и замена в середине сохраняют позиции остальных цифр и разделителей',()=>{
  const {input,type}=phoneField();
  type('9211234567');
  input.setSelectionRange(9,9);type(null,'deleteContentBackward');
  assert.equal(input.value,'+7 (92_) 123-45-67');
  type('5');assert.equal(input.value,'+7 (925) 123-45-67');
  input.setSelectionRange(0,18);type(null,'deleteContentBackward');
  assert.equal(input.value,'+7 (___) ___-__-__');
  assert.equal(input.selectionStart,4);
});

test('вставка полного номера заполняет маску, буквы не заменяют цифры',()=>{
  const {input,handlers,type}=phoneField();
  handlers.paste({preventDefault(){},clipboardData:{getData:()=>'+7 (921) 123-45-67'}});
  assert.equal(input.value,'+7 (921) 123-45-67');
  input.setSelectionRange(4,4);type('abc');
  assert.equal(input.value,'+7 (921) 123-45-67');
});
