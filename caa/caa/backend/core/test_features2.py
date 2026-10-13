"""Pure-Python tests (no Django):  cd backend && python3 -m unittest core.test_features2"""
import unittest

from datetime import date

from . import allotment, attendance_calc as ac, pdf_extract


def R(**k):
    base = {"section": "", "roll_from": "", "roll_to": "", "room": "", "seat": "", "note": ""}
    base.update(k)
    return base


class Allotment(unittest.TestCase):
    rows = [R(roll_from="21CS001", roll_to="21CS060", room="Room 204"),
            R(roll_from="21CS061", roll_to="21CS120", room="Room 205"),
            R(roll_from="21CS017", room="Room 301", seat="B4", note="Special arrangement")]

    def test_range_individual_and_exception_priority(self):
        self.assertEqual(allotment.resolve("21cs005", "", self.rows)["room"], "Room 204")
        self.assertEqual(allotment.resolve("21 CS 061", "", self.rows)["room"], "Room 205")
        m = allotment.resolve("21CS017", "", self.rows)
        self.assertEqual((m["room"], m["seat"], m["kind"]), ("Room 301", "B4", "individual"))

    def test_no_match_is_none_not_a_guess(self):
        self.assertIsNone(allotment.resolve("21CS999", "", self.rows))
        self.assertIsNone(allotment.resolve("22CS005", "", self.rows))      # other prefix
        self.assertIsNone(allotment.resolve("ABC", "", self.rows))
        self.assertIsNone(allotment.resolve("21CS005", "", []))

    def test_section_scope(self):
        rows = [R(section="A1", roll_from="1", roll_to="30", room="R1"), R(section="A2", roll_from="1", roll_to="30", room="R2")]
        self.assertEqual(allotment.resolve("5", "A1", rows)["room"], "R1")
        self.assertEqual(allotment.resolve("5", "a2", rows)["room"], "R2")
        self.assertIsNone(allotment.resolve("5", "B1", rows))
        self.assertIsNone(allotment.resolve("5", "", rows))

    def test_narrowest_range_wins(self):
        rows = [R(roll_from="1", roll_to="100", room="Hall"), R(roll_from="10", roll_to="20", room="Lab")]
        self.assertEqual(allotment.resolve("15", "", rows)["room"], "Lab")
        self.assertEqual(allotment.resolve("50", "", rows)["room"], "Hall")

    def test_validation(self):
        self.assertEqual(allotment.validate_row(R(roll_from="1", room="R")), [])
        self.assertTrue(allotment.validate_row(R(roll_from="", room="R")))
        self.assertTrue(allotment.validate_row(R(roll_from="1", room="")))
        self.assertIn("after", " ".join(allotment.validate_row(R(roll_from="9", roll_to="2", room="R"))))
        self.assertIn("prefix", " ".join(allotment.validate_row(R(roll_from="A1", roll_to="B9", room="R"))))
        self.assertIn("digits", " ".join(allotment.validate_row(R(roll_from="ABC", roll_to="XYZ", room="R"))))

    def test_conflicts(self):
        self.assertEqual(allotment.find_conflicts(self.rows), [])
        dup = self.rows + [R(roll_from="21cs017", room="Room 9")]
        self.assertTrue(any("twice" in c for c in allotment.find_conflicts(dup)))
        over = self.rows + [R(roll_from="21CS050", roll_to="21CS070", room="Room 999")]
        self.assertTrue(any("overlap" in c for c in allotment.find_conflicts(over)))
        same_room = self.rows + [R(roll_from="21CS040", roll_to="21CS055", room="room 204")]
        self.assertEqual([c for c in allotment.find_conflicts(same_room) if "overlap" in c], [])
        diff_sec = [R(section="A1", roll_from="1", roll_to="9", room="X"), R(section="A2", roll_from="1", roll_to="9", room="Y")]
        self.assertEqual(allotment.find_conflicts(diff_sec), [])

    def test_csv(self):
        rows, errs = allotment.parse_csv("roll_no,roll_to,room,seat,section\n21CS001,21CS060,Room 204,,a1\n21CS017,,Room 301,B4,\n,,,,\n21CS009,,,3,\n")
        self.assertEqual(len(rows), 2); self.assertEqual(rows[0]["section"], "A1"); self.assertEqual(len(errs), 1)
        with self.assertRaises(allotment.ImportProblem):
            allotment.parse_csv("a,b\n1,2")
        with self.assertRaises(allotment.ImportProblem):
            allotment.parse_csv("")


