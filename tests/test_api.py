import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(cls.tmp.name, "sub", "t.db")
        os.environ["QUIET"] = "1"
        import server
        cls.server = server.make_server(port=0, host="127.0.0.1")
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def req(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(self.base + path, data=data, method=method,
                                   headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def j(self, method, path, body=None, expect=200):
        st, raw, _ = self.req(method, path, body)
        self.assertEqual(st, expect, raw)
        return json.loads(raw) if raw else None

    def new_decision(self, title="Laptop?"):
        return self.j("POST", "/api/decisions", {"title": title}, 201)

    def test_healthz(self):
        st, raw, _ = self.req("GET", "/healthz")
        self.assertEqual((st, raw), (200, b"ok"))

    def test_decision_crud(self):
        d = self.new_decision("Türkçe başlık çğış")
        self.assertEqual(d["status"], "open")
        self.assertEqual(d["options"], [])
        self.assertEqual(d["notes"], "")
        got = self.j("GET", f"/api/decisions/{d['id']}")
        self.assertEqual(got["title"], "Türkçe başlık çğış")
        up = self.j("PUT", f"/api/decisions/{d['id']}", {"notes": "not"})
        self.assertEqual((up["title"], up["notes"]), ("Türkçe başlık çğış", "not"))
        ids = [x["id"] for x in self.j("GET", "/api/decisions")]
        self.assertIn(d["id"], ids)
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.j("DELETE", f"/api/decisions/{d['id']}", expect=204)
        self.j("GET", f"/api/decisions/{d['id']}", expect=404)
        self.j("DELETE", f"/api/decisions/{d['id']}", expect=404)

    def test_validation(self):
        self.assertIn("error", self.j("POST", "/api/decisions", {"title": "  "}, 400))
        self.j("POST", "/api/decisions", {}, 400)
        self.j("POST", "/api/decisions", {"title": 5}, 400)
        st, raw, _ = self.req("POST", "/api/decisions", raw=b"{bozuk")
        self.assertEqual(st, 400)
        self.assertIn("error", json.loads(raw))
        d = self.new_decision()
        self.j("PUT", f"/api/decisions/{d['id']}", {"title": ""}, 400)
        self.j("PUT", "/api/decisions/99999", {"title": "x"}, 404)
        self.j("POST", f"/api/decisions/{d['id']}/options", {"name": ""}, 400)
        self.j("POST", "/api/decisions/99999/options", {"name": "a"}, 404)
        self.j("PUT", "/api/options/99999", {"name": "a"}, 404)
        self.j("DELETE", "/api/options/99999", expect=404)
        self.j("GET", "/api/nope", expect=404)
        self.j("DELETE", "/api/decisions", expect=405)

    def test_options_and_decide(self):
        d = self.new_decision()
        did = d["id"]
        a = self.j("POST", f"/api/decisions/{did}/options",
                   {"name": "A", "gains": "g", "losses": "l", "risks": "r"}, 201)
        b = self.j("POST", f"/api/decisions/{did}/options", {"name": "B"}, 201)
        self.assertEqual((a["gains"], a["losses"], a["risks"]), ("g", "l", "r"))
        self.assertEqual(b["gains"], "")
        self.assertLess(a["position"], b["position"])
        up = self.j("PUT", f"/api/options/{b['id']}", {"gains": "yeni"})
        self.assertEqual((up["name"], up["gains"]), ("B", "yeni"))
        self.j("PUT", f"/api/options/{b['id']}", {"name": ""}, 400)
        self.assertEqual(len(self.j("GET", f"/api/decisions/{did}")["options"]), 2)

        dec = self.j("POST", f"/api/decisions/{did}/decide", {"option_id": a["id"], "reason": "iyi"})
        self.assertEqual((dec["status"], dec["chosen_option_id"], dec["decision_reason"]),
                         ("decided", a["id"], "iyi"))
        self.assertTrue(dec["decided_at"])
        self.j("POST", f"/api/decisions/{did}/decide", {"option_id": "x"}, 400)
        self.j("POST", "/api/decisions/99999/decide", {"option_id": 1}, 404)

        re_ = self.j("POST", f"/api/decisions/{did}/reopen")
        self.assertEqual((re_["status"], re_["chosen_option_id"], re_["decided_at"]),
                         ("open", None, None))
        self.assertEqual(re_["decision_reason"], "")
        self.j("POST", "/api/decisions/99999/reopen", expect=404)

    def test_foreign_option_decide(self):
        d1, d2 = self.new_decision("1"), self.new_decision("2")
        o2 = self.j("POST", f"/api/decisions/{d2['id']}/options", {"name": "x"}, 201)
        self.j("POST", f"/api/decisions/{d1['id']}/decide", {"option_id": o2["id"]}, 400)
        self.assertEqual(self.j("GET", f"/api/decisions/{d1['id']}")["status"], "open")

    def test_delete_chosen_option_reopens(self):
        d = self.new_decision()
        o = self.j("POST", f"/api/decisions/{d['id']}/options", {"name": "x"}, 201)
        self.j("POST", f"/api/decisions/{d['id']}/decide", {"option_id": o["id"], "reason": "r"})
        self.j("DELETE", f"/api/options/{o['id']}", expect=204)
        got = self.j("GET", f"/api/decisions/{d['id']}")
        self.assertEqual((got["status"], got["chosen_option_id"], got["options"]), ("open", None, []))

    def test_delete_decision_cascades_options(self):
        d = self.new_decision()
        o = self.j("POST", f"/api/decisions/{d['id']}/options", {"name": "x"}, 201)
        self.j("DELETE", f"/api/decisions/{d['id']}", expect=204)
        self.j("PUT", f"/api/options/{o['id']}", {"name": "y"}, 404)

    def test_static_and_traversal(self):
        static = os.path.join(ROOT, "app", "static")
        os.makedirs(static, exist_ok=True)
        probe = os.path.join(static, "_probe.js")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("// çğ")
        try:
            st, raw, h = self.req("GET", "/static/_probe.js")
            self.assertEqual(st, 200)
            self.assertIn("javascript", h["Content-Type"])
            self.assertIn("utf-8", h["Content-Type"])
            self.assertEqual(raw.decode("utf-8"), "// çğ")
        finally:
            os.remove(probe)
        self.assertEqual(self.req("GET", "/static/yok.css")[0], 404)
        for p in ("/static/../server.py", "/static/..%2fserver.py", "/static/%2e%2e/db.py",
                  "/static/..%2f..%2ftests/test_api.py", "/static//etc/passwd",
                  "/static/%2Fetc%2Fpasswd"):
            st, raw, _ = self.req("GET", p)
            self.assertEqual(st, 404, p)
            self.assertNotIn(b"import", raw)

    def test_index(self):
        # static/ henüz yoksa da çökmemeli; varsa 200 döner.
        st, _, _ = self.req("GET", "/")
        self.assertIn(st, (200, 404))
        self.assertEqual(self.req("GET", "/healthz")[0], 200)


if __name__ == "__main__":
    unittest.main()
