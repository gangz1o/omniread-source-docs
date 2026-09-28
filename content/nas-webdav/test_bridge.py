import base64
import http.client
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote
from xml.sax.saxutils import escape
from bridge import Bridge
from webdav_client import AdapterError, WebDAV, chapters

TEXT = '序言\n这是原创联调内容。\n第一章 来信\n窗外下起了雨。\n第二章 晴天\n云散了。\n'
PASSWORD = 'fixture-password'
KEY = 'fixture-bridge-key-123456'


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, value, status=200, headers=None):
        self.send_response(status)
        self.send_header('Content-Length', str(len(value)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(value)
    def authorized(self):
        expected = 'Basic ' + base64.b64encode(('reader:' + PASSWORD).encode()).decode()
        self.server.seen.append((self.command, self.path))
        if self.headers.get('Authorization') != expected:
            self.reply(b'', 401)
            return False
        return True
    def do_PROPFIND(self):
        if not self.authorized(): return
        if self.headers.get('Depth') != '1':
            self.reply(b'', 400)
            return
        entries = [('/books/', True), ('/books/云间 小记.txt', False), ('/books/子目录/', True), ('/books/image.jpg', False)] if self.path == '/books/' else [('/books/子目录/', True), ('/books/子目录/远山&月.txt', False)]
        body = '<d:multistatus xmlns:d="DAV:">' + ''.join('<d:response><d:href>' + escape(path) + '</d:href><d:propstat><d:prop><d:resourcetype>' + ('<d:collection/>' if folder else '') + '</d:resourcetype></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>' for path, folder in entries) + '</d:multistatus>'
        self.reply(body.encode(), 207)
    def do_GET(self):
        if not self.authorized(): return
        if self.server.reject_reads:
            self.reply(b'', 401)
        elif self.path == '/books/redirect.txt':
            self.reply(b'', 302, {'Location': '/private.txt'})
        else:
            encoding = 'gb18030' if '远山' in unquote(self.path) else 'utf-8-sig'
            self.reply(TEXT.encode(encoding))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.nas = HTTPServer(('127.0.0.1', 0), Fixture)
        self.nas.seen, self.nas.reject_reads = [], False
        self.worker = threading.Thread(target=self.nas.serve_forever, daemon=True)
        self.worker.start()
        self.dav = WebDAV('http://127.0.0.1:' + str(self.nas.server_port) + '/books/', 'reader', PASSWORD, allow_http=True)
        self.app = Bridge(('127.0.0.1', 0), 'https://library.example', KEY, self.dav)
        self.app_worker = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.app_worker.start()
    def tearDown(self):
        self.app.shutdown(); self.app.server_close(); self.app_worker.join()
        self.nas.shutdown(); self.nas.server_close(); self.worker.join()
    def request(self, method, path, body=None, token=None):
        c = http.client.HTTPConnection('127.0.0.1', self.app.server_port, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        c.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = c.getresponse(); status, data = r.status, r.read(); c.close()
        return status, json.loads(data) if data else None
    def login(self):
        status, result = self.request('POST', '/nas/login', {'apiKey': KEY})
        self.assertEqual(status, 200)
        return result['accessToken']
    def test_end_to_end_source_search_toc_content(self):
        status, source = self.request('GET', '/source.json')
        self.assertEqual(status, 200)
        self.assertEqual(source['omnireadLogin']['loginUrl'], 'https://library.example/nas/login')
        self.assertNotIn(PASSWORD, json.dumps(source)); self.assertNotIn(KEY, json.dumps(source))
        self.assertEqual(self.request('GET', '/nas/search')[0], 401)
        token = self.login()
        listing = self.request('GET', '/nas/search', token=token)[1]['books']
        self.assertEqual(len(listing), 2)
        self.assertEqual(self.request('GET', '/nas/search?page=2', token=token)[1]['books'], [])
        self.assertEqual(self.request('GET', '/nas/search?page=0', token=token)[0], 400)
        for book in listing:
            detail = self.request('GET', book['url'], token=token)[1]
            toc = self.request('GET', detail['toc'], token=token)[1]
            self.assertEqual(len(toc['chapters']), 3)
            self.assertEqual(toc['next'], '')
            content = ''.join(self.request('GET', item['url'], token=token)[1]['text'] for item in toc['chapters'])
            self.assertEqual(content, TEXT)
        self.assertEqual(sum(method == 'PROPFIND' for method, _ in self.nas.seen), 2)
        self.assertTrue(all(method in ('GET', 'PROPFIND') for method, _ in self.nas.seen))
    def test_auth_expiry_and_upstream_failure(self):
        self.assertEqual(self.request('POST', '/nas/login', {'apiKey': 'wrong'})[0], 401)
        self.assertEqual(self.request('POST', '/nas/login', [KEY])[0], 401)
        token = self.login()
        self.assertEqual(self.request('GET', '/nas/session', token=token)[0], 204)
        book = self.request('GET', '/nas/explore', token=token)[1]['books'][0]
        self.nas.reject_reads = True
        self.assertEqual(self.request('GET', book['toc'], token=token), (502, {'error': 'webdav_auth_failed'}))
        self.assertEqual(self.request('GET', '/nas/session', token=token)[0], 204)
        self.app.tokens[token] = time.monotonic() - 1
        self.assertEqual(self.request('GET', '/nas/session', token=token)[0], 401)
    def test_scoping_redirects_xml_and_response_limit(self):
        for href in ('https://evil.example/file.txt', '/private.txt', '/books/%2e%2e/private.txt', '/books/%252e%252e/private.txt', '/books/a.txt?secret=1', '//evil.example/a.txt'):
            with self.assertRaises(AdapterError): self.dav.safe_url(href, self.dav.root)
        with self.assertRaises(AdapterError): self.dav.request(self.dav.root + 'redirect.txt', 'GET', 100)
        self.assertNotIn(('GET', '/private.txt'), self.nas.seen)
        with self.assertRaises(AdapterError): self.dav.request(self.dav.root + 'small.txt', 'GET', 3)
        with patch.object(self.dav, 'request', return_value=b'<!DOCTYPE x [<!ENTITY a "bad">]><x/>'):
            with self.assertRaises(AdapterError): self.dav.list_directory(self.dav.root)
    def test_long_text_and_toc_pagination(self):
        value = '第一章 开始\n' + '甲' * 35000 + '\n第二章 继续\n尾声'
        parts = chapters(value)
        self.assertEqual(''.join(x['text'] for x in parts), value)
        self.assertTrue(all(len(x['text']) <= 12000 for x in parts))
        token = self.login(); identity = next(iter(self.app.books))
        with patch.object(self.app, 'book_chapters', return_value=[{'title': str(i), 'text': str(i)} for i in range(201)]):
            toc = self.request('GET', '/nas/books/' + identity + '/chapters', token=token)[1]
            self.assertEqual(len(toc['chapters']), 200)
            last = self.request('GET', toc['next'], token=token)[1]
            self.assertEqual(len(last['chapters']), 1)
            self.assertEqual(last['next'], '')
    def test_encoding_and_collection_validation(self):
        for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
            with patch.object(self.dav, 'request', return_value=TEXT.encode(encoding)):
                self.assertEqual(self.dav.read_text(self.dav.root + 'book.txt'), TEXT)
        self.assertEqual(self.dav.safe_url(self.dav.root.rstrip('/'), self.dav.root), self.dav.root)
        xml = b'<d:multistatus xmlns:d="DAV:"><d:response><d:href>/books/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop><d:status>HTTP/1.1 403 Forbidden</d:status></d:propstat></d:response></d:multistatus>'
        with patch.object(self.dav, 'request', return_value=xml):
            with self.assertRaises(AdapterError): self.dav.list_directory(self.dav.root)

    def test_stable_ids_and_invalid_configuration(self):
        self.assertEqual(set(self.dav.scan()), set(self.app.books))
        with self.assertRaises(AdapterError): WebDAV('http://nas.example/books/', 'u', 'p')
        with self.assertRaises(AdapterError): Bridge(('127.0.0.1', 0), 'http://library.example', KEY, self.dav)
        with self.assertRaises(AdapterError): Bridge(('127.0.0.1', 0), 'https://library.example', 'short', self.dav)


if __name__ == '__main__': unittest.main()