class PdfExtract(unittest.TestCase):
    TEXT = "SAMPLE LAYOUT (test only)\nRoom 204\nA1: 21CS001 - 21CS030\nA2: 21CS031 to 21CS060\nHall 3 : 21CS061-21CS090 Section B1\nsome footer line\n"

    def test_suggestions_have_sources_and_are_not_invented(self):
        out = pdf_extract.suggest_rows(self.TEXT)
        self.assertTrue(out["text_found"])
        got = [(r["section"], r["roll_from"], r["roll_to"], r["room"]) for r in out["rows"]]
        self.assertIn(("A1", "21CS001", "21CS030", "204"), got)
        self.assertIn(("A2", "21CS031", "21CS060", "204"), got)
        self.assertTrue(all(r["source"] for r in out["rows"]))
        self.assertGreaterEqual(out["ignored"], 1)

    def test_empty_text_means_scanned(self):
        self.assertFalse(pdf_extract.suggest_rows("   \n")["text_found"])

    def test_real_pdf_round_trip(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("reportlab missing")
        import io
        buf = io.BytesIO(); c = canvas.Canvas(buf)
        for i, line in enumerate(self.TEXT.splitlines()):
            c.drawString(50, 780 - i * 18, line)
        c.save()
        text = pdf_extract.extract_text(buf.getvalue())
        self.assertTrue(len(pdf_extract.suggest_rows(text)["rows"]) >= 3)
        with self.assertRaises(pdf_extract.ExtractionUnavailable):
            pdf_extract.extract_text(b"not a pdf")


class Attendance(unittest.TestCase):
    D = lambda self, m, d: date(2026, m, d)

    def rec(self, status, m=10, d=1, subject=None, reason=""):
        return {"date": self.D(m, d), "subject": subject, "status": status, "reason": reason}

    def test_formula_excludes_holidays_and_missing(self):
        s = ac.summarize([self.rec("present", d=1), self.rec("present", d=2), self.rec("absent", d=3, reason="illness"),
                          self.rec("holiday", d=4), self.rec("holiday", d=5)])
        self.assertEqual((s["present"], s["absent"], s["holiday"], s["counted"]), (2, 1, 2, 3))
        self.assertEqual(s["percentage"], 66.7)

    def test_not_enough_data(self):
        self.assertIsNone(ac.summarize([])["percentage"])
        self.assertIsNone(ac.summarize([self.rec("holiday")])["percentage"])
        self.assertEqual(ac.summarize([])["insights"], ["Record a few days to see your attendance summary."])

    def test_subject_wise_independent(self):
        s = ac.summarize([self.rec("present", subject=1), self.rec("absent", d=2, subject=1), self.rec("present", d=3, subject=2),
                          self.rec("present", d=4, subject=2)])
        by = {x["subject"]: x["percentage"] for x in s["subjects"]}
        self.assertEqual(by, {1: 50.0, 2: 100.0}); self.assertEqual(s["percentage"], 75.0)

    def test_months_and_reasons(self):
        s = ac.summarize([self.rec("absent", m=9, reason="illness"), self.rec("absent", m=10, d=2, reason="illness"),
                          self.rec("absent", m=10, d=3, reason="family"), self.rec("present", m=10, d=4)])
        self.assertEqual([m["month"] for m in s["months"]], ["2026-09", "2026-10"])
        self.assertEqual(s["reasons"][0], {"reason": "illness", "label": "Illness", "count": 2})

    def test_estimates(self):
        self.assertEqual(ac.sessions_needed(6, 4, 75), 6)          # (6+6)/(10+6)=75%
        self.assertEqual(ac.sessions_needed(9, 1, 75), 0)
        self.assertIsNone(ac.sessions_needed(6, 4, 100)); self.assertEqual(ac.sessions_needed(10, 0, 100), 0)
        self.assertIsNone(ac.sessions_needed(0, 0, 75)); self.assertIsNone(ac.sessions_needed(5, 5, 0))
        self.assertEqual(ac.can_miss(9, 1, 75), 2)                 # 9/12 = 75%
        self.assertEqual(ac.can_miss(5, 5, 75), 0)

    def test_target_insights_labelled_as_estimates(self):
        s = ac.summarize([self.rec("present"), self.rec("absent", d=2, reason="illness")], target=75)
        txt = " ".join(s["insights"])
        self.assertIn("estimate", txt); self.assertIn("recorded 1 absence", txt)
        self.assertIn("not your official", s["target"]["note"])


if __name__ == "__main__":
    unittest.main()
