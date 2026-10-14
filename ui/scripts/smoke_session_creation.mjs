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
  await form.getByLabel('Название',{exact:true}).fill('Будущая тренировка');
  await form.getByLabel('Длительность, минут').fill('60');
  await form.getByRole('button',{name:'Запланировать тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Незавершённое создание'}).waitFor();
  await page.reload();
  await page.getByRole('button',{name:'Продолжить создание'}).click();
  await modal.getByRole('button',{name:'Повторить прежний запрос'}).click();
  await modal.getByRole('heading',{name:'Будущая тренировка',exact:true}).waitFor();
  assert.equal(saved.size,1);assert.deepEqual(writes[0],writes[1]);
  assert.equal(writes[0].status,'PLANNED');assert.equal(writes[0].startsAt,futureDay+'T06:00:00.000Z');
  await modal.getByText('Тренировка создана',{exact:true}).waitFor();
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  const event=page.getByRole('button',{name:/Будущая тренировка ·/});
  await event.waitFor();assert.equal(await event.evaluate(element=>getComputedStyle(element).position),'absolute');
  assert.equal(await event.evaluate(element=>Math.round(element.getBoundingClientRect().height)),96);
  await page.screenshot({path:join(tmpdir(),'gelios-time-grid.png'),fullPage:true});
  await event.click();
  assert.equal(await modal.getByRole('heading',{name:'Новая тренировка',exact:true}).count(),0);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('button',{name:'+ Новая тренировка',exact:true}).click();
  await form.getByLabel('Название',{exact:true}).fill('Прошедшая тренировка');
  await form.getByLabel('Дата и начало (Москва)').fill(addDays(today(),-1)+'T10:00');
  await form.getByRole('button',{name:'Внести прошедшую тренировку',exact:true}).click();
  assert.equal(writes.length,2);
  await form.getByRole('checkbox',{name:'Подтверждаю, что тренировка состоялась'}).check();
  await page.screenshot({path:join(tmpdir(),'gelios-create-past-session.png'),fullPage:true});
  await form.getByRole('button',{name:'Внести прошедшую тренировку',exact:true}).click();
  await modal.getByRole('heading',{name:'Прошедшая тренировка',exact:true}).waitFor();
  assert.equal(writes.at(-1).status,'COMPLETED');
  assert.equal(writes.at(-1).pastConfirmed,true);
  assert.equal(data.transactions.length,0);assert.equal(data.bookings.length,0);assert.equal(data.events.length,2);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:join(tmpdir(),'gelios-time-grid-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: grid cell prefill, Moscow time, future creation, lost response/reload/retry, duration layout under CSP, existing click, past confirmation, no visits consumed, mobile.');
}catch(error){console.log('UI errors',errors);console.log(await page.locator('body').innerText());throw error;}
finally{await browser.close();}
