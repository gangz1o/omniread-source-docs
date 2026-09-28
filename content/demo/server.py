#!/usr/bin/env python3
"""Local book-source protocol fixture. Standard library only; not a production server."""
import argparse
import copy
import io
import json
import math
from pathlib import Path
import secrets
import ssl
import struct
import time
import wave
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
RESPONSES = json.loads((ROOT / "demo/responses.json").read_text())


def image_bytes(second=False):
    width, height = 240, 320
    colors = [(235, 223, 195), (84, 116, 130)] if second else [(218, 233, 226), (90, 119, 92)]
    rows = b"".join(b"\x00" + bytes(colors[(y // 80) % 2]) * width for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def audio_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", int(1800 * math.sin(2 * math.pi * 440 * n / 8000))) for n in range(16000)))
    return output.getvalue()


ASSETS = {"/assets/page-1.png": ("image/png", image_bytes()), "/assets/page-2.png": ("image/png", image_bytes(True)), "/assets/tone.wav": ("audio/wav", audio_bytes())}


ASSETS["/assets/demo.mp4"] = ("video/mp4", (ROOT / "demo/assets/demo.mp4").read_bytes())


class DemoServer(HTTPServer):
    def __init__(self, address, base_url):
        super().__init__(address, Handler)
        self.base_url = base_url.rstrip("/")
        self.tokens = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No request bodies, Authorization, or signed URLs in logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def send_bytes(self, data, content_type, status=200, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def authenticated(self, scope):
        value = self.headers.get("Authorization", "")
        record = self.server.tokens.get(value.removeprefix("Bearer ")) if value.startswith("Bearer ") else None
        return record is not None and record[0] == scope and record[1] > time.monotonic()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/account/login", "/key/login"):
            self.send_json({"error": "not_found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
        except (ValueError, OSError):
            self.send_json({"error": "invalid_request"}, 400)
            return
        expected = {"username": "demo", "password": "demo-password"} if path == "/account/login" else {"apiKey": "demo-api-key"}
        if body != expected:
            self.send_json({"error": "invalid_credentials"}, 401)
            return
        self.server.tokens = {key: value for key, value in self.server.tokens.items() if value[1] > time.monotonic()}
        if len(self.server.tokens) >= 100:
            self.send_json({"error": "too_many_sessions"}, 429)
            return
        token = secrets.token_urlsafe(24)
        self.server.tokens[token] = (path.split("/")[1], time.monotonic() + 3600)
        self.send_json({"accessToken": token, "expiresIn": 3600})

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/sources.json":
            sources = []
            for name in ("novel", "comic", "audio", "video", "account", "key"):
                if name in ("account", "key") and not self.server.base_url.startswith("https://"):
                    continue
                source = (ROOT / f"examples/{name}.json").read_text().replace("https://demo.omniread.invalid", self.server.base_url)
                sources.append(json.loads(source))
            self.send_json(sources)
            return
        scope = path.split("/")[1] if "/" in path else ""
        if scope in ("account", "key"):
            if not self.authenticated(scope):
                self.send_json({"error": "authentication_required"}, 401)
                return
            if path.endswith("/session"):
                self.send_bytes(b"", "application/json", 204)
                return
        if path in ASSETS:
            content_type, data = ASSETS[path]
            extra = {"Accept-Ranges": "bytes"}
            range_value = self.headers.get("Range")
            if range_value:
                try:
                    if not range_value.startswith("bytes=") or "," in range_value:
                        raise ValueError()
                    start, end = range_value[6:].split("-")
                    if not start:
                        suffix = int(end)
                        if suffix <= 0:
                            raise ValueError()
                        start, end = max(0, len(data) - suffix), len(data) - 1
                    else:
                        start, end = int(start), int(end) if end else len(data) - 1
                    end = min(end, len(data) - 1)
                    if start < 0 or start > end or start >= len(data):
                        raise ValueError()
                except ValueError:
                    self.send_bytes(b"", content_type, 416, {"Content-Range": f"bytes */{len(data)}"})
                    return
                extra["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
                self.send_bytes(data[start:end + 1], content_type, 206, extra)
            else:
                self.send_bytes(data, content_type, headers=extra)
            return
        if path not in RESPONSES:
            self.send_json({"error": "not_found"}, 404)
            return
        value = copy.deepcopy(RESPONSES[path])
        if path.endswith(("/search", "/explore")):
            query = parse_qs(parsed.query)
            keyword = query.get("q", [""])[0]
            if query.get("page", ["1"])[0] != "1" or (keyword and keyword not in "云间小记 云间短剧 演示作者"):
                value = {"books": []}
        self.send_json(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--tls-cert")
    parser.add_argument("--tls-key")
    args = parser.parse_args()
    base = urlsplit(args.base_url)
    if base.scheme not in ("http", "https") or not base.hostname or base.username or base.password or base.query or base.fragment or base.path not in ("", "/"):
        parser.error("--base-url 必须是无路径和凭据的 HTTP(S) 根地址")
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("证书和私钥必须同时提供")
    server = DemoServer((args.bind, args.port), args.base_url)
    if args.tls_cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print("演示服务已启动；GET /sources.json 获取书源。Ctrl-C 停止。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
