import assert from 'node:assert/strict';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {chooseOption} from './select_option.mjs';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
const personId='00000000-0000-4000-8000-000000000001';
const secondPersonId='00000000-0000-4000-8000-000000000002';
const productId='00000000-0000-4000-8000-000000000003';
const membershipId='00000000-0000-4000-8000-000000000004';
const data={
  clients:[personId,secondPersonId].map((id,index)=>({id,name:{firstName:'Анна',lastName:'Тестовая'},phones:{primaryPhoneNumber:`921000000${index}`}})),
  products:[{id:productId,name:'Реформер',category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER',isActive:true,price:{amountMicros:16000000000,currencyCode:'RUB'},visitsIncluded:8,durationMinutes:55,validityDays:30}],
  packages:[{id:membershipId,name:'Тестовый пакет',personId,productId,status:'ACTIVE',visitsGranted:8,visitsAvailable:7,visitsReserved:0,visitsConsumed:1,activatedAt:'2020-01-01T00:00:00Z'}],
  bookings:[{id:'booking',personId,membershipId,classSessionId:'session',status:'ATTENDED'}],
  sessions:[{id:'session',name:'Реформер',startsAt:'2026-01-01T10:00:00Z'}],
  transactions:[],events:[],
};
const originalRelations=JSON.stringify({packages:data.packages,bookings:data.bookings});
const writes=[];
let rejectRename=true;
let releaseRename;
let renameStarted;
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  assert.equal(request.headers().authorization,'Bearer test-session');
  if(path==='/api/v1/studio/auth/status')return reply({configured:true,auth_mode:'api_key'});
  if(path.startsWith('/api/v1/studio/records/'))return reply({items:data[path.split('/').at(-1)],next_cursor:null});
  if(request.method()==='PATCH'&&path===`/api/v1/studio/clients/${personId}`){
    const body=request.postDataJSON();writes.push({path,body});
    assert.deepEqual(Object.keys(body).sort(),['email','firstName','lastName']);
    if(rejectRename)return reply({detail:'CRM временно недоступна'},502);
    renameStarted?.();
    if(releaseRename)await releaseRename.promise;
    data.clients[0].name={firstName:body.firstName,lastName:body.lastName};
    data.clients[0].emails={primaryEmail:body.email};
    return reply({id:personId,name:data.clients[0].name,emails:data.clients[0].emails});
  }
  if(path==='/api/v1/train-types'||path==='/api/v1/reports/monthly')return reply([]);
  if(['/api/v1/clients','/api/v1/bookings','/api/v1/prepaid'].includes(path))return reply({items:[],total:0});
  throw new Error(`Unexpected ${request.method()} ${path}`);
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test-session'));
const dialog=page.locator('#confirm');
async function openRename(){
  await page.locator(`[data-studio-person="${personId}"]`).click();
  await dialog.getByRole('button',{name:'Редактировать контакт',exact:true}).click();
  await dialog.getByRole('heading',{name:'Редактировать контакт',exact:true}).waitFor();
  return page.locator('#studio-rename-form');
}
try{
  await page.goto((process.env.UI_SMOKE_URL||'http://127.0.0.1:5184/')+'#overview');
  await page.getByRole('heading',{name:'Обзор',exact:true}).waitFor();
  await chooseOption(page.getByLabel('Рабочее пространство'),'gelios');
  await page.getByRole('heading',{name:'Обзор Gelios',exact:true}).waitFor();
  await page.getByRole('link',{name:'Клиенты',exact:true}).click();
  await page.getByRole('heading',{name:'Клиенты Gelios',exact:true}).waitFor();
  let form=await openRename();
  await form.getByLabel('Имя',{exact:true}).fill('Отменённое имя');
  await dialog.getByRole('button',{name:'Отменить',exact:true}).click();
  assert.equal(writes.length,0);
  form=await openRename();
  await form.getByLabel('Имя',{exact:true}).fill('   ');
  await dialog.getByRole('button',{name:'Сохранить',exact:true}).click();
  assert.equal(writes.length,0);
  await form.getByLabel('Имя',{exact:true}).fill('  Мария  ');
  await form.getByLabel('Фамилия',{exact:true}).fill('  Новая  ');
  await form.getByLabel('Email',{exact:true}).fill('katfit.test@gmail.com');
  await dialog.getByRole('button',{name:'Сохранить',exact:true}).click();
  await dialog.getByRole('alert').getByText('CRM временно недоступна',{exact:false}).waitFor();
  assert.equal(await form.getByLabel('Имя',{exact:true}).inputValue(),'  Мария  ');
  assert.equal(data.clients[0].name.firstName,'Анна');
  assert.deepEqual(writes[0].body,{firstName:'Мария',lastName:'Новая',email:'katfit.test@gmail.com'});
  rejectRename=false;
  let release;
  releaseRename={promise:new Promise(resolve=>{release=resolve;})};
  const started=new Promise(resolve=>{renameStarted=resolve;});
  await dialog.getByRole('button',{name:'Сохранить',exact:true}).click();
  await started;
  assert.equal(await dialog.getByRole('button',{name:'Сохранить',exact:true}).isDisabled(),true);
  await form.evaluate(element=>element.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  release();
  await page.locator(`[data-studio-person="${personId}"]`).getByText('Мария Новая',{exact:true}).waitFor();
  assert.equal(writes.length,2);
  assert.deepEqual(writes[0],writes[1]);
  assert.deepEqual(data.clients[1].name,{firstName:'Анна',lastName:'Тестовая'});
  assert.equal(JSON.stringify({packages:data.packages,bookings:data.bookings}),originalRelations);
  await page.reload();
  await page.locator(`[data-studio-person="${personId}"]`).getByText('Мария Новая',{exact:true}).waitFor();
  await page.getByRole('link',{name:'Пакеты и оплата',exact:true}).click();
  await chooseOption(page.locator('#studio-payment-form').getByLabel('Клиент'),personId);
  assert.equal(await page.locator('#studio-payment-form').getByLabel('Клиент').inputValue(),'Мария Новая');
  await page.getByRole('link',{name:'Внести тренировку',exact:true}).click();
  await chooseOption(page.locator('#studio-attendance-form').getByLabel('Клиент'),personId);
  assert.equal(await page.locator('#studio-attendance-form').getByLabel('Клиент').inputValue(),'Мария Новая');
  await page.getByRole('link',{name:'Календарь тренировок',exact:true}).click();
  await page.locator('#calendar-new').click();
  assert.equal(await page.locator(`#session-person option[value="${personId}"]`).textContent(),'Мария Новая');
  assert.deepEqual(errors,[]);
  console.log('PASS: cancel, blank-name validation, trimmed rename, error recovery, duplicate-submit guard, reload, distinct contact IDs, unchanged relationships and current-name selectors.');
}catch(error){
  console.log(await page.locator('body').innerText());
  await page.screenshot({path:join(process.env.UI_SMOKE_ARTIFACT_DIR||tmpdir(),'gelios-client-rename-error.png'),fullPage:true});
  throw error;
}finally{await browser.close();}
