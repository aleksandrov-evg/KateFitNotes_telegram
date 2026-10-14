import {chooseOption} from './select_option.mjs';
import assert from 'node:assert/strict';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {today,weekStart} from '../src/domain.js';
import {calendarDate} from '../src/studio-domain.js';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const personId='00000000-0000-4000-8000-000000000001',membershipId='00000000-0000-4000-8000-000000000002',productId='00000000-0000-4000-8000-000000000003',sessionId='00000000-0000-4000-8000-000000000004';
const startsAt=new Date(Date.now()+86400000).toISOString();
const data={
  clients:[{id:personId,name:{firstName:'Анна',lastName:'Календарная'}}],
  products:[{id:productId,category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER'}],
  packages:[{id:membershipId,name:'8 занятий',personId,productId,status:'ACTIVE',activatedAt:'2020-01-01T00:00:00Z',visitsGranted:8,visitsAvailable:8,visitsReserved:0,visitsConsumed:0}],
  sessions:[{id:sessionId,name:'Реформер · календарь',startsAt,endsAt:new Date(new Date(startsAt).getTime()+55*60000).toISOString(),status:'PLANNED',sessionFormat:'GROUP_REFORMER',capacity:4}],
  bookings:[],transactions:[],events:[],
};
const writes=[],createdKeys=new Set(),cancelledKeys=new Set();
let loseCreateResponse=true;
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/v1/studio/auth/status')return reply({configured:true,auth_mode:'api_key'});
  if(path.startsWith('/api/v1/studio/records/'))return reply({items:data[path.split('/').at(-1)],next_cursor:null});
  const body=request.postDataJSON();writes.push({path,body});
  if(path==='/api/v1/studio/bookings/create'){
    if(!createdKeys.has(body.idempotencyKey)){
      createdKeys.add(body.idempotencyKey);
      data.bookings.push({id:'booking',personId,membershipId,classSessionId:sessionId,bookingType:'REGULAR',status:'BOOKED'});
      data.transactions.push({id:'reserve',membershipId,bookingId:'booking',transactionType:'RESERVE',visitDelta:-1});
      data.packages[0].visitsAvailable=7;data.packages[0].visitsReserved=1;
      data.events.push({id:'created-event',bookingId:'booking',classSessionId:sessionId,eventType:'BOOKING_CREATED',outcome:'SUCCESS',occurredAt:new Date().toISOString()});
    }
    if(loseCreateResponse){loseCreateResponse=false;return reply({detail:'Результат неизвестен. Используйте прежний ключ.'},502);}
    return reply({success:true,duplicate:true});
  }
  if(path==='/api/v1/studio/bookings/cancel'){
    if(!cancelledKeys.has(body.idempotencyKey)){
      cancelledKeys.add(body.idempotencyKey);
      data.bookings[0].status='CANCELLED_BY_STUDIO';
      data.transactions.push({id:'release',membershipId,bookingId:'booking',transactionType:'RELEASE',visitDelta:1});
      data.packages[0].visitsAvailable=8;data.packages[0].visitsReserved=0;
      data.events.push({id:'cancelled-event',bookingId:'booking',classSessionId:sessionId,eventType:'BOOKING_CANCELLED',outcome:'SUCCESS',occurredAt:new Date().toISOString()});
    }
    return reply({success:true});
  }
  throw new Error('Unexpected API path '+path);
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test-session'));
page.on('dialog',dialog=>dialog.accept());
try{
  await page.goto((process.env.UI_SMOKE_URL||'http://127.0.0.1:5184/')+'#gelios/calendar');
  await page.getByRole('heading',{name:'Календарь тренировок',exact:true}).waitFor();
  if(weekStart(calendarDate(startsAt))!==weekStart(today()))await page.getByRole('button',{name:'Неделя →',exact:true}).click();
  await page.screenshot({path:join(tmpdir(),'gelios-calendar-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:/Реформер · календарь/}).click();
  const modal=page.locator('#confirm');
  await chooseOption(modal.getByLabel('Клиент',{exact:true}),personId);
  await chooseOption(modal.getByLabel('Пакет',{exact:true}),membershipId);
  await modal.getByRole('button',{name:'Добавить клиента в тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Незавершённая операция'}).waitFor();
  await page.reload();
  await page.getByRole('button',{name:'Открыть карточку'}).click();
  await modal.getByRole('button',{name:'Повторить прежний запрос'}).click();
  await modal.getByRole('button',{name:'Убрать клиента',exact:true}).waitFor();
  assert.equal(createdKeys.size,1);
  const additions=writes.filter(write=>write.path.endsWith('/create'));
  assert.equal(additions.length,2);assert.deepEqual(additions[0].body,additions[1].body);
  await modal.getByText('Клиент добавлен',{exact:true}).waitFor();
  await page.screenshot({path:join(tmpdir(),'gelios-calendar-dialog.png'),fullPage:true});
  await modal.getByRole('button',{name:'Убрать клиента',exact:true}).click();
  await modal.getByText('Клиент убран',{exact:true}).waitFor();
  assert.equal(data.packages[0].visitsAvailable,8);
  assert.equal(data.transactions.length,2);
  assert.equal(data.events.length,2);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  data.sessions[0].status='COMPLETED';
  await page.getByRole('button',{name:'Обновить данные'}).click();
  if(weekStart(calendarDate(startsAt))!==weekStart(today()))await page.getByRole('button',{name:'Неделя →',exact:true}).click();
  await page.getByRole('button',{name:/Реформер · календарь/}).click();
  assert.equal(await modal.getByRole('button',{name:'Убрать клиента',exact:true}).count(),0);
  assert.equal(await modal.getByRole('button',{name:'Добавить клиента в тренировку',exact:true}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:join(tmpdir(),'gelios-calendar-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: calendar, modal, booking, lost response + reload + same-key retry, cancellation, CRM history, completed session protections, mobile.');
}catch(error){console.log('UI errors',errors);console.log(await page.locator('body').innerText());throw error;}
finally{await browser.close();}
