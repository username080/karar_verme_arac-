"""HTTP sunucu: JSON API + statik dosya servisi (yalnızca standart kütüphane)."""
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boardio  # noqa: E402
import db  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_BODY = 1024 * 1024

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

ROUTES = [
    ("GET", r"/api/decisions", lambda m, b: (200, db.list_decisions())),
    ("POST", r"/api/decisions", lambda m, b: (201, db.create_decision(b))),
    ("GET", r"/api/decisions/(\d+)", lambda m, b: (200, db.get_decision(int(m[1])))),
    ("PUT", r"/api/decisions/(\d+)", lambda m, b: (200, db.update_decision(int(m[1]), b))),
    ("DELETE", r"/api/decisions/(\d+)", lambda m, b: (204, db.delete_decision(int(m[1])))),
    ("POST", r"/api/decisions/(\d+)/options", lambda m, b: (201, db.create_option(int(m[1]), b))),
    ("PUT", r"/api/options/(\d+)", lambda m, b: (200, db.update_option(int(m[1]), b))),
    ("DELETE", r"/api/options/(\d+)", lambda m, b: (204, db.delete_option(int(m[1])))),
    ("POST", r"/api/decisions/(\d+)/decide", lambda m, b: (200, db.decide(int(m[1]), b))),
    ("POST", r"/api/import", lambda m, b: (201, db.import_board(boardio.parse_import(b)))),
    ("POST", r"/api/decisions/(\d+)/reopen", lambda m, b: (200, db.reopen(int(m[1])))),
]


class Handler(BaseHTTPRequestHandler):
    server_version = "makeurchoice"

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)

    def _send(self, code, body=b"", ctype=None):
        self.send_response(code)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD" and code != 204:
            self.wfile.write(body)

    def _json(self, code, obj):
        if code == 204:
            return self._send(204)
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, code, msg):
        self._json(code, {"error": msg})

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise db.BadRequest("geçersiz Content-Length")
        if n > MAX_BODY:
            raise db.BadRequest("gövde çok büyük")
        if n == 0:
            return {}
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise db.BadRequest("geçersiz JSON")
        if not isinstance(data, dict):
            raise db.BadRequest("JSON nesnesi bekleniyor")
        return data

    def _handle(self):
        path = urlsplit(self.path).path
        try:
            if path.startswith("/api/"):
                return self._api(path)
            if self.command not in ("GET", "HEAD"):
                return self._error(405, "yöntem desteklenmiyor")
            if path == "/healthz":
                return self._send(200, b"ok", "text/plain; charset=utf-8")
            if path == "/":
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(unquote(path[len("/static/"):]))
            self._error(404, "bulunamadı")
        except (db.BadRequest, boardio.BoardError) as e:
            self._error(400, str(e))
        except db.NotFound as e:
            self._error(404, str(e))
        except Exception as e:  # noqa: BLE001
            self.log_error("hata: %r", e)
            self._error(500, "sunucu hatası")

    def _api(self, path):
        path_matched = False
        for method, pattern, fn in ROUTES:
            m = re.fullmatch(pattern, path)
            if not m:
                continue
            path_matched = True
            if method != self.command:
                continue
            body = self._read_body() if method in ("POST", "PUT") else {}
            code, obj = fn(m, body)
            return self._json(code, obj)
        self._error(405 if path_matched else 404,
                    "yöntem desteklenmiyor" if path_matched else "bulunamadı")

    def _static(self, rel):
        if "\x00" in rel or not rel:
            return self._error(404, "bulunamadı")
        root = os.path.realpath(STATIC_DIR)
        full = os.path.realpath(os.path.join(root, rel))
        if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
            return self._error(404, "bulunamadı")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = _handle


def make_server(port=None, host="0.0.0.0"):
    db.init_db()
    if port is None:
        port = int(os.environ.get("PORT", "8767"))
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


if __name__ == "__main__":
    s = make_server()
    print(f"dinleniyor: {s.server_address[0]}:{s.server_address[1]}", flush=True)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
