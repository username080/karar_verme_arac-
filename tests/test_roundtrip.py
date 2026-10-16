import json
import unittest

from test_api import ApiTest as Base


def copy_text(d):
    """app.js buildBoardText şablonunu taklit eder (kopyala metni)."""
    chosen = next((o for o in d["options"] if o["id"] == d["chosen_option_id"]), None)
    board = {
        "format": "makeurchoice.board", "version": 1,
        "title": d["title"], "notes": d["notes"],
        "status": "decided" if chosen else "open",
        "chosen_option": chosen["name"] if chosen else None,
        "decision_reason": d["decision_reason"],
        "options": [{k: o[k] for k in ("name", "gains", "losses", "risks")} for o in d["options"]],
    }
    return ("Aşağıda bir karar panosu var...\n\n## %s\n" % d["title"]
            + "```json\n" + json.dumps(board, indent=2) + "\n```")


class RoundTripTest(Base):
    def test_copy_import_roundtrip(self):
        d = self.new_decision("Şehir seçimi: İstanbul mu İzmir mi? ğüşıöç")
        self.j("PUT", f"/api/decisions/{d['id']}", {"notes": "Not \"tırnak\"\nsatır 2 ✓"})
        ids = []
        for n in ("İstanbul", "İzmir", "Çanakkale"):
            o = self.j("POST", f"/api/decisions/{d['id']}/options",
                       {"name": n, "gains": f"{n} kazanç ğ", "losses": "kayıp\nçok satır", "risks": "risk ş"}, 201)
            ids.append(o["id"])
        self.j("POST", f"/api/decisions/{d['id']}/decide", {"option_id": ids[1], "reason": "Deniz ve sakinlik ı"})
        src = self.j("GET", f"/api/decisions/{d['id']}")

        new = self.j("POST", "/api/import", {"text": copy_text(src)}, 201)
        self.assertNotEqual(new["id"], src["id"])
        for k in ("title", "notes", "status", "decision_reason"):
            self.assertEqual(new[k], src[k], k)
        self.assertEqual([{k: o[k] for k in ("name", "gains", "losses", "risks")} for o in new["options"]],
                         [{k: o[k] for k in ("name", "gains", "losses", "risks")} for o in src["options"]])
        chosen = next(o for o in new["options"] if o["id"] == new["chosen_option_id"])
        self.assertEqual(chosen["name"], "İzmir")

    def test_reason_put_survives_reopen(self):
        d = self.new_decision("Neden testi")
        o = self.j("POST", f"/api/decisions/{d['id']}/options", {"name": "A"}, 201)
        self.j("POST", f"/api/decisions/{d['id']}/decide", {"option_id": o["id"]})
        r = self.j("PUT", f"/api/decisions/{d['id']}", {"decision_reason": "sonradan yazıldı ç"})
        self.assertEqual(r["decision_reason"], "sonradan yazıldı ç")
        re = self.j("POST", f"/api/decisions/{d['id']}/reopen")
        self.assertEqual(re["status"], "open")
        self.assertEqual(re["decision_reason"], "sonradan yazıldı ç")
        self.assertEqual(self.j("GET", f"/api/decisions/{d['id']}")["decision_reason"], "sonradan yazıldı ç")


# Temel sınıfın testleri iki kez çalışmasın: devralınanları devre dışı bırak.
for _n in dir(Base):
    if _n.startswith("test_") and _n not in RoundTripTest.__dict__:
        setattr(RoundTripTest, _n, None)
del Base
if __name__ == "__main__":
    unittest.main()
