from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from src.Kate_Fit_Notes.api.studio import StudioCrm
from tests.test_api import API_SETTINGS, FakeApiRepo
from tests.test_studio_api import SETTINGS

EXPENSE_ID = '70000000-0000-4000-8000-000000000001'
EXPENSE = {'name': 'Аренда', 'amountMinor': '123456', 'category': 'RENT', 'description': None,
           'costType': 'FIXED', 'accrualMonth': '2026-10', 'paidOn': '2026-11-02'}


@pytest.fixture
def expenses_app():
    calls = []
    state = {'timeout': False, 'malformed': False}

    def handle(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer server-api-key'
        path = request.url.path
        if path == '/s/studio/expenses/save':
            if state['timeout']:
                raise httpx.ReadTimeout('lost committed response', request=request)
            body = json.loads(request.content)
            operation = 'updateStudioExpense' if 'expenseId' in body else 'createStudioExpense'
            return httpx.Response(200, json={} if state['malformed'] else {operation: {'id': EXPENSE_ID}})
        if path == '/s/studio/expenses/report':
            return httpx.Response(200, json={'accruedExpenseMinor': '123456'})
        if path == f'/rest/studioExpenses/{EXPENSE_ID}':
            if request.method == 'DELETE':
                if state['timeout']:
                    raise httpx.ReadTimeout('lost committed delete', request=request)
                return httpx.Response(200, json={'data': {'deleteStudioExpense': {'id': EXPENSE_ID}}})
            return httpx.Response(200, json={'data': {'studioExpense': {'id': EXPENSE_ID}}})
        if path in {'/rest/studioExpenses', '/rest/studioPayments'}:
            resource = path.split('/')[-1]
            return httpx.Response(200, json={'data': {resource: [{'id': EXPENSE_ID}]}, 'pageInfo': {'hasNextPage': True, 'endCursor': 'next'}})
        raise AssertionError(path)

    studio = StudioCrm(SETTINGS, httpx.Client(transport=httpx.MockTransport(handle)))
    with TestClient(create_app(API_SETTINGS, FakeApiRepo(), studio)) as client:
        token = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'secret'}).json()['access_token']
        yield client, calls, state, {'Authorization': f'Bearer {token}'}


def test_authorization_before_any_crm_write(expenses_app):
    client, calls, _, _ = expenses_app
    assert client.post('/api/v1/studio/expenses/save', json=EXPENSE).status_code == 401
    assert client.delete(f'/api/v1/studio/expenses/{EXPENSE_ID}').status_code == 401
    assert client.post('/api/v1/studio/expenses/report', json={'month': '2026-10'}).status_code == 401
    assert calls == []


@pytest.mark.parametrize('extra', [{'amountMinor': '0'}, {'amountMinor': 123}, {'amountMinor': '1.2'}, {'amountMinor': '-1'}, {'amountMinor': '1000000000000'}, {'category': 'BAD'}, {'costType': 'BAD'}, {'accrualMonth': '0000-01'}, {'paidOn': '2026-02-30'}, {'name': '   '}, {'apiKey': 'secret'}, {'expenseId': 'bad'}])
def test_expense_validation_before_forward(expenses_app, extra):
    client, calls, _, headers = expenses_app
    assert client.post('/api/v1/studio/expenses/save', json={**EXPENSE, **extra}, headers=headers).status_code == 422
    assert calls == []


def test_create_update_and_unpaid_expense_forward_exact_contract(expenses_app):
    client, calls, _, headers = expenses_app
    for body in (EXPENSE, {**EXPENSE, 'expenseId': EXPENSE_ID, 'paidOn': None}):
        response = client.post('/api/v1/studio/expenses/save', json=body, headers=headers)
        assert response.status_code == 200
        assert response.json() == {'id': EXPENSE_ID}
        assert json.loads(calls[-1].content) == body


@pytest.mark.parametrize('state_key', ['timeout', 'malformed'])
def test_unknown_save_never_retries(expenses_app, state_key):
    client, calls, state, headers = expenses_app
    state[state_key] = True
    response = client.post('/api/v1/studio/expenses/save', json=EXPENSE, headers=headers)
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'EXPENSE_OUTCOME_UNKNOWN'
    assert len(calls) == 1


def test_delete_checks_record_then_soft_deletes(expenses_app):
    client, calls, state, headers = expenses_app
    response = client.delete(f'/api/v1/studio/expenses/{EXPENSE_ID}', headers=headers)
    assert response.json() == {'id': EXPENSE_ID, 'deleted': True}
    assert [call.method for call in calls] == ['GET', 'DELETE']
    state['timeout'] = True
    response = client.delete(f'/api/v1/studio/expenses/{EXPENSE_ID}', headers=headers)
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'EXPENSE_OUTCOME_UNKNOWN'
    assert [call.method for call in calls] == ['GET', 'DELETE', 'GET', 'DELETE']


def test_new_resources_page_and_report(expenses_app):
    client, calls, _, headers = expenses_app
    for resource in ('payments', 'expenses'):
        response = client.get(f'/api/v1/studio/records/{resource}?cursor=previous', headers=headers)
        assert response.json() == {'items': [{'id': EXPENSE_ID}], 'next_cursor': 'next'}
        assert calls[-1].url.params['starting_after'] == 'previous'
    response = client.post('/api/v1/studio/expenses/report', json={'month': '2026-10'}, headers=headers)
    assert response.json() == {'accruedExpenseMinor': '123456'}
    assert json.loads(calls[-1].content) == {'month': '2026-10'}
    assert client.post('/api/v1/studio/expenses/report', json={'month': '2026-13'}, headers=headers).status_code == 422
