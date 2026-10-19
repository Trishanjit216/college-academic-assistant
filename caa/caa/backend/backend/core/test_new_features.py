"""Pure-Python tests (no Django needed):  cd backend && python3 -m unittest core.test_new_features"""
import unittest
from datetime import date

from . import sections


class SectionRules(unittest.TestCase):
    def test_lists(self):
        self.assertEqual(sections.allowed_sections("Group A"), [f"A{i}" for i in range(1, 13)])
        self.assertEqual(sections.allowed_sections("group b")[-1], "B12")
        self.assertEqual(sections.allowed_sections("Group C"), [])
        self.assertEqual(sections.allowed_sections(None), [])

    def test_valid_and_invalid(self):
        self.assertIsNone(sections.check("Group A", "A12"))
        self.assertIsNone(sections.check("Group B", "b3"))
        self.assertIsNone(sections.check("Group A", ""))
        self.assertIsNone(sections.check(None, ""))
        self.assertIn("does not belong", sections.check("Group A", "B1"))
        self.assertIn("does not belong", sections.check("Group B", "A1"))
        self.assertIn("does not belong", sections.check("Group A", "A13"))
        self.assertIn("does not belong", sections.check("Group A", "A0"))
        self.assertIn("Select your group", sections.check(None, "A1"))
        self.assertIn("only available", sections.check("Lab 7", "A1"))


class RequiredFields(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(sections.missing_fields("Group A", "A1", "21CS001"), [])
        self.assertEqual(sections.missing_fields("Group A", "", "21CS001"), ["section"])
        self.assertEqual(sections.missing_fields(None, "", ""), ["roll number", "group"])
        self.assertEqual(sections.missing_fields("Lab 7", "", "5"), [])        # group without sections
        self.assertEqual(sections.missing_fields("Group B", " ", " "), ["roll number", "section"])

    def test_message(self):
        self.assertEqual(sections.missing_message([]), "")
        self.assertEqual(sections.missing_message(["group"]), "Please provide your group.")
        self.assertEqual(sections.missing_message(["roll number", "group", "section"]),
                         "Please provide your roll number, group and section.")


if __name__ == "__main__":
    unittest.main()
