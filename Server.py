import http.server
import urllib.request
import urllib.error
import json
import os
import ssl
import uuid

ssl._create_default_https_context = ssl._create_unverified_context

# Ключи берутся из переменных окружения Render — никогда не хардкодь их здесь
GIGACHAT_KEY = os.environ.get('GIGACHAT_KEY', '')
PEXELS_KEY   = os.environ.get('PEXELS_KEY', '')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/landing.html':
            self._serve_html('landing.html')

        elif self.path == '/index.html':
            self._serve_html('index.html')

        elif self.path.startswith('/images/'):
            try:
                filename = os.path.join(BASE_DIR, self.path[1:])
                with open(filename, 'rb') as f:
                    img_data = f.read()
                if filename.endswith('.png'):
                    ctype = 'image/png'
                elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
                    ctype = 'image/jpeg'
                elif filename.endswith('.svg'):
                    ctype = 'image/svg+xml'
                else:
                    ctype = 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(img_data)))
                self.end_headers()
                self.wfile.write(img_data)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()

        elif self.path.startswith('/image?'):
            try:
                query = self.path.split('q=')[1] if 'q=' in self.path else 'business'
                query = urllib.request.unquote(query).split('&')[0]

                req = urllib.request.Request(
                    f'https://api.pexels.com/v1/search?query={urllib.request.quote(query)}&per_page=1&orientation=landscape',
                    headers={
                        'Authorization': PEXELS_KEY,
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json'
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())

                if data.get('photos') and len(data['photos']) > 0:
                    src = data['photos'][0]['src']
                    img_url = src.get('large2x') or src.get('large') or src.get('medium')
                    img_req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                        img_data = img_resp.read()
                        content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', str(len(img_data)))
                    self.end_headers()
                    self.wfile.write(img_data)
                else:
                    self.send_response(404)
                    self.end_headers()

            except Exception as e:
                print(f'Image error: {e}')
                self.send_response(500)
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self, fname):
        try:
            filepath = os.path.join(BASE_DIR, fname)
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/token':
            try:
                req = urllib.request.Request(
                    'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                    data=b'scope=GIGACHAT_API_PERS',
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                        'RqUID': str(uuid.uuid4()),
                        'Authorization': f'Basic {GIGACHAT_KEY}'
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        elif self.path == '/chat':
            try:
                length = int(self.headers['Content-Length'])
                body = json.loads(self.rfile.read(length))
                token = body['token']
                messages = body['messages']

                req = urllib.request.Request(
                    'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                    data=json.dumps({
                        'model': 'GigaChat-2',
                        'messages': messages,
                        'max_tokens': 800,
                        'temperature': 0.7
                    }).encode(),
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {token}'
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

    def log_message(self, format, *args):
        print(f'[{self.address_string()}] {format % args}')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f'Сервер запущен на порту {port}')
    httpd = http.server.HTTPServer(('0.0.0.0', port), Handler)
    httpd.serve_forever()
