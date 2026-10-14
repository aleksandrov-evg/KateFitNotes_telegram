import assert from 'node:assert/strict';
import {join} from 'node:path';
import {tmpdir} from 'node:os';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const artifactDirectory=process.env.UI_SMOKE_ARTIFACT_DIR || tmpdir();

const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME ? {executablePath:process.env.UI_SMOKE_CHROME} : {})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.setDefaultTimeout(8000);
page.on('pageerror',error=>errors.push(error.message));
const personId='00000000-0000-4000-8000-000000000001',productId='00000000-0000-4000-8000-000000000002',membershipId='00000000-0000-4000-8000-000000000003';
const data={
  clients:[{id:personId,name:{firstName:'Анна',lastName:'Тестовая'},phones:{primaryPhoneCallingCode:'+7',primaryPhoneNumber:'9210000000'},emails:{primaryEmail:'anna@example.com'}}],
  products:[{id:productId,name:'Реформер · 8 занятий',category:'GROUP_PACKAGE',isActive:true,price:{amountMicros:16000000000,currencyCode:'RUB'},visitsIncluded:8,durationMinutes:55,validityDays:30}],
  packages:[{id:membershipId,name:'Реформер · тестовый пакет',personId,productId,status:'ACTIVE',visitsGranted:8,visitsAvailable:8,visitsReserved:0,visitsConsumed:0,expiresOn:'2026-12-31'}],
  bookings:[],sessions:[],transactions:[],events:[],
};
const writes=[],recorded=new Set();
let failRecord=true,configured=true;
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  assert.equal(request.headers().authorization,'Bearer test-session');
  if(path==='/api/v1/studio/auth/status')return reply({configured,auth_mode:'api_key'});
  if(path.startsWith('/api/v1/studio/records/'))return reply({items:data[path.split('/').at(-1)],next_cursor:null});
  if(request.method()==='POST'){
    const body=request.postDataJSON();writes.push({path,body});
    if(path==='/api/v1/studio/clients'){data.clients.push({id:body.clientId,name:{firstName:body.firstName,lastName:body.lastName},phones:{primaryPhoneNumber:body.phone}});return reply({id:body.clientId});}
    if(path==='/api/v1/studio/package-payments/confirm')return reply({success:true,membershipId:'new-package'});
    if(path==='/api/v1/studio/attendance/preview')return reply({success:true,preview:true,visitsAvailable:8,visitsAfter:7});
    if(path==='/api/v1/studio/attendance/record-past'){
      if(!recorded.has(body.idempotencyKey)){
        recorded.add(body.idempotencyKey);data.packages[0].visitsAvailable=7;data.packages[0].visitsConsumed=1;
        data.sessions.push({id:'session',startsAt:body.startsAt});
        data.bookings.push({id:'booking',personId,membershipId,classSessionId:'session',status:'ATTENDED'});
        data.transactions.push({id:'consume',membershipId,transactionType:'CONSUME',visitDelta:-1,occurredAt:body.startsAt,reason:body.reason});
      }
      if(failRecord){failRecord=false;return reply({detail:'Результат неизвестен. Повторите с прежним ключом.'},502);}
      return reply({success:true,duplicate:true,visitsAvailable:7});
    }
  }
  if(path==='/api/v1/train-types'||path==='/api/v1/reports/monthly')return reply([]);
  if(['/api/v1/clients','/api/v1/bookings','/api/v1/prepaid'].includes(path))return reply({items:[],total:0});
  throw new Error('Unexpected request '+path);
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test-session'));
try {
  await page.goto((process.env.UI_SMOKE_URL || 'http://127.0.0.1:5184/') + '#overview');
  await page.getByRole('heading',{name:'Обзор',exact:true}).waitFor();
  await page.getByLabel('Рабочее пространство').selectOption('gelios');
  await page.getByRole('heading',{name:'Обзор Gelios',exact:true}).waitFor();
  await page.screenshot({path:join(artifactDirectory,'gelios-ui-overview.png'),fullPage:true});
  await page.getByRole('link',{name:'Клиенты',exact:true}).click();
  await page.getByRole('heading',{name:'Клиенты Gelios',exact:true}).waitFor();
  const client=page.locator('#studio-client-form');
  await client.getByLabel('Имя',{exact:true}).fill('Мария');
  await client.getByLabel('Фамилия').fill('Новая');
  await client.getByLabel('Телефон').fill('+7 921 111-11-11');
  await client.getByRole('button',{name:'Добавить клиента'}).click();
  await page.getByRole('button',{name:'Мария Новая'}).waitFor();
  await page.getByRole('link',{name:'Пакеты и оплата',exact:true}).click();
  const payment=page.locator('#studio-payment-form');
  await payment.getByLabel('Клиент').selectOption(personId);
  await payment.getByLabel('Продукт').selectOption(productId);
  await payment.getByLabel('Когда оплачено').fill('2026-01-01T09:00');
  await payment.getByRole('button',{name:'Подтвердить оплату и создать пакет'}).click();
  await page.locator('#confirm').getByRole('button',{name:'Добавить',exact:true}).click();
  await page.locator('#confirm').waitFor({state:'hidden'});
  await page.getByRole('link',{name:'Внести тренировку',exact:true}).click();
  const attendance=page.locator('#studio-attendance-form');
  await attendance.getByLabel('Клиент').selectOption(personId);
  await attendance.getByLabel('Пакет').selectOption(membershipId);
  await attendance.getByLabel('Начало занятия').fill('2026-01-01T10:00');
  await attendance.getByLabel('Причина внесения').fill('По журналу');
  await attendance.getByRole('button',{name:'Проверить списание'}).click();
  await page.getByRole('button',{name:'Подтвердить посещение и списание'}).click();
  await page.getByRole('heading',{name:'Незавершённая отправка'}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'Незавершённая отправка'}).waitFor();
  await page.getByRole('button',{name:'Повторить прежний запрос'}).click();
  await page.getByRole('button',{name:'Проверить списание'}).waitFor();
  assert.equal(recorded.size,1);
  const records=writes.filter(write=>write.path.endsWith('/record-past'));
  assert.equal(records.length,2);assert.deepEqual(records[0].body,records[1].body);
  await page.getByRole('link',{name:'Журнал списаний',exact:true}).click();
  await page.locator('#studio-ledger').getByText('По журналу').waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:join(artifactDirectory,'gelios-ui-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.getByRole('button',{name:'Открыть меню'}).click();
  await page.getByLabel('Рабочее пространство').selectOption('terfit');
  await page.getByRole('heading',{name:'Обзор',exact:true}).waitFor();
  await page.getByRole('button',{name:'Открыть меню'}).click();
  await page.getByLabel('Рабочее пространство').selectOption('gelios');
  configured=false;
  await page.getByRole('button',{name:'Обновить данные'}).click();
  await page.getByText('CRM пока не подключена.',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS: modes, client creation, payment, preview, lost-response recovery, ledger, mobile, disabled CRM; no browser errors.');
} catch(error) {console.log('UI errors',errors);console.log(await page.locator('body').innerText());await page.screenshot({path:join(artifactDirectory,'gelios-ui-error.png'),fullPage:true});throw error;}
finally {await browser.close();}
