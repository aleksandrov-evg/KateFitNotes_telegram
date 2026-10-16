export function formatPhoneInput(value) {
  let digits=value.replace(/[^0-9]/g,'');
  if(value.startsWith('+7')||(digits.length===11&&/^[78]/.test(digits)))digits=digits.slice(1);
  digits=digits.slice(0,10);
  let formatted='+7';
  if(digits.length)formatted+=' ('+digits.slice(0,3);
  if(digits.length>=3)formatted+=') '+digits.slice(3,6);
  if(digits.length>6)formatted+='-'+digits.slice(6,8);
  if(digits.length>8)formatted+='-'+digits.slice(8,10);
  return formatted;
}

export function bindPhoneInput(input) {
  input.value=formatPhoneInput(input.value);
  const validate=()=>input.setCustomValidity(/^\+7 \([0-9]{3}\) [0-9]{3}-[0-9]{2}-[0-9]{2}$/.test(input.value)?'':'Введите номер полностью: +7 (921) 000-00-00.');
  input.addEventListener('input',()=>{
    const cursor=input.selectionStart??input.value.length;
    const digitsBeforeCursor=input.value.slice(0,cursor).replace(/[^0-9]/g,'').length;
    input.value=formatPhoneInput(input.value);
    let position=2, digitsSeen=1;
    while(position<input.value.length&&digitsSeen<digitsBeforeCursor){
      if(/[0-9]/.test(input.value[position]))digitsSeen++;
      position++;
    }
    while(position<input.value.length&&/[^0-9]/.test(input.value[position]))position++;
    input.setSelectionRange(position,position);
    validate();
  });
  input.addEventListener('keydown',event=>{
    const start=input.selectionStart, end=input.selectionEnd;
    if(start!==end||event.key!=='Backspace')return;
    let position=start;
    while(position>2&&/[^0-9]/.test(input.value[position-1]))position--;
    if(position<=2){event.preventDefault();return;}
    input.setSelectionRange(position,start);
  });
  validate();
}
