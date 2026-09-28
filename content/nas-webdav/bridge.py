#!/usr/bin/env python3
"""Single-library WebDAV → OmniRead TXT source. Python 3 standard library only."""
import argparse
import getpass
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit
from webdav_client import AdapterError, WebDAV, chapters


class Bridge(HTTPServer):
    def __init__(self, address, base_url, api_key, dav):
        p = urlsplit(base_url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
            raise AdapterError('public_base_requires_https_origin')
        if len(api_key.encode()) < 16 or len(api_key.encode()) > 4096 or api_key != api_key.strip():
            raise AdapterError('bridge_key_must_be_16_to_4096_bytes_without_outer_whitespace')
        self.base_url, self.api_key, self.dav = base_url.rstrip('/'), api_key, dav
        self.books = dav.scan()  # Startup snapshot; never scan the NAS during search.
        self.tokens, self.attempts = {}, []
        self.cached = None  # One book, at most 16 MiB input, retained for five minutes.
        super().__init__(address, Handler)

    def source(self):
        data = (Path(__file__).parent / 'source.json').read_text()
        return json.loads(data.replace('https://your-bridge.example', self.base_url))

    def book_chapters(self, identity):
        now = time.monotonic()
        if self.cached and self.cached[0] == identity and self.cached[1] > now:
            return self.cached[2]
        self.cached = None
        result = chapters(self.dav.read_text(self.books[identity]['dav_url']))
        self.cached = (identity, now + 300, result)
        return result


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        pass

    def send_json(self, data, status=200):
        body = b'' if status == 204 else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def logged_in(self):
        now = time.monotonic()
        self.server.tokens = {token: expiry for token, expiry in self.server.tokens.items() if expiry > now}
        header = self.headers.get('Authorization', '')
        return header.startswith('Bearer ') and header[7:] in self.server.tokens

    def do_POST(self):
        if urlsplit(self.path).path != '/nas/login':
            self.send_json({'error': 'not_found'}, 404)
            return
        now = time.monotonic()
        self.server.attempts = [attempt for attempt in self.server.attempts if attempt > now - 60]
        if len(self.server.attempts) >= 30:
            self.send_json({'error': 'login_rate_limited'}, 429)
            return
        self.server.attempts.append(now)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32768 or self.headers.get('Transfer-Encoding'):
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            key = data.get('apiKey') if isinstance(data, dict) else None
            if not isinstance(key, str) or not hmac.compare_digest(key.encode(), self.server.api_key.encode()):
                self.send_json({'error': 'invalid_credentials'}, 401)
                return
        except (ValueError, OSError):
            self.send_json({'error': 'invalid_request'}, 400)
            return
        self.logged_in()  # Prune expired sessions.
        if len(self.server.tokens) >= 100:
            self.send_json({'error': 'session_limit'}, 429)
            return
        token = secrets.token_urlsafe(32)
        self.server.tokens[token] = now + 3600
        self.send_json({'accessToken': token, 'expiresIn': 3600})

    def summary(self, book):
        url = '/nas/books/' + book['id']
        return {'title': book['title'], 'author': '', 'intro': '来自你的 NAS · TXT 小说', 'url': url, 'toc': url + '/chapters'}

    def do_GET(self):
        try:
            self.route()
        except AdapterError as error:
            self.send_json({'error': str(error)}, 502)
        except (ValueError, UnicodeError):
            self.send_json({'error': 'invalid_request'}, 400)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def route(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/source.json':
            self.send_json(self.server.source())
            return
        if not self.logged_in():
            self.send_json({'error': 'authentication_required'}, 401)
            return
        if parsed.path == '/nas/session':
            self.send_json(None, 204)
            return
        query = parse_qs(parsed.query)
        page = int(query.get('page', ['1'])[0])
        if not 1 <= page <= 100000:
            raise ValueError()
        if parsed.path in ('/nas/search', '/nas/explore'):
            keyword = query.get('q', [''])[0].casefold()
            books = sorted((book for book in self.server.books.values() if keyword in book['title'].casefold()), key=lambda b: (b['title'].casefold(), b['id']))
            self.send_json({'books': [self.summary(b) for b in books[(page-1)*50:page*50]]})
            return
        match = re.fullmatch(r'/nas/books/([a-f0-9]{24})(?:/(chapters|chapter/([0-9]+)))?', parsed.path)
        if not match or match[1] not in self.server.books:
            self.send_json({'error': 'not_found'}, 404)
            return
        book = self.server.books[match[1]]
        if match[2] is None:
            self.send_json(self.summary(book))
            return
        content = self.server.book_chapters(match[1])
        if match[2] == 'chapters':
            offset = (page-1)*200
            self.send_json({'chapters': [{'title': item['title'], 'url': '/nas/books/' + match[1] + '/chapter/' + str(index)} for index, item in enumerate(content[offset:offset+200], offset)], 'next': parsed.path + '?page=' + str(page+1) if offset+200 < len(content) else ''})
            return
        index = int(match[3])
        if index >= len(content):
            self.send_json({'error': 'not_found'}, 404)
            return
        self.send_json({'text': content[index]['text']})


def secret(name, prompt):
    if os.environ.get(name + '_FILE'):
        return Path(os.environ[name + '_FILE']).read_text().rstrip('\r\n')
    return os.environ.get(name) or getpass.getpass(prompt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--allow-http-webdav', action='store_true', help='Only for a trusted private network or local fixture')
    args = parser.parse_args()
    try:
        dav = WebDAV(os.environ['WEBDAV_URL'], os.environ['WEBDAV_USERNAME'], secret('WEBDAV_PASSWORD', 'NAS 密码（不回显）：'), args.allow_http_webdav)
        server = Bridge((args.bind, args.port), os.environ['PUBLIC_BASE_URL'], secret('BRIDGE_API_KEY', '设置书源访问密钥（至少 16 字节，不回显）：'), dav)
    except (KeyError, ValueError, OSError, AdapterError):
        parser.exit(1, '启动失败：检查必填配置、HTTPS 证书、凭据、WebDAV 路径及目录规模。敏感配置未输出。\n')
    print('索引完成：' + str(len(server.books)) + ' 本 TXT。通过配置的 HTTPS 地址获取 /source.json。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
