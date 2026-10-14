import assert from 'node:assert/strict';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {today,addDays} from '../src/domain.js';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const data={clients:[],products:[],packages:[],bookings:[],sessions:[],transactions:[],events:[]};
const groupPerson='00000000-0000-4000-8000-000000000011',personalPerson='00000000-0000-4000-8000-000000000012';
data.clients=[{id:groupPerson,name:{firstName:'Групповой клиент'}},{id:personalPerson,name:{firstName:'Персональный клиент'}},{id:'no-package',name:{firstName:'Без пакета'}}];
data.products=[{id:'group-product',category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER',durationMinutes:55},{id:'personal-product',category:'PERSONAL',sessionFormat:'PERSONAL_EQUIPMENT',durationMinutes:55}];
data.packages=[{id:'00000000-0000-4000-8000-000000000021',name:'Групповой пакет',personId:groupPerson,productId:'group-product',status:'ACTIVE',activatedAt:'2020-01-01T00:00:00Z',visitsAvailable:8},{id:'00000000-0000-4000-8000-000000000022',name:'Персональный пакет',personId:personalPerson,productId:'personal-product',status:'ACTIVE',activatedAt:'2020-01-01T00:00:00Z',visitsAvailable:8}];
const writes=[],saved=new Map();
let loseResponse=true;
const origin=process.env.UI_SMOKE_URL||'http://127.0.0.1:5184/';
await page.route(origin,async route=>{
  const response=await route.fetch();
  await route.fulfill({response,headers:{...response.headers(),'content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'"}});
});
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/v1/studio/auth/status')return reply({configured:true,auth_mode:'api_key'});
  if(path.startsWith('/api/v1/studio/records/'))return reply({items:data[path.split('/').at(-1)],next_cursor:null});
  assert.equal(path,'/api/v1/studio/sessions/create');
  const body=request.postDataJSON();writes.push(body);
  let session=saved.get(body.idempotencyKey);
  if(!session){
    session={id:'session-'+saved.size,...body,endsAt:new Date(new Date(body.startsAt).getTime()+body.durationMinutes*60000).toISOString(),bookedCount:0,attendedCount:0};
    saved.set(body.idempotencyKey,session);data.sessions.push(session);
    data.events.push({id:session.id,classSessionId:session.id,eventType:'SESSION_CREATED',outcome:'SUCCESS',occurredAt:new Date().toISOString()});
    for(const participant of body.participants||[]){
      data.bookings.push({id:session.id+'-booking',...participant,classSessionId:session.id,status:body.status==='COMPLETED'?'ATTENDED':'BOOKED',bookingType:body.sessionFormat==='PERSONAL_EQUIPMENT'?'PERSONAL':'REGULAR'});
      data.transactions.push({id:session.id+'-transaction',membershipId:participant.membershipId,transactionType:body.status==='COMPLETED'?'CONSUME':'RESERVE',visitDelta:-1});
      data.events.push({id:session.id+'-participant',classSessionId:session.id,eventType:'BOOKING_CREATED',outcome:'SUCCESS',occurredAt:new Date().toISOString()});
    }
  }
  if(loseResponse){loseResponse=false;return reply({detail:'Результат создания не подтверждён. Повторите прежний запрос.'},502);}
  return reply({success:true,classSessionId:session.id,duplicate:writes.length===2});
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test'));
try{
  await page.goto(origin+'#gelios/calendar');
  await page.getByRole('heading',{name:'Календарь тренировок',exact:true}).waitFor();
  await page.getByRole('button',{name:'Неделя →',exact:true}).click();
  const futureDay=addDays(today(),7);
  await page.locator(`[data-calendar-slot="${futureDay}T09:00"]`).click();
  const modal=page.locator('#confirm'),form=modal.locator('#calendar-create-form');
  assert.equal(await form.getByLabel('Дата и начало (Москва)').inputValue(),futureDay+'T09:00');
  assert.equal(await form.getByLabel('Название (из формата)').inputValue(),'Группа на реформере');
  assert.ok(await form.getByLabel('Название (из формата)').getAttribute('readonly')!==null);
  await form.getByLabel('Длительность, минут').fill('60');
  assert.equal(await form.getByLabel('Доступный клиент').locator('option').count(),2);
  await form.getByLabel('Доступный клиент').selectOption(groupPerson);
  await form.getByRole('button',{name:'Добавить в список',exact:true}).click();
  await form.getByRole('button',{name:'Запланировать тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Незавершённое создание'}).waitFor();
  await page.reload();
  await page.getByRole('button',{name:'Продолжить создание'}).click();
  await modal.getByRole('button',{name:'Повторить прежний запрос'}).click();
  await modal.getByRole('heading',{name:'Группа на реформере',exact:true}).waitFor();
  assert.equal(saved.size,1);assert.deepEqual(writes[0],writes[1]);
  assert.equal(writes[0].status,'PLANNED');assert.equal(writes[0].startsAt,futureDay+'T06:00:00.000Z');
  assert.equal(writes[0].participants[0].personId,groupPerson);
  assert.equal(data.bookings.length,1);
  await modal.getByText('Тренировка создана',{exact:true}).waitFor();
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  const event=page.getByRole('button',{name:/Группа на реформере ·/});
  await event.waitFor();assert.equal(await event.evaluate(element=>getComputedStyle(element).position),'absolute');
  assert.equal(await event.evaluate(element=>Math.round(element.getBoundingClientRect().height)),96);
  await page.screenshot({path:join(tmpdir(),'gelios-time-grid.png'),fullPage:true});
  await event.click();
  assert.equal(await modal.getByRole('heading',{name:'Новая тренировка',exact:true}).count(),0);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('button',{name:'+ Новая тренировка',exact:true}).click();
  await form.getByLabel('Дата и начало (Москва)').fill(addDays(today(),-1)+'T10:00');
  await form.getByRole('button',{name:'Внести прошедшую тренировку',exact:true}).click();
  assert.equal(writes.length,2);
  await form.getByRole('checkbox',{name:'Подтверждаю, что тренировка состоялась'}).check();
  await page.screenshot({path:join(tmpdir(),'gelios-create-past-session.png'),fullPage:true});
  await form.getByRole('button',{name:'Внести прошедшую тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Группа на реформере',exact:true}).waitFor();
  assert.equal(writes.at(-1).status,'COMPLETED');
  assert.equal(writes.at(-1).pastConfirmed,true);
  assert.equal(data.transactions.length,1);assert.equal(data.bookings.length,1);assert.equal(data.events.length,3);
  assert.equal(data.transactions[0].transactionType,'RESERVE');
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('button',{name:'+ Новая тренировка',exact:true}).click();
  await form.getByLabel('Дата и начало (Москва)').fill(futureDay+'T11:00');
  await form.getByLabel('Формат',{exact:true}).selectOption('PERSONAL_EQUIPMENT');
  assert.equal(await form.getByLabel('Название (из формата)').inputValue(),'Персональное на оборудовании');
  assert.equal(await form.getByLabel('Количество мест').inputValue(),'1');
  assert.equal(await form.getByLabel('Количество мест').getAttribute('readonly'),'');
  assert.equal(await form.getByLabel('Доступный клиент').locator('option').count(),2);
  await form.getByLabel('Доступный клиент').selectOption(personalPerson);
  await form.getByRole('button',{name:'Добавить в список',exact:true}).click();
  assert.ok(await form.getByRole('button',{name:'Добавить в список',exact:true}).isDisabled());
  await page.screenshot({path:join(tmpdir(),'gelios-personal-participant-picker.png'),fullPage:true});
  await form.getByRole('button',{name:'Запланировать тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Персональное на оборудовании',exact:true}).waitFor();
  assert.equal(writes.at(-1).participants[0].personId,personalPerson);
  assert.equal(data.bookings.length,2);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:join(tmpdir(),'gelios-time-grid-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: grid creation, available group/personal clients, selected packages, personal capacity, lost response/retry without duplicate people, empty historical session, mobile.');
}catch(error){console.log('UI errors',errors);console.log(await page.locator('body').innerText());throw error;}
finally{await browser.close();}
