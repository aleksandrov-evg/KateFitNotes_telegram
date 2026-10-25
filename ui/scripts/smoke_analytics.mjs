import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:false,slowMo:200,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
await page.clock.install({time:new Date('2026-10-25T10:00:00Z')});
const origin=process.env.UI_SMOKE_URL||'http://127.0.0.1:5186/';
const artifacts=process.env.UI_SMOKE_ARTIFACT_DIR||join(tmpdir(),'katfit-analytics-smoke');
await mkdir(artifacts,{recursive:true});
const errors=[],writes=[];
page.on('pageerror',error=>errors.push(error.message));
const currency=minor=>({amountMicros:String(BigInt(minor)*10000n),currencyCode:'RUB'});
const personId='00000000-0000-4000-8000-000000000001';
const expenseId='00000000-0000-4000-8000-000000000002';
const data={
  clients:[{id:personId,name:{firstName:'Анна',lastName:'Тестовая'}}],
  products:[],packages:[],transactions:[],events:[],
  sessions:[{id:'session-1',name:'Группа на реформере',sessionFormat:'GROUP_REFORMER',capacity:4,status:'COMPLETED',startsAt:'2026-10-15T09:00:00+03:00',endsAt:'2026-10-15T09:55:00+03:00'}],
  bookings:[{id:'booking-1',personId,classSessionId:'session-1',status:'ATTENDED'}],
  payments:[{id:'payment-1',personId,name:'Тестовая оплата',status:'PAID',paidAt:'2026-10-10T09:00:00+03:00',amount:currency('1000000')}],
  expenses:[{id:expenseId,name:'Тестовая аренда',category:'RENT',costType:'FIXED',amount:currency('123456'),accruedOn:'2026-10-01',paidOn:'2026-11-02',description:'Синтетические данные'}],
};
let rejectedSource=null,unknownSave=false,saveGate=null;
const recordRequests=new Map();
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  assert.equal(request.headers().authorization,'Bearer analytics-test');
  if(path==='/api/v1/studio/auth/status')return reply({configured:true});
  if(path.startsWith('/api/v1/studio/records/')){
    const resource=path.split('/').at(-1);recordRequests.set(resource,(recordRequests.get(resource)||0)+1);
    if(resource===rejectedSource)return reply({detail:'Тестовая недоступность источника'},502);
    if(resource==='payments'&&!url.searchParams.get('cursor'))return reply({items:[],next_cursor:'page-2'});
    assert.ok(Array.isArray(data[resource]),'Unknown resource '+resource);
    return reply({items:data[resource],next_cursor:null});
  }
  if(path==='/api/v1/studio/expenses/save'){
    assert.equal(request.method(),'POST');const body=request.postDataJSON();writes.push(body);
    if(saveGate)await saveGate;
    if(unknownSave)return reply({detail:{code:'EXPENSE_OUTCOME_UNKNOWN',message:'Результат сохранения неизвестен. Проверьте журнал.'}},502);
    const record={id:body.expenseId||expenseId+'-created',name:body.name,amount:currency(body.amountMinor),category:body.category,costType:body.costType,accruedOn:body.accrualMonth+'-01',paidOn:body.paidOn,description:body.description};
    const index=data.expenses.findIndex(item=>item.id===record.id);
    if(index<0)data.expenses.push(record);else data.expenses[index]=record;
    return reply({id:record.id});
  }
  if(request.method()==='DELETE'&&path.startsWith('/api/v1/studio/expenses/')){
    const id=decodeURIComponent(path.split('/').at(-1));writes.push({deleted:id});data.expenses=data.expenses.filter(record=>record.id!==id);return reply({id,deleted:true});
  }
  throw new Error(`Unexpected request ${request.method()} ${path}`);
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','analytics-test'));
const tab=key=>page.locator(`[data-analytics-tab="${key}"]`);
const action=(key,scope=page)=>scope.locator(`[data-analytics-action="${key}"]`);
const dialog=page.locator('#confirm');
const noOverflow=async()=>{
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);
  if(!fits){
    console.log(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(element=>{const box=element.getBoundingClientRect();return box.width>0&&(box.right>innerWidth+1||box.left< -1)&&getComputedStyle(element).position!=='fixed';}).map(element=>({tag:element.tagName,class:element.className,width:element.getBoundingClientRect().width,right:element.getBoundingClientRect().right})).slice(0,20)));
    await page.screenshot({path:join(artifacts,'overflow.png'),fullPage:true});
  }
  assert.ok(fits,'Page must fit viewport');
};
try{
  await page.goto(origin+'#gelios/analytics');
  await tab('overview').waitFor();
  await page.locator('#analytics-content').getByText('10 000,00 ₽',{exact:true}).first().waitFor();
  assert.equal(recordRequests.get('payments'),2,'All payment pages must load');
  await noOverflow();
  await page.screenshot({path:join(artifacts,'analytics-desktop.png'),fullPage:true});
  for(const key of ['income','expenses','profit','sessions','clients','balances','overview']){
    await tab(key).click();await page.locator('#analytics-content').waitFor();await noOverflow();
  }
  await tab('clients').click();await page.getByRole('link',{name:'Открыть клиента',exact:true}).click();
  await dialog.getByRole('heading',{name:'Анна Тестовая'}).waitFor();await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('link',{name:'Аналитика',exact:true}).click();await tab('overview').waitFor();
  await page.getByRole('button',{name:'Как считаем',exact:true}).click();await dialog.getByRole('heading',{name:'Как считаем аналитику'}).waitFor();await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
  await tab('expenses').click();await action('expense-create').click();
  let form=page.locator('#analytics-expense-form');
  await form.getByLabel('Название расхода',{exact:true}).fill('STAGE-QA mock expense');
  await form.getByLabel('Сумма, ₽',{exact:true}).fill('0');
  await page.locator('#dialog-submit').click();assert.equal(writes.length,0,'Invalid amount must not write');
  await form.getByLabel('Сумма, ₽',{exact:true}).fill('1500,25');
  let releaseSave;saveGate=new Promise(resolve=>{releaseSave=resolve;});
  await page.locator('#dialog-submit').click();
  await page.waitForFunction(()=>document.querySelector('#dialog-submit').disabled);
  assert.equal(writes.length,1);assert.equal(writes[0].amountMinor,'150025');assert.equal(writes[0].paidOn,null);
  releaseSave();saveGate=null;await dialog.waitFor({state:'hidden'});
  await page.locator('tbody tr').filter({hasText:'STAGE-QA mock expense'}).waitFor();
  const created=data.expenses.find(record=>record.name==='STAGE-QA mock expense');
  await page.locator(`[data-analytics-action="expense-edit"][data-id="${created.id}"]`).click();
  form=page.locator('#analytics-expense-form');await form.getByLabel('Сумма, ₽',{exact:true}).fill('1600,50');await page.locator('#dialog-submit').click();await dialog.waitFor({state:'hidden'});
  assert.equal(writes.at(-1).expenseId,created.id);assert.equal(writes.at(-1).amountMinor,'160050');
  await page.locator(`[data-analytics-action="expense-detail"][data-id="${created.id}"]`).click();await action('expense-delete',dialog).click();await dialog.getByRole('heading',{name:'Удалить расход?',exact:true}).waitFor();await dialog.locator('#dialog-submit').click();await dialog.waitFor({state:'hidden'});assert.equal(data.expenses.some(record=>record.id===created.id),false);
  await action('expense-create').click();form=page.locator('#analytics-expense-form');await form.getByLabel('Название расхода',{exact:true}).fill('Неопределённый результат');await form.getByLabel('Сумма, ₽',{exact:true}).fill('100');unknownSave=true;await page.locator('#dialog-submit').click();
  await dialog.getByText(/Результат сохранения неизвестен/).first().waitFor();await page.waitForFunction(()=>document.querySelector('#dialog-submit').disabled);assert.equal(await form.getByLabel('Сумма, ₽',{exact:true}).inputValue(),'100');await dialog.getByRole('button',{name:'Отменить',exact:true}).click();unknownSave=false;
  rejectedSource='expenses';await page.getByRole('button',{name:'Обновить данные',exact:true}).click();await page.getByRole('alert').filter({hasText:'Часть данных'}).waitFor();await tab('overview').click();assert.equal(await page.locator('.analytics-metric').filter({hasText:'Начисленные расходы'}).locator('strong').innerText(),'—');rejectedSource=null;
  await action('reload').click();await tab('overview').waitFor();
  await page.locator('#analytics-month').fill('2026-11');await page.locator('#analytics-month').dispatchEvent('change');await page.getByText(/Будущий месяц/).first().waitFor();
  await page.locator('#analytics-month').fill('2026-10');await page.locator('#analytics-month').dispatchEvent('change');
  await page.setViewportSize({width:390,height:844});await noOverflow();
  await page.screenshot({path:join(artifacts,'analytics-mobile.png'),fullPage:true});
  for(const key of ['income','expenses','profit','sessions','clients','balances']){await tab(key).click();await noOverflow();}
  assert.deepEqual(errors,[]);console.log('Analytics smoke PASS: 7 tabs, pagination, expense create/edit/delete, validation, pending, unknown outcome, partial source, future month, mobile.');
  console.log('Screenshots:',artifacts);
}finally{await browser.close();}
