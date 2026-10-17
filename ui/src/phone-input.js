const PHONE_MASK='+7 (___) ___-__-__';
const DIGIT_POSITIONS=[4,5,6,9,10,11,13,14,16,17];

export function formatPhoneInput(value) {
  let digits=value.replace(/[^0-9]/g,'');
  if(value.startsWith('+7')||(digits.length===11&&/^[78]/.test(digits)))digits=digits.slice(1);
  let index=0;
  return PHONE_MASK.replace(/_/g,()=>digits[index++]||'_');
}

export function bindPhoneInput(input) {
  input.value=formatPhoneInput(input.value);
  const validate=()=>input.setCustomValidity(input.value.includes('_')?'Введите номер полностью: +7 (921) 000-00-00.':'');
  const moveCursor=position=>input.setSelectionRange(position,position);
  const firstEmpty=()=>{
    const position=input.value.indexOf('_');
    return position===-1?PHONE_MASK.length:position;
  };
  const edit=(text,deletion)=>{
    const start=input.selectionStart??4, end=input.selectionEnd??start;
    const characters=input.value.split('');
    const selected=DIGIT_POSITIONS.filter(position=>position>=start&&position<end);
    for(const position of selected)characters[position]='_';
    if(deletion){
      const position=selected[0]??(deletion==='backward'
        ?DIGIT_POSITIONS.findLast(position=>position<start)
        :DIGIT_POSITIONS.find(position=>position>=start));
      if(position!==undefined){characters[position]='_';moveCursor(position);}
      input.value=characters.join('');
      if(position!==undefined)moveCursor(position);
    }else{
      let digits=text.replace(/[^0-9]/g,'');
      const replacesNumber=start<=4&&(end===PHONE_MASK.length||input.value===PHONE_MASK);
      if(replacesNumber&&(text.startsWith('+7')||(digits.length===11&&/^[78]/.test(digits))))digits=digits.slice(1);
      const positions=DIGIT_POSITIONS.filter(position=>position>=Math.max(4,start));
      let lastPosition=start;
      for(const [index,digit] of [...digits].entries()){
        const position=positions[index];
        if(position===undefined)break;
        characters[position]=digit;lastPosition=position+1;
      }
      input.value=characters.join('');
      moveCursor(DIGIT_POSITIONS.find(position=>position>=lastPosition)??PHONE_MASK.length);
    }
    validate();
  };
  input.addEventListener('focus',()=>moveCursor(firstEmpty()));
  input.addEventListener('beforeinput',event=>{
    if(event.inputType.startsWith('delete')){
      event.preventDefault();edit('',event.inputType.includes('Backward')?'backward':'forward');
    }else if(event.inputType.startsWith('insert')&&event.data!==null){
      event.preventDefault();edit(event.data);
    }
  });
  input.addEventListener('paste',event=>{
    event.preventDefault();edit(event.clipboardData.getData('text'));
  });
  input.addEventListener('input',()=>{
    input.value=formatPhoneInput(input.value);moveCursor(firstEmpty());validate();
  });
  validate();
}
