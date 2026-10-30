from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import SETTINGS

TRAINER='70000000-0000-4000-8000-000000000001'
RATE='70000000-0000-4000-8000-000000000002'
SESSION='70000000-0000-4000-8000-000000000003'
KEY='70000000-0000-4000-8000-000000000004'
ASSIGNMENT='70000000-0000-4000-8000-000000000005'
CLOSE={'classSessionId':SESSION,'trainerId':TRAINER,'requestKey':KEY,'previewOnly':True}

@pytest.fixture
def payroll_app():
    calls=[]
    state={'records':{},'assignments':[], 'timeout':False,'malformed':False}
    def handle(request):
        calls.append(request)
        assert request.headers['authorization']=='Bearer server-api-key'
        path=request.url.path
        if path=='/rest/studioEvents' and request.method=='POST':
            return httpx.Response(200,json={'data':{'createStudioEvent':{'id':json.loads(request.content)['id']}}})
        if path.startswith('/rest/'):
            parts=path.split('/');plural=parts[2]
            singular={'studioTrainers':'studioTrainer','trainerPayRates':'trainerPayRate','trainerRateAssignments':'trainerRateAssignment','studioEvents':'studioEvent'}[plural]
            if request.method=='GET':
                if len(parts)==3:return httpx.Response(200,json={'data':{plural:state['assignments']},'pageInfo':{'hasNextPage':False}})
                row=state['records'].get(parts[3])
                return httpx.Response(200,json={'data':{singular:row}}) if row else httpx.Response(404,json={})
            body=json.loads(request.content);record_id=parts[3] if len(parts)==4 else body['id']
            operation=('update' if request.method=='PATCH' else 'create')+singular[0].upper()+singular[1:]
            return httpx.Response(200,json={'data':{operation:{'id':record_id}}})
        if path.startswith('/s/studio/'):
            if state['timeout']:raise httpx.ReadTimeout('lost response',request=request)
            body=json.loads(request.content)
            if state['malformed']:return httpx.Response(200,json={'success':True})
            if body.get('previewOnly'):return httpx.Response(200,json={'success':True,'preview':True,'snapshot':{'amount':{'amountMicros':1650000000}},'previewToken':'a'*64,'revision':1})
            return httpx.Response(200,json={'success':True,'preview':False,'entryId':KEY,'amountMicros':1650000000,'duplicate':False})
        raise AssertionError(path)
    studio=StudioCrm(SETTINGS,httpx.Client(transport=httpx.MockTransport(handle)))
    with TestClient(create_app(API_SETTINGS,FakeApiRepo(),studio)) as client:
        token=client.post('/api/v1/auth/login',json={'username':'admin','password':'secret'}).json()['access_token']
        yield client,calls,state,{'Authorization':f'Bearer {token}'}

def test_payroll_requires_auth_before_crm_access(payroll_app):
    client,calls,_,_=payroll_app
    for path,body in [('compensation/close',CLOSE),('trainers/save',{'trainerId':TRAINER,'name':'Анна'}),('trainer-rates/publish',{'payRateId':RATE})]:
        assert client.post('/api/v1/studio/'+path,json=body).status_code==401
    assert not calls

@pytest.mark.parametrize('extra',[{'previewOnly':False},{'previewToken':'bad'},{'amountMicros':1},{'requestKey':'bad'},{'previousEntryId':KEY},{'attendanceCorrections':[{'bookingId':KEY,'status':'ATTENDED'},{'bookingId':KEY,'status':'NO_SHOW'}]}])
def test_bad_payroll_input_never_reaches_crm(payroll_app,extra):
    client,calls,_,headers=payroll_app
    assert client.post('/api/v1/studio/compensation/close',json={**CLOSE,**extra},headers=headers).status_code==422
    assert not calls

def test_preview_and_confirmation_keep_same_key_and_token(payroll_app):
    client,calls,_,headers=payroll_app
    response=client.post('/api/v1/studio/compensation/close',json=CLOSE,headers=headers)
    assert response.status_code==200
    confirmed={**CLOSE,'previewOnly':False,'previewToken':response.json()['previewToken']}
    assert client.post('/api/v1/studio/compensation/close',json=confirmed,headers=headers).status_code==200
    assert len(calls)==2
    assert json.loads(calls[-1].content)=={**confirmed,'reason':'','attendanceCorrections':[]}

@pytest.mark.parametrize('mode',['timeout','malformed'])
def test_unknown_confirmation_does_not_retry_and_is_audited(payroll_app,mode):
    client,calls,state,headers=payroll_app;state[mode]=True
    response=client.post('/api/v1/studio/compensation/close',json={**CLOSE,'previewOnly':False,'previewToken':'a'*64},headers=headers)
    assert response.status_code==502
    assert len([row for row in calls if row.url.path=='/s/studio/compensation/close'])==1
    event=json.loads(calls[-1].content)
    assert event['idempotencyKey']==KEY
    assert json.loads(event['details'])['execution']=='UNKNOWN'

def test_rates_have_four_exact_configurable_steps_and_published_versions_are_immutable(payroll_app):
    client,calls,state,headers=payroll_app
    body={'rateId':RATE,'name':'Группа','version':2,'amountsMinor':['0','110050','130000','210000']}
    assert client.post('/api/v1/studio/trainer-rates/save',json=body,headers=headers).status_code==200
    forwarded=json.loads(calls[-1].content)
    assert forwarded['amountFor1']=={'amountMicros':0,'currencyCode':'RUB'}
    assert forwarded['amountFor2']['amountMicros']==1100500000
    assert forwarded['amountFor4']['amountMicros']==2100000000
    state['records'][RATE]={'id':RATE,'publishedSnapshot':'{}'}
    count=len(calls)
    assert client.post('/api/v1/studio/trainer-rates/save',json=body,headers=headers).status_code==409
    assert len(calls)==count+1
    assert calls[-1].method=='GET'

def test_assignment_overlap_is_rejected_but_touching_boundaries_are_allowed(payroll_app):
    client,calls,state,headers=payroll_app
    state['records']={TRAINER:{'id':TRAINER,'name':'Анна','active':True},RATE:{'id':RATE,'name':'Тариф','publishedSnapshot':'{}'}}
    state['assignments']=[{'id':KEY,'trainerId':TRAINER,'validFrom':'2026-10-01T00:00:00+03:00','validUntil':'2026-11-01T00:00:00+03:00'}]
    body={'assignmentId':ASSIGNMENT,'trainerId':TRAINER,'payRateId':RATE,'validFrom':'2026-10-31T00:00:00+03:00'}
    assert client.post('/api/v1/studio/trainer-assignments/save',json=body,headers=headers).status_code==409
    assert all(row.method=='GET' for row in calls)
    assert client.post('/api/v1/studio/trainer-assignments/save',json={**body,'validFrom':'2026-11-01T00:00:00+03:00'},headers=headers).status_code==200
    assert calls[-1].method=='POST'
