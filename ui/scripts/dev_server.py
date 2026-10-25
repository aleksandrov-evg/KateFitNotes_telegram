"""Локальная раздача UI с прокси к API; без дополнительных зависимостей."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/environment.css':
            data = b"@import url('/src/stage-banner.css');" if os.environ.get('UI_ENVIRONMENT') == 'stage' else b''
            self.send_response(200)
            self.send_header('Content-Type', 'text/css')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith('/api/'):
            return self.proxy()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/'):
            return self.proxy()
        self.send_error(404)

    def do_PATCH(self):
        if self.path.startswith('/api/'):
            return self.proxy()
        self.send_error(404)

    def proxy(self):
        origin = os.environ.get('UI_API_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))) if self.command in {'POST', 'PATCH'} else None
        headers = {key: self.headers[key] for key in ('Authorization', 'Content-Type') if key in self.headers}
        request = Request(origin + self.path, data=body, headers=headers, method=self.command)
        try:
            response = urlopen(request, timeout=25)
        except HTTPError as error:
            response = error
        except URLError:
            self.send_error(502, 'API unavailable')
            return
        with response:
            data = response.read()
            self.send_response(response.status)
            self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)


if __name__ == '__main__':
    port = int(os.environ.get('UI_PORT', '5173'))
    directory = str(Path(__file__).resolve().parents[1])
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=directory))
    print(f'UI: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()
