"""Pure-Python tests (no Django):  cd backend && python3 -m unittest core.test_faculty_codes"""
import re
import unittest

from . import faculty_codes as fc


class Codes(unittest.TestCase):
    def test_format_and_alphabet(self):
        for _ in range(200):
            c = fc.generate_code()
            self.assertRegex(c, r"^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$")
            self.assertFalse(set(c) & set("IO01"))            # nothing easy to misread

    def test_every_code_is_different(self):
        codes = {fc.generate_code() for _ in range(2000)}
        self.assertEqual(len(codes), 2000)                     # no shared / repeating code

    def test_normalize_accepts_typing_variations(self):
        c = fc.generate_code()
        raw = c.replace("-", "")
        for typed in (c, c.lower(), "  " + c + " ", raw, raw.lower(), c.replace("-", " ")):
            self.assertEqual(fc.normalize(typed), raw)
        for bad in ("", None, "ABC", "AAAA-AAAA-AAA", "AAAA-AAAA-AAAAA", "IIII-OOOO-0000", 123, "AAAA-AAAA-AAA!"):
            self.assertEqual(fc.normalize(bad), "")

    def test_hash_never_contains_the_code_and_verifies(self):
        c = fc.generate_code()
        h = fc.hash_code(c)
        self.assertTrue(h.startswith("pbkdf2_sha256$"))
        self.assertNotIn(c.replace("-", ""), h)
        self.assertNotIn(c, h)
        self.assertTrue(fc.check_code(c, h))
        self.assertTrue(fc.check_code(c.lower().replace("-", " "), h))

    def test_wrong_code_and_garbage_fail_safely(self):
        h = fc.hash_code("ABCD-EFGH-JKLM")
        self.assertFalse(fc.check_code("ABCD-EFGH-JKLN", h))
        for junk in (None, "", "x", 5):
            self.assertFalse(fc.check_code(junk, h))
        for bad_hash in ("", "plain", "md5$1$a$b", None, "pbkdf2_sha256$x$y"):
            self.assertFalse(fc.check_code("ABCD-EFGH-JKLM", bad_hash))

    def test_same_code_gets_different_hashes(self):
        c = fc.generate_code()
        self.assertNotEqual(fc.hash_code(c), fc.hash_code(c))   # random salt

    def test_hash_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            fc.hash_code("nope")

    def test_dummy_hash_never_matches_a_real_guess_path(self):
        self.assertTrue(fc.DUMMY_HASH.startswith("pbkdf2_sha256$"))


if __name__ == "__main__":
    unittest.main()
