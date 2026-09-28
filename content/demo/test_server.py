import http.client
import json
import threading
import unittest
from server import DemoServer


class DemoProtocolTests(unittest.TestCase):
    def setUp(self):
        self.server = DemoServer(("127.0.0.1", 0), "https://demo.example")
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def request(self, method, path, body=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request(method, path, json.dumps(body) if body else None, headers)
        response = connection.getresponse()
        status, data = response.status, response.read()
        connection.close()
        return status, json.loads(data) if data else None

    def test_sources_pagination_and_video(self):
        status, sources = self.request("GET", "/sources.json")
        self.assertEqual(status, 200)
        self.assertEqual(len(sources), 6)
        self.assertTrue(all(source["bookSourceUrl"].startswith("https://demo.example/") for source in sources))
        self.assertEqual(self.request("GET", "/novel/search?page=2")[1], {"books": []})
        self.assertEqual(self.request("GET", "/video/chapters/1")[1], {"video": "/assets/demo.mp4"})
        self.server.base_url = "http://127.0.0.1"
        self.assertEqual(len(self.request("GET", "/sources.json")[1]), 4)

    def test_password_and_key_sessions_are_scoped(self):
        self.assertEqual(self.request("GET", "/account/search")[0], 401)
        self.assertEqual(self.request("POST", "/account/login", {"username": "demo", "password": "wrong"})[0], 401)
        status, result = self.request("POST", "/account/login", {"username": "demo", "password": "demo-password"})
        self.assertEqual(status, 200)
        token = result["accessToken"]
        self.assertEqual(self.request("GET", "/account/session", token=token)[0], 204)
        self.assertEqual(self.request("GET", "/key/session", token=token)[0], 401)
        self.assertEqual(self.request("GET", "/account/books/demo/chapters", token=token)[0], 200)
        self.assertEqual(self.request("POST", "/key/login", {"apiKey": "demo-api-key"})[0], 200)
        self.server.tokens.clear()
        self.assertEqual(self.request("GET", "/account/session", token=token)[0], 401)

    def test_video_range(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request("GET", "/assets/demo.mp4", headers={"Range": "bytes=0-31"})
        response = connection.getresponse()
        self.assertEqual(response.status, 206)
        self.assertEqual(len(response.read()), 32)
        self.assertTrue(response.getheader("Content-Range").startswith("bytes 0-31/"))
        connection.close()
