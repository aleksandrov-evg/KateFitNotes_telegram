import {chooseOption} from './select_option.mjs';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const uiDirectory=fileURLToPath(new URL('../',import.meta.url));
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME ? {executablePath:process.env.UI_SMOKE_CHROME} : {})});
const page=await browser.newPage();
page.setDefaultTimeout(5000);
const errors=[],writes=[];
page.on('pageerror',error=>errors.push(error.message));
const id='00000000-0000-4000-8000-000000000001';
await page.route('http://gelios-ui.test/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  const json=body=>route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/v1/studio/auth/status')return json({configured:true,auth_mode:'api_key'});
  if(path.startsWith('/api/v1/studio/records/'))return json({items:path.endsWith('/clients')?[{id,name:{firstName:'Тест'}}]:path.endsWith('/products')?[{id,name:'Пакет',category:'GROUP_PACKAGE',isActive:true,visitsIncluded:8,price:{amountMicros:1000000000,currencyCode:'RUB'}}]:[],next_cursor:null});
  if(path==='/api/v1/studio/package-payments/confirm'){writes.push(route.request().postDataJSON());return json({success:true});}
  if(path==='/'||path.startsWith('/src/')){
    const body=await readFile(uiDirectory+(path==='/'?'index.html':path.slice(1)));
    return route.fulfill({body,contentType:path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':path.endsWith('.ttf')?'font/ttf':'text/html'});
  }
  return route.abort();
});
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test'));
try{
  await page.goto('http://gelios-ui.test/#gelios/packages');
  const form=page.locator('#studio-payment-form');
  await chooseOption(form.getByLabel('Клиент',{exact:true}),id);
  await chooseOption(form.getByLabel('Продукт',{exact:true}),id);
  await form.getByLabel('Когда оплачено').fill('2026-01-01T09:00');
  console.log(await page.evaluate(()=>({secureContext:isSecureContext,randomUUID:typeof crypto.randomUUID,getRandomValues:typeof crypto.getRandomValues})));
  await form.getByRole('button',{name:'Подтвердить оплату и создать пакет'}).click();
  if(process.argv.includes('--expect-failure')){
    assert.ok(errors.some(error=>error.includes('randomUUID')));
    assert.equal(await page.locator('#confirm').evaluate(dialog=>dialog.open),false);
    console.log('REPRODUCED:',errors);
  }else{
    await page.locator('#confirm').getByRole('heading',{name:'Подтвердить оплату',exact:true}).waitFor();
    await page.locator('#confirm').getByRole('button',{name:'Добавить',exact:true}).click();
    await page.locator('#confirm').waitFor({state:'hidden'});
    assert.equal(writes.length,1);
    assert.match(writes[0].idempotencyKey,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    assert.deepEqual(errors,[]);
    console.log('PASS: payment confirmation works on insecure HTTP origin without randomUUID.');
  }
}finally{await browser.close();}
