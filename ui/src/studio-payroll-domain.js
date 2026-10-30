import {calendarDate,relationId} from './studio-domain.js';
import {analyticsMoney} from './studio-money.js';

const day=value=>{
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value))return null;
  const date=value.slice(0,10),moment=new Date(value);
  if(!Number.isFinite(moment.getTime())||new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date)return null;
  return calendarDate(value);
};
const failure=reason=>({available:false,reasons:[reason],warnings:[reason],rows:[],expenses:[],trainers:[],pendingSessionIds:[],unclosedSessionIds:[],amountMinor:null,sessionCount:null,participantCount:null});

export const buildTrainerPayroll = (input={}, {month,now=new Date()}={}) => {
  if(!Array.isArray(input.trainerPayEntries)||input.incompleteSources?.includes('trainerPayEntries'))return failure('Реестр начислений тренерам не загружен. Итог затрат на зарплату неизвестен.');
  const sessions=new Map(),seen=new Map(),warnings=[];
  try {
    for(const entry of input.trainerPayEntries.filter(row=>!row.deletedAt)) {
      if(!entry.id)throw new Error('Начисление без идентификатора.');
      if(seen.has(entry.id)) {if(seen.get(entry.id)!==JSON.stringify(entry))throw new Error('Противоречивые страницы журнала начислений.');continue;}
      seen.set(entry.id,JSON.stringify(entry));
      if(!['ACCRUAL','REVERSAL'].includes(entry.entryType)||!['POSTED','PENDING'].includes(entry.state)||!Number.isSafeInteger(entry.revision)||entry.revision<1)throw new Error('Неизвестная операция или ревизия начисления.');
      const snapshot=JSON.parse(entry.snapshot);
      const sessionId=relationId(entry,'classSession'),trainerId=relationId(entry,'trainer');
      const amount=analyticsMoney(snapshot.amount),entryAmount=analyticsMoney(entry.amount);
      if(entry.participantCount!==snapshot.participantCount||snapshot.schemaVersion!==1||snapshot.calculationBasis!=='ATTENDED'||!Array.isArray(snapshot.bookings)||!Array.isArray(snapshot.attendedBookingIds)||snapshot.attendedBookingIds.length!==snapshot.participantCount||new Set(snapshot.attendedBookingIds).size!==snapshot.participantCount||snapshot.bookings.filter(row=>row.status==='ATTENDED').length!==snapshot.participantCount||snapshot.attendedBookingIds.some(id=>!snapshot.bookings.some(row=>row.id===id&&row.status==='ATTENDED'))||!sessionId||!trainerId||snapshot.session?.id!==sessionId||snapshot.session?.trainer?.id!==trainerId||!day(snapshot.session.startsAt)||Date.parse(snapshot.session.startsAt)>now.getTime()||amount===null||BigInt(amount)<0n||entryAmount===null||!Number.isSafeInteger(snapshot.participantCount)||snapshot.participantCount<1||snapshot.participantCount>4)throw new Error('Неполные или некорректные данные снимка начисления.');
      if(BigInt(entryAmount)!==BigInt(amount)*(entry.entryType==='REVERSAL'?-1n:1n))throw new Error('Сумма операции не совпадает с сохранённым расчётом.');
      const records=sessions.get(sessionId)||[];
      records.push({entry,snapshot,sessionId,trainerId,amountMinor:amount,date:day(snapshot.session.startsAt)});sessions.set(sessionId,records);
    }
    const rows=[],pending=new Set();
    for(const [sessionId,records] of sessions) {
      const accruals=records.filter(row=>row.entry.entryType==='ACCRUAL').sort((a,b)=>a.entry.revision-b.entry.revision);
      if(new Set(accruals.map(row=>row.entry.revision)).size!==accruals.length)throw new Error('Два начисления одной ревизии занятия.');
      if(accruals.length&&accruals[0].entry.revision!==1)throw new Error('Отсутствует исходное начисление занятия.');
      for(const reversal of records.filter(row=>row.entry.entryType==='REVERSAL')) {
        const accrual=accruals.find(row=>row.entry.revision===reversal.entry.revision);
        const previous=accruals.find(row=>row.entry.id===reversal.entry.previousEntryId&&row.entry.revision===reversal.entry.revision-1&&row.entry.state==='POSTED');
        if(!accrual||!previous||accrual.entry.previousEntryId!==previous.entry.id||reversal.trainerId!==previous.trainerId||reversal.amountMinor!==previous.amountMinor)throw new Error('Сторно не связано с исправлением занятия.');
      }
      for(const row of accruals.filter(row=>row.entry.state==='POSTED'&&row.entry.revision>1)) {
        const previous=accruals.find(item=>item.entry.id===row.entry.previousEntryId&&item.entry.state==='POSTED'&&item.entry.revision===row.entry.revision-1);
        const reversals=records.filter(item=>item.entry.entryType==='REVERSAL'&&item.entry.revision===row.entry.revision&&item.entry.state==='POSTED'&&item.entry.previousEntryId===previous?.entry.id);
        if(!previous||reversals.length!==1||reversals[0].trainerId!==previous.trainerId||reversals[0].amountMinor!==previous.amountMinor)throw new Error('Исправление не подтверждено соответствующим сторно.');
      }
      if(records.some(row=>row.entry.state==='PENDING'&&(!month||row.date.slice(0,7)===month)))pending.add(sessionId);
      const latest=accruals.filter(row=>row.entry.state==='POSTED').at(-1);
      if(latest)rows.push({...latest,id:latest.entry.id,name:latest.snapshot.session.name,participantCount:latest.snapshot.participantCount,trainerName:input.trainers?.find(trainer=>trainer.id===latest.trainerId)?.name||latest.snapshot.session.trainer.name||'Тренер',active:input.trainers?.find(trainer=>trainer.id===latest.trainerId)?.active});
    }
    const expenses=rows.map(row=>({id:'payroll:'+row.id,name:`Оплата тренеру · ${row.trainerName} · ${row.name}`,source:'TRAINER_PAYROLL',category:'TRAINERS',costType:'VARIABLE',accruedOn:row.date.slice(0,7)+'-01',paidOn:null,amount:{amountMicros:(BigInt(row.amountMinor)*10000n).toString(),currencyCode:'RUB'},trainerId:row.trainerId,classSessionId:row.sessionId,trainerPayEntryId:row.id,description:row.date,payroll:row}));
    const monthly=rows.filter(row=>!month||row.date.slice(0,7)===month).sort((a,b)=>b.date.localeCompare(a.date)||a.id.localeCompare(b.id));
    const trainers=[...new Set(monthly.map(row=>row.trainerId))].map(id=>{
      const entries=monthly.filter(row=>row.trainerId===id);
      return {id,name:entries[0].trainerName,active:entries[0].active,sessionCount:entries.length,participantCount:entries.reduce((sum,row)=>sum+row.participantCount,0),amountMinor:entries.reduce((sum,row)=>sum+BigInt(row.amountMinor),0n).toString(),rows:entries};
    }).sort((a,b)=>a.name.localeCompare(b.name,'ru'));
    const unclosed=(input.sessions||[]).filter(session=>!session.deletedAt&&session.status==='COMPLETED'&&session.sessionFormat==='GROUP_REFORMER'&&day(session.startsAt)?.slice(0,7)===month&&!rows.some(row=>row.sessionId===session.id)).map(session=>session.id);
    if(pending.size)warnings.push(`Есть незавершённые начисления: ${pending.size}. Итог предварительный, учтены последние завершённые ревизии.`);
    if(unclosed.length)warnings.push(`Проведены, но ещё не начислены: ${unclosed.length}. Их оплата пока не включена в затраты.`);
    return {available:true,month,reasons:[],warnings,rows:monthly,allRows:rows,expenses,trainers,pendingSessionIds:[...pending],unclosedSessionIds:unclosed,amountMinor:monthly.reduce((sum,row)=>sum+BigInt(row.amountMinor),0n).toString(),sessionCount:monthly.length,participantCount:monthly.reduce((sum,row)=>sum+row.participantCount,0)};
  } catch(error) {return failure(`Журнал зарплаты требует сверки: ${error.message}`);}
};
