import assert from 'node:assert/strict';
import {today} from '../src/domain.js';

const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.UI_SMOKE_CHROME?{executablePath:process.env.UI_SMOKE_CHROME}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
let bookings=[{id:12,date:today(),time:'17:00',type_train_id:1,client:1,participants:[1],accounting_id:2,price:4500,spend:1500}];
const deletes=[],errors=[];
let loseResponse=true;
page.on('pageerror',error=>errors.push(error.message));
await page.addInitScript(()=>sessionStorage.setItem('katefit-token','test-session'));
await page.route('**/api/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(request.method()==='DELETE'){
    assert.equal(path,'/api/v1/bookings/12');deletes.push(path);bookings=[];
    if(loseResponse){loseResponse=false;return reply({detail:'Ответ потерян. Повторите удаление той же записи.'},502);}
    return reply({deleted:false});
  }
  if(path==='/api/v1/bookings')return reply({items:bookings,total:bookings.length});
  if(path==='/api/v1/clients')return reply({items:[{id:1,name:'Сергей',surname:'Тестовый',phone:'9210000000'}],total:1});
  if(path==='/api/v1/prepaid')return reply({items:[],total:0});
  if(path==='/api/v1/train-types')return reply([{id:1,type_train:'Гамак',group_train:false}]);
  if(path==='/api/v1/reports/monthly')return reply([]);
  throw new Error('Unexpected route '+path);
});
try{
  await page.goto((process.env.UI_SMOKE_URL||'http://127.0.0.1:5184/')+'#schedule');
  await page.locator('[data-booking="12"]').click();
  const modal=page.locator('#confirm');
  await modal.getByRole('button',{name:'Удалить тренировку',exact:true}).click();
  await modal.getByText(/Посещение вернётся/).waitFor();
  await modal.getByRole('button',{name:'Отменить',exact:true}).click();
  assert.equal(deletes.length,0);
  await page.locator('[data-booking="12"]').click();
  await modal.getByRole('button',{name:'Удалить тренировку',exact:true}).click();
  await modal.getByRole('button',{name:'Удалить тренировку',exact:true}).click();
  await modal.getByRole('alert').getByText(/Ответ потерян/).waitFor();
  await modal.getByRole('button',{name:'Удалить тренировку',exact:true}).click();
  await modal.waitFor({state:'hidden'});
  assert.equal(await page.locator('[data-booking="12"]').count(),0);
  assert.deepEqual(deletes,['/api/v1/bookings/12','/api/v1/bookings/12']);
  assert.deepEqual(errors,[]);
  console.log('PASS: explicit delete confirmation, cancellation without writes, lost response and safe same-ID retry, refreshed schedule.');
}finally{await browser.close();}
