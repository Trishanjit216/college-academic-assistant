"""Pure tests for the forgot-password OTP rules (no Django needed): python -m unittest core.test_reset_otp"""
import unittest

from core import reset_otp as ro

S = "secret-key"


class Store(dict):
    def set(self, k, v, ttl=None): self[k] = dict(v)
    def get(self, k): return dict(self[k]) if k in self else None
    def delete(self, k): self.pop(k, None)


class Mail:
    def __init__(self, fail=False): self.sent, self.fail = [], fail
    def __call__(self, email, code):
        if self.fail: raise RuntimeError("down")
        self.sent.append((email, code))


class ResetOtpTests(unittest.TestCase):
    def setUp(self): self.st, self.mail = Store(), Mail()

    def begin(self, portal="student", email="a@x.test", real=True, now=1000.0, mail=None):
        return ro.begin(self.st, portal, email, real, mail or self.mail, S, now)

    def test_code_is_six_digits_hashed_and_expires_in_five_minutes(self):
        info = self.begin(); code = self.mail.sent[0][1]
        self.assertRegex(code, r"^\d{6}$"); self.assertEqual(info["expires_in"], 300)
        self.assertNotIn(code, str(self.st)); self.assertEqual(self.st[ro.key_for("student", "a@x.test")]["expires_at"], 1300.0)

    def test_correct_code_gives_token_and_burns_the_code(self):
        self.begin(); code = self.mail.sent[0][1]
        tok = ro.verify(self.st, "student", "a@x.test", code, S, 1010)
        self.assertTrue(ro.check_token(self.st, "student", "a@x.test", tok, S, 1020))
        with self.assertRaises(ro.ResetError):                       # same code can't be used twice
            ro.verify(self.st, "student", "a@x.test", code, S, 1030)

    def test_wrong_code_rejected_and_counts_down_then_locks(self):
        self.begin(); good = self.mail.sent[0][1]; bad = "000000" if good != "000000" else "111111"
        for left in (4, 3, 2, 1):
            with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "a@x.test", bad, S, 1010)
            self.assertEqual(c.exception.code, "invalid"); self.assertIn(str(left), c.exception.message)
        with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "a@x.test", bad, S, 1010)
        self.assertEqual((c.exception.code, c.exception.status), ("too_many_attempts", 429))
        with self.assertRaises(ro.ResetError): ro.verify(self.st, "student", "a@x.test", good, S, 1011)   # right code now useless

    def test_expired_code_rejected(self):
        self.begin(); code = self.mail.sent[0][1]
        with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "a@x.test", code, S, 1000 + 301)
        self.assertEqual(c.exception.code, "expired")

    def test_malformed_code_rejected_without_counting(self):
        self.begin()
        for bad in ("", "12345", "abcdef", "1234567", None):
            with self.assertRaises(ro.ResetError): ro.verify(self.st, "student", "a@x.test", bad, S, 1010)
        self.assertEqual(self.st[ro.key_for("student", "a@x.test")]["attempts"], 0)

    def test_cooldown_then_resend_invalidates_previous_code(self):
        self.begin(); first = self.mail.sent[0][1]
        with self.assertRaises(ro.ResetError) as c: self.begin(now=1030)
        self.assertEqual((c.exception.code, c.exception.retry_after), ("cooldown", 30))
        self.begin(now=1061); second = self.mail.sent[1][1]
        if first != second:
            with self.assertRaises(ro.ResetError): ro.verify(self.st, "student", "a@x.test", first, S, 1062)
        self.assertTrue(ro.verify(self.st, "student", "a@x.test", second, S, 1062))

    def test_hourly_send_limit(self):
        for i in range(ro.MAX_SENDS): self.begin(now=1000 + i * 61)
        with self.assertRaises(ro.ResetError) as c: self.begin(now=1000 + 5 * 61)
        self.assertEqual(c.exception.code, "rate_limited")
        self.begin(now=1000 + ro.SEND_WINDOW + 10)                   # a new hour starts fresh

    def test_delivery_failure_saves_nothing_and_starts_no_cooldown(self):
        with self.assertRaises(RuntimeError): self.begin(mail=Mail(fail=True))
        self.assertEqual(self.st, {})
        self.begin(now=1001)                                          # can retry immediately

    def test_unknown_account_looks_identical_but_nothing_is_sent_and_nothing_can_match(self):
        a = self.begin(email="ghost@x.test", real=False)
        self.assertEqual(self.mail.sent, []); self.assertEqual(a, {"resend_in": 60, "expires_in": 300})
        with self.assertRaises(ro.ResetError) as c: self.begin(email="ghost@x.test", real=False, now=1010)     # same cooldown
        self.assertEqual(c.exception.code, "cooldown")
        for i in range(4):
            with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "ghost@x.test", "123456", S, 1020)
            self.assertEqual(c.exception.code, "invalid")             # same attempts-left wording as a real account
        with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "ghost@x.test", "123456", S, 1020)
        self.assertEqual(c.exception.code, "too_many_attempts")

    def test_never_requested_gives_generic_message(self):
        with self.assertRaises(ro.ResetError) as c: ro.verify(self.st, "student", "a@x.test", "123456", S, 1000)
        self.assertEqual(c.exception.message, ro.GENERIC_BAD)

    def test_student_and_faculty_are_separate(self):
        self.begin("student"); code = self.mail.sent[0][1]
        with self.assertRaises(ro.ResetError): ro.verify(self.st, "faculty", "a@x.test", code, S, 1010)
        tok = ro.verify(self.st, "student", "a@x.test", code, S, 1010)
        self.assertFalse(ro.check_token(self.st, "faculty", "a@x.test", tok, S, 1020))

    def test_token_expires_is_single_use_and_bound_to_email(self):
        self.begin(); tok = ro.verify(self.st, "student", "a@x.test", self.mail.sent[0][1], S, 1010)
        self.assertFalse(ro.check_token(self.st, "student", "b@x.test", tok, S, 1020))
        self.assertFalse(ro.check_token(self.st, "student", "a@x.test", "wrong", S, 1020))
        self.assertFalse(ro.check_token(self.st, "student", "a@x.test", None, S, 1020))
        self.assertFalse(ro.check_token(self.st, "student", "a@x.test", tok, S, 1010 + ro.RESET_TTL + 1))
        ro.finish(self.st, "student", "a@x.test"); self.assertFalse(ro.check_token(self.st, "student", "a@x.test", tok, S, 1020))

    def test_mask(self): self.assertEqual(ro.mask_email("asha@x.test"), "a***@x.test")


class StampTests(unittest.TestCase):
    def test_stamp_changes_when_password_hash_changes(self):
        import types
        from core import session_stamp as A
        u = types.SimpleNamespace(password="pbkdf2$1$abc"); a = A.stamp(u); u.password = "pbkdf2$1$def"
        self.assertNotEqual(a, A.stamp(u)); self.assertEqual(len(a), 20); self.assertNotIn("abc", a)


if __name__ == "__main__":
    unittest.main()
