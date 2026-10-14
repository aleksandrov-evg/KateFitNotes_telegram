import {chooseOption} from './select_option.mjs';
import assert from 'node:assert/strict';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {today} from '../src/domain.js';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const origin=process.env.UI_SMOKE_URL||'http://127.0.0.1:5184/';
const artifacts=process.env.UI_SMOKE_ARTIFACT_DIR||tmpdir();
const data={
  clients:[{id:'client-1',name:{firstName:'Мария',lastName:'Александрова'},phones:{primaryPhoneCallingCode:'+7',primaryPhoneNumber:'9211234567'},emails:{primaryEmail:'maria@example.com'}},{id:'client-2',name:{firstName:'Анна',lastName:'Иванова'},phones:{primaryPhoneNumber:'9997654321'},emails:{primaryEmail:'anna@example.com'}}],
  products:[{id:'product-1',name:'Группа на реформере · 8 занятий',category:'GROUP_PACKAGE',sessionFormat:'GROUP_REFORMER',isActive:true,visitsIncluded:8,validityDays:30,durationMinutes:55,price:{amountMicros:8800000000,currencyCode:'RUB'}}],
  packages:[{id:'package-1',personId:'client-1',productId:'product-1',name:'Группа на реформере · 8 занятий',status:'ACTIVE',visitsAvailable:2,visitsGranted:8,visitsConsumed:5,visitsReserved:1,expiresOn:'2027-12-31'}],
  sessions:[{id:'session-1',name:'Группа на реформере',sessionFormat:'GROUP_REFORMER',startsAt:today()+'T09:00:00+03:00',endsAt:today()+'T09:55:00+03:00',status:'COMPLETED',capacity:4}],
  bookings:[{id:'booking-1',personId:'client-1',membershipId:'package-1',classSessionId:'session-1',status:'ATTENDED',recordedAt:today()+'T09:55:00+03:00'}],
  transactions:[{id:'transaction-1',membershipId:'package-1',transactionType:'CONSUME',visitDelta:-1,occurredAt:today()+'T09:55:00+03:00',reason:'Посещение групповой тренировки'}],events:[],
};
await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  assert.equal(route.request().method(),'GET');
  let body;
  if(path.endsWith('/studio/auth/status'))body={configured:true,auth_mode:'api_key'};
  else if(path.includes('/studio/records/'))body={items:data[path.split('/').at(-1)],next_cursor:null};
  else if(['/api/v1/train-types','/api/v1/reports/monthly'].includes(path))body=[];
  else if(['/api/v1/clients','/api/v1/bookings','/api/v1/prepaid'].includes(path))body={items:[],total:0};
  else throw new Error('Unexpected request '+path);
  await route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','design-test'));
const routes={overview:'Обзор Gelios',clients:'Клиенты Gelios',packages:'Пакеты и оплата',attendance:'Внести прошедшую тренировку',bookings:'Посещения Gelios',transactions:'Журнал списаний',calendar:'Календарь тренировок'};
const noPageOverflow=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Page must not overflow horizontally');
try{
  for(const width of [1440,1024,768,390]){
    await page.setViewportSize({width,height:1000});
    for(const [route,title] of Object.entries(routes)){
      await page.goto(origin+'#gelios/'+route);
      await page.getByRole('heading',{name:title,exact:true}).waitFor();
      await page.evaluate(()=>document.fonts.ready);
      await noPageOverflow();
      assert.equal(await page.locator('.sidebar').evaluate(element=>getComputedStyle(element).backgroundColor),'rgb(24, 43, 39)');
      if(width===1440)assert.equal((await page.locator('.sidebar').boundingBox()).width,232);
      if(route==='calendar')assert.equal(await page.locator('.calendar-free-slot').first().evaluate(element=>getComputedStyle(element).borderRadius),'0px');
      if(route==='packages'){
        const form=page.locator('#studio-payment-form');
        const picker=form.getByRole('combobox',{name:'Клиент',exact:true});
        await picker.fill('м');
        assert.equal(await page.locator('#'+await picker.getAttribute('aria-controls')).getByRole('option').count(),1);
        await picker.fill('АЛЕКС');
        const menu=page.locator('#'+await picker.getAttribute('aria-controls'));
        assert.equal(await menu.getByRole('option').count(),1);
        await page.screenshot({path:join(artifacts,`gelios-client-search-${width}.png`)});
        await picker.fill('921123');
        assert.equal(await menu.getByRole('option').count(),1);
        await picker.fill('maria@');
        assert.equal(await menu.getByRole('option').count(),1);
        await picker.press('ArrowDown');await picker.press('Enter');
        assert.equal(await form.locator('select[name=personId]').inputValue(),'client-1');
        await picker.fill('несуществующий');
        await menu.getByText('Ничего не найдено',{exact:true}).waitFor();
        assert.equal(await form.locator('select[name=personId]').inputValue(),'');
        assert.equal(await picker.evaluate(element=>element.checkValidity()),false);
        await picker.press('Escape');
        assert.equal(await picker.getAttribute('aria-expanded'),'false');
        await chooseOption(form.getByLabel('Клиент',{exact:true}),'client-1');
        await chooseOption(form.getByLabel('Продукт',{exact:true}),'product-1');
        await chooseOption(form.getByLabel('Способ оплаты'),'SBP');
        await page.locator('.studio-payment-summary').getByText('Мария Александрова',{exact:true}).waitFor();
        assert.equal(await page.locator('.studio-summary-method').textContent(),'СБП');
        const layout=await page.locator('.studio-payment-layout').boundingBox();
        const summary=await page.locator('.studio-payment-summary').boundingBox();
        if(width>=1024)assert.ok(summary.x>layout.x+layout.width/2);
        else assert.ok(summary.y>(await form.boundingBox()).y);
      }
      await page.screenshot({path:join(artifacts,`gelios-v2-${route}-${width}.png`),fullPage:true});
    }
    await page.getByRole('button',{name:'+ Новая тренировка',exact:true}).click();
    await page.locator('#calendar-create-form').waitFor();
    await noPageOverflow();
    const modal=await page.locator('#confirm').boundingBox();
    assert.ok(modal.x>=0&&modal.x+modal.width<=width);
    await page.screenshot({path:join(artifacts,`gelios-v2-create-${width}.png`)});
    await page.locator('#dialog-cancel').click();
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(origin+'#overview');
  await page.getByRole('heading',{name:'Обзор',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>document.body.classList.contains('studio-mode')),false);
  assert.equal(await page.locator('.sidebar').evaluate(element=>getComputedStyle(element).backgroundColor),'rgb(248, 248, 248)');
  assert.deepEqual(errors,[]);
  console.log('PASS: seven Gelios screens at desktop/mobile sizes, payment summary, calendar dialog, original Terfit theme; no horizontal overflow or browser errors.');
}finally{await browser.close();}
