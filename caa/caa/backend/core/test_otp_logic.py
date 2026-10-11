"""Pure-Python tests for the OTP rules and the Brevo call (no Django needed).
Run:  python -m unittest core.test_otp_logic
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import otp
from .emailer import EmailDeliveryError, send_via_brevo

SECRET = "test-secret"
EMAIL = "asha@example.com"


class FakeStore(dict):
    def set(self, k, v, ttl=None):
        self[k] = v


class Mailbox:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def __call__(self, email, code):
        if self.fail:
            raise EmailDeliveryError("down")
        self.sent.append((email, code))


def start(store, mail, now=1000.0):
    return otp.begin_signup(store, EMAIL, {"first_name": "Asha"}, "HASH", mail, SECRET, now)


class OtpFlow(unittest.TestCase):
    def setUp(self):
        self.store, self.mail = FakeStore(), Mailbox()

    def err(self, fn, *a):
        with self.assertRaises(otp.OtpError) as c:
            fn(*a)
        return c.exception

    def test_success(self):
        start(self.store, self.mail)
        code = self.mail.sent[0][1]
        self.assertRegex(code, r"^\d{6}$")
        state = otp.verify(self.store, EMAIL, code, SECRET, 1010.0)
        self.assertEqual(state["password_hash"], "HASH")

    def test_code_not_stored_in_plain_text(self):
        start(self.store, self.mail)
        code = self.mail.sent[0][1]
        self.assertNotIn(code, json.dumps(self.store))

    def test_wrong_code_counts_down_then_locks(self):
        start(self.store, self.mail)
        good = self.mail.sent[0][1]
        bad = "000000" if good != "000000" else "111111"
        for left in (4, 3, 2, 1):
            e = self.err(otp.verify, self.store, EMAIL, bad, SECRET, 1010.0)
            self.assertEqual(e.code, "invalid")
            self.assertIn(f"{left} ", e.message)
        e = self.err(otp.verify, self.store, EMAIL, bad, SECRET, 1010.0)
        self.assertEqual((e.code, e.status), ("too_many_attempts", 429))
        # even the right code no longer works once locked
        self.assertEqual(self.err(otp.verify, self.store, EMAIL, good, SECRET, 1011.0).code, "too_many_attempts")

    def test_new_code_after_lock_resets_attempts(self):
        start(self.store, self.mail)
        for _ in range(5):
            self.err(otp.verify, self.store, EMAIL, "123456" if self.mail.sent[0][1] != "123456" else "654321", SECRET, 1010.0)
        otp.resend(self.store, EMAIL, self.mail, SECRET, 1100.0)
        self.assertEqual(len(self.mail.sent), 2)
        otp.verify(self.store, EMAIL, self.mail.sent[1][1], SECRET, 1101.0)

    def test_expired(self):
        start(self.store, self.mail)
        e = self.err(otp.verify, self.store, EMAIL, self.mail.sent[0][1], SECRET, 1000.0 + otp.OTP_TTL + 1)
        self.assertEqual(e.code, "expired")

    def test_not_expired_at_boundary(self):
        start(self.store, self.mail)
        otp.verify(self.store, EMAIL, self.mail.sent[0][1], SECRET, 1000.0 + otp.OTP_TTL)

    def test_resend_cooldown(self):
        start(self.store, self.mail)
        e = self.err(otp.resend, self.store, EMAIL, self.mail, SECRET, 1030.0)
        self.assertEqual((e.code, e.status, e.retry_after), ("cooldown", 429, 30))
        otp.resend(self.store, EMAIL, self.mail, SECRET, 1061.0)
        self.assertEqual(len(self.mail.sent), 2)

    def test_restarting_signup_also_respects_cooldown(self):
        start(self.store, self.mail)
        self.assertEqual(self.err(start, self.store, self.mail, 1010.0).code, "cooldown")

    def test_hourly_send_limit(self):
        t = 1000.0
        start(self.store, self.mail, t)
        for _ in range(otp.MAX_SENDS - 1):
            t += otp.COOLDOWN + 1
            otp.resend(self.store, EMAIL, self.mail, SECRET, t)
        self.assertEqual(len(self.mail.sent), otp.MAX_SENDS)
        t += otp.COOLDOWN + 1
        e = self.err(otp.resend, self.store, EMAIL, self.mail, SECRET, t)
        self.assertEqual(e.code, "rate_limited")
        # after the window passes, sending works again
        otp.resend(self.store, EMAIL, self.mail, SECRET, 1000.0 + otp.SEND_WINDOW + 5)

    def test_email_failure_saves_nothing_and_starts_no_cooldown(self):
        with self.assertRaises(EmailDeliveryError):
            start(self.store, Mailbox(fail=True))
        self.assertEqual(self.store, {})
        start(self.store, self.mail, 1001.0)          # immediate retry is allowed
        self.assertEqual(len(self.mail.sent), 1)

    def test_resend_and_verify_without_signup(self):
        self.assertEqual(self.err(otp.resend, self.store, EMAIL, self.mail, SECRET, 1.0).code, "not_found")
        self.assertEqual(self.err(otp.verify, self.store, EMAIL, "123456", SECRET, 1.0).code, "not_found")

    def test_malformed_code_rejected_without_using_an_attempt(self):
        start(self.store, self.mail)
        for junk in ("", "12345", "abcdef", "1234567", None):
            self.assertEqual(self.err(otp.verify, self.store, EMAIL, junk, SECRET, 1010.0).code, "invalid")
        self.assertEqual(self.store[otp.key_for(EMAIL)]["attempts"], 0)

    def test_other_email_cannot_use_code(self):
        start(self.store, self.mail)
        self.assertEqual(self.err(otp.verify, self.store, "x@example.com", self.mail.sent[0][1], SECRET, 1010.0).code, "not_found")

    def test_mask(self):
        self.assertEqual(otp.mask_email("asha@example.com"), "a***@example.com")
        self.assertEqual(otp.mask_email("a@example.com"), "a*@example.com")


class _Brevo(BaseHTTPRequestHandler):
    seen = {}
    status = 201

    def do_POST(self):
        n = int(self.headers["content-length"])
        _Brevo.seen = {"headers": {k.lower(): v for k, v in self.headers.items()}, "body": json.loads(self.rfile.read(n))}
        self.send_response(_Brevo.status)
        self.end_headers()
        self.wfile.write(b'{"messageId":"x"}' if _Brevo.status < 300 else b'{"message":"bad key"}')

    def log_message(self, *a):
        pass


class BrevoCall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Brevo)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}/v3/smtp/email"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_request_shape(self):
        _Brevo.status = 201
        send_via_brevo("KEY123", "from@college.edu", "CAA", "to@example.com", "482913", url=self.url)
        h, b = _Brevo.seen["headers"], _Brevo.seen["body"]
        self.assertEqual(h["api-key"], "KEY123")
        self.assertEqual(b["to"], [{"email": "to@example.com"}])
        self.assertEqual(b["sender"]["email"], "from@college.edu")
        self.assertIn("482913", b["textContent"])
        self.assertIn("482913", b["htmlContent"])

    def test_provider_error_becomes_friendly_error(self):
        _Brevo.status = 401
        with self.assertRaises(EmailDeliveryError) as c:
            send_via_brevo("BAD", "from@college.edu", "CAA", "to@example.com", "111111", url=self.url)
        self.assertNotIn("BAD", str(c.exception))

    def test_unreachable_provider(self):
        with self.assertRaises(EmailDeliveryError):
            send_via_brevo("K", "f@x.com", "CAA", "t@x.com", "111111", url="http://127.0.0.1:9/x", timeout=2)

    def test_not_configured(self):
        with self.assertRaises(EmailDeliveryError):
            send_via_brevo("", "", "CAA", "t@x.com", "111111")


if __name__ == "__main__":
    unittest.main()
