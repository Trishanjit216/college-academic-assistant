"""Pure-Python tests (no Django needed):  cd backend && python3 -m unittest core.test_new_features"""
import unittest
from datetime import date

from . import sections, seat_import


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


GOOD = "roll_no,student_name,exam_name,exam_date,room,seat,instructions\n" \
       "21cs001,Asha Rao,Mid-Term 1,2026-11-03,Room 204,B12,Bring ID\n" \
       "21CS002,,Mid-Term 1,,Hall 1,A3,\n"


class SeatImport(unittest.TestCase):
    def test_good_rows(self):
        rows, errs = seat_import.parse_csv(GOOD)
        self.assertEqual(errs, [])
        self.assertEqual(rows[0]["roll_no"], "21CS001")
        self.assertEqual(rows[0]["exam_date"], date(2026, 11, 3))
        self.assertIsNone(rows[1]["exam_date"])

    def test_missing_columns(self):
        with self.assertRaises(seat_import.ImportProblem):
            seat_import.parse_csv("roll_no,room\n1,2\n")

    def test_bad_rows_reported_not_invented(self):
        txt = "roll_no,exam_name,room,seat,exam_date\n,Mid,R1,1,\n1,Mid,,2,\n3,Mid,R3,4,03-11-2026\n5,Mid,R5,6,\n5,mid,R5,7,\n"
        rows, errs = seat_import.parse_csv(txt)
        self.assertEqual([r["roll_no"] for r in rows], ["5"])
        self.assertEqual([e["row"] for e in errs], [2, 3, 4, 6])
        self.assertIn("Duplicate", errs[-1]["error"])

    def test_empty_and_bom_and_blank_lines(self):
        with self.assertRaises(seat_import.ImportProblem):
            seat_import.parse_csv("  ")
        rows, errs = seat_import.parse_csv("﻿roll_no,exam_name,room,seat\n\n1,E,R,1\n")
        self.assertEqual(len(rows), 1)

    def test_too_long_value(self):
        rows, errs = seat_import.parse_csv("roll_no,exam_name,room,seat\n1,E," + "x" * 80 + ",1\n")
        self.assertEqual(rows, []); self.assertIn("Too long", errs[0]["error"])


if __name__ == "__main__":
    unittest.main()
