import json

import httpx


class FakeStudioEvents:
    def __init__(self):
        self.events = {}
        self.unavailable = False
        self.fail_success_write = False
        self.lose_success_response = False

    def handle(self, request):
        path = request.url.path
        if not path.startswith("/rest/studioEvents"):
            return None
        if self.unavailable:
            raise httpx.ReadTimeout("audit unavailable", request=request)
        if request.method == "GET":
            event = self.events.get(path.rsplit("/", 1)[1])
            return httpx.Response(200, json={"data": {"studioEvent": event}}) if event else httpx.Response(404, json={"message": "Not found"})
        assert request.method == "POST"
        event = json.loads(request.content)
        if event["outcome"] == "SUCCESS" and self.fail_success_write:
            self.fail_success_write = False
            raise httpx.ReadTimeout("audit write failed", request=request)
        assert event["id"] not in self.events
        self.events[event["id"]] = event
        if event["outcome"] == "SUCCESS" and self.lose_success_response:
            self.lose_success_response = False
            raise httpx.ReadTimeout("audit response lost", request=request)
        return httpx.Response(201, json={"data": {"createStudioEvent": event}})
