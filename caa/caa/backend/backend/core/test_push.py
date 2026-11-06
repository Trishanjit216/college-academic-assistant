"""Pure-Python tests (no Django):  cd backend && python3 -m unittest core.test_push"""
import base64
import json
import unittest

from . import push

INFO = {"client_email": "svc@proj.iam.gserviceaccount.com", "private_key": "-----BEGIN PRIVATE KEY-----\nX\n-----END PRIVATE KEY-----\n", "project_id": "caa-demo"}
TOK = "dXNlci10b2tlbi0x" + "A" * 30


class Parsing(unittest.TestCase):
    def test_service_account_plain_and_base64(self):
        raw = json.dumps(INFO)
        self.assertEqual(push.load_service_account(raw)["project_id"], "caa-demo")
        self.assertEqual(push.load_service_account(base64.b64encode(raw.encode()).decode())["project_id"], "caa-demo")

    def test_bad_service_account(self):
        for bad in ("", None, "   ", "not json", "{}", json.dumps({"project_id": "x"}), "{broken", base64.b64encode(b"hello").decode(), "[1]"):
            self.assertIsNone(push.load_service_account(bad), bad)

    def test_safe_link(self):
        self.assertEqual(push.safe_link("/events?event=3"), "/events?event=3")
        for bad in ("https://evil.example", "//evil.example", "javascript:alert(1)", "", None, "/\\evil", "x" * 300, 5):
            self.assertEqual(push.safe_link(bad), "/notifications")

    def test_token_validation(self):
        self.assertEqual(push.clean_token("  " + TOK + " "), TOK)
        for bad in (None, "", "short", "a b" * 20, "x" * 600, 12, "<script>" + "a" * 30):
            self.assertIsNone(push.clean_token(bad))

    def test_body_is_one_short_line(self):
        self.assertEqual(push.push_body("Line one\nOn 17 Oct 2026"), "Line one On 17 Oct 2026")
        self.assertLessEqual(len(push.push_body("word " * 100)), 160)

    def test_message_shape_is_data_only_and_safe(self):
        m = push.build_message(TOK, "T" * 300, "B", "https://evil.example", tag="event:1:published", kind="event")["message"]
        self.assertNotIn("notification", m)                         # data-only, so it can never be shown twice
        self.assertEqual(m["token"], TOK)
        self.assertEqual(m["data"]["link"], "/notifications")
        self.assertLessEqual(len(m["data"]["title"]), 100)
        self.assertTrue(all(isinstance(v, str) for v in m["data"].values()))   # FCM data values must be strings

    def test_classify(self):
        self.assertEqual(push.classify(200, "{}"), "ok")
        self.assertEqual(push.classify(404, '{"error":{"status":"NOT_FOUND"}}'), "dead")
        self.assertEqual(push.classify(400, '{"error":{"status":"INVALID_ARGUMENT","message":"The registration token is not a valid FCM registration token"}}'), "dead")
        self.assertEqual(push.classify(403, '{"error":{"status":"SENDER_ID_MISMATCH"}}'), "dead")
        self.assertEqual(push.classify(400, '{"error":{"status":"INVALID_ARGUMENT","message":"bad payload"}}'), "fail")   # our bug: keep the token
        self.assertEqual(push.classify(401, "unauthorized"), "fail")
        self.assertEqual(push.classify(429, ""), "retry")
        self.assertEqual(push.classify(503, ""), "retry")


class FakeFCM:
    def __init__(self, plan=None):
        self.calls, self.plan = [], plan or {}

    def post(self, url, headers, body):
        msg = json.loads(body)["message"]
        self.calls.append((url, headers, msg))
        seq = self.plan.get(msg["token"], [(200, "{}")])
        return seq.pop(0) if len(seq) > 1 else seq[0]


def sender(fake, ttl=3000):
    n = {"n": 0}

    def tf():
        n["n"] += 1
        return f"access-{n['n']}", ttl
    s = push.Sender(INFO, post=fake.post, token_fn=tf)
    s.token_calls = n
    return s


class Sending(unittest.TestCase):
    def setUp(self):
        push.time.sleep = lambda *_: None                           # no real waiting in retries

    def test_sends_to_v1_endpoint_with_bearer(self):
        f = FakeFCM(); s = sender(f)
        r = push.send_many(s, [TOK], "Title", "Body", "/events?event=1", tag="event:1:published", kind="event")
        self.assertEqual(r, {"sent": 1, "failed": 0, "dead": []})
        url, headers, msg = f.calls[0]
        self.assertEqual(url, "https://fcm.googleapis.com/v1/projects/caa-demo/messages:send")
        self.assertEqual(headers["Authorization"], "Bearer access-1")
        self.assertEqual(msg["data"]["link"], "/events?event=1")

    def test_access_token_is_reused_then_renewed(self):
        f = FakeFCM(); s = sender(f)
        push.send_many(s, [TOK, TOK + "2"], "t", "b", "/")
        self.assertEqual(s.token_calls["n"], 1)
        s._exp = 0
        push.send_many(s, [TOK], "t", "b", "/")
        self.assertEqual(s.token_calls["n"], 2)

    def test_duplicate_tokens_get_one_message(self):
        f = FakeFCM()
        push.send_many(sender(f), [TOK, TOK, "", None], "t", "b", "/")
        self.assertEqual(len(f.calls), 1)

    def test_dead_token_is_reported_for_removal_others_still_sent(self):
        good, dead = TOK, TOK + "dead"
        f = FakeFCM({dead: [(404, '{"error":{"status":"NOT_FOUND"}}')]})
        r = push.send_many(sender(f), [good, dead], "t", "b", "/")
        self.assertEqual((r["sent"], r["dead"], r["failed"]), (1, [dead], 0))

    def test_retries_once_then_gives_up_without_deleting(self):
        t = TOK + "slow"
        f = FakeFCM({t: [(503, ""), (200, "{}")]})
        self.assertEqual(push.send_many(sender(f), [t], "t", "b", "/")["sent"], 1)
        f2 = FakeFCM({t: [(503, "")]})
        r = push.send_many(sender(f2), [t], "t", "b", "/")
        self.assertEqual((r["sent"], r["failed"], r["dead"]), (0, 1, []))
        self.assertEqual(len(f2.calls), 2)

    def test_auth_problem_never_raises_and_keeps_tokens(self):
        def boom():
            raise RuntimeError("bad key")
        s = push.Sender(INFO, post=FakeFCM().post, token_fn=boom)
        r = push.send_many(s, [TOK], "t", "b", "/")
        self.assertEqual((r["sent"], r["failed"], r["dead"]), (0, 1, []))

    def test_empty_list(self):
        self.assertEqual(push.send_many(sender(FakeFCM()), [], "t", "b", "/"), {"sent": 0, "failed": 0, "dead": []})

    def test_secret_never_in_messages(self):
        f = FakeFCM(); push.send_many(sender(f), [TOK], "t", "b", "/")
        self.assertNotIn("PRIVATE KEY", json.dumps(f.calls[0][2]))


if __name__ == "__main__":
    unittest.main()
