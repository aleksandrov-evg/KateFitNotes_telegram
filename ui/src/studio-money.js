export const analyticsMoney = value => {
  if (!value || value.currencyCode !== 'RUB') return null;
  const raw = value.amountMicros;
  if ((typeof raw === 'number' && !Number.isSafeInteger(raw)) || !/^-?\d+$/.test(String(raw))) return null;
  const micros = BigInt(raw);
  return micros % 10000n === 0n ? (micros / 10000n).toString() : null;
};
export const formatMinorMoney = value => {
  if(value === null || value === undefined)return '—';
  const amount=BigInt(value), absolute=amount<0n?-amount:amount;
  return `${amount<0n?'−':''}${(absolute/100n).toLocaleString('ru-RU')},${String(absolute%100n).padStart(2,'0')} ₽`;
};
export const parseMinorMoney = value => {
  const text=String(value).trim().replace(',','.');
  if(!/^\d{1,10}(\.\d{1,2})?$/.test(text))throw Object.assign(new Error('Укажите сумму с точностью до копейки.'),{status:422});
  const [whole,fraction='']=text.split('.');
  return (BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'))).toString();
};
