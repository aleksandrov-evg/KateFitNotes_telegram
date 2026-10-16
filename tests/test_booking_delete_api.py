from fastapi.testclient import TestClient

from src.Kate_Fit_Notes.api.app import create_app
from tests.test_api import API_SETTINGS, FakeApiRepo


class DeleteRepo(FakeApiRepo):
    def __init__(self):
        super().__init__()
        self.ids = {12}
        self.calls = []

    def delete_booking(self, booking_id):
        self.calls.append(booking_id)
        if booking_id not in self.ids:
            return False
        self.ids.remove(booking_id)
        return True


def test_delete_requires_login_and_replays_safely():
    repo = DeleteRepo()
    with TestClient(create_app(API_SETTINGS, repo)) as browser:
        assert browser.delete('/api/v1/bookings/12').status_code == 401
        assert repo.calls == []
        token = browser.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'secret'}).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        assert browser.delete('/api/v1/bookings/12', headers=headers).json() == {'deleted': True}
        assert browser.delete('/api/v1/bookings/12', headers=headers).json() == {'deleted': False}
        assert repo.ids == set()
        for invalid_id in ['0', '-1', 'not-a-number']:
            assert browser.delete('/api/v1/bookings/' + invalid_id, headers=headers).status_code == 422
        assert repo.calls == [12, 12]
