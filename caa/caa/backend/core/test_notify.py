"""Pure tests for the notification rules (no Django):  cd backend && python3 -m unittest core.test_notify"""
import unittest
from datetime import date, datetime

from . import notify as n


class Sections(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(n.parse_sections("a1, A3;b2  a1"), ["A1", "A3", "B2"])
        self.assertEqual(n.parse_sections(""), [])
        for bad in ("A13", "C1", "A0", "group a"):
            with self.assertRaises(ValueError):
                n.parse_sections(bad)


S = lambda content="Unit 1\n- Limits", pdf="", verified=True: {"content": content, "pdf_url": pdf, "verified": verified}


class SyllabusPlan(unittest.TestCase):
    def test_new_verified_is_published(self):
        self.assertEqual(n.syllabus_plan(None, S())["kind"], "published")

    def test_unverified_or_empty_draft_notifies_nobody(self):
        self.assertIsNone(n.syllabus_plan(None, S(verified=False)))
        self.assertIsNone(n.syllabus_plan(None, S(content="  \n", verified=True)))
        self.assertIsNone(n.syllabus_plan(S(verified=False), S("Unit 1\n- Other", verified=False)))     # editing a draft
        self.assertEqual(n.syllabus_plan(None, S(verified=False), require_verified=False)["kind"], "published")

    def test_verifying_an_existing_entry_publishes_it(self):
        self.assertEqual(n.syllabus_plan(S(verified=False), S(verified=True))["kind"], "published")

    def test_unchanged_or_whitespace_only_is_silent(self):
        self.assertIsNone(n.syllabus_plan(S(), S()))
        self.assertIsNone(n.syllabus_plan(S("Unit 1\n- Limits"), S("Unit 1  \r\n\n-   Limits\n")))
        self.assertIsNone(n.syllabus_plan(S(pdf="https://x.org/a.pdf"), S(pdf=" https://x.org/a.pdf ")))

    def test_real_change_is_an_update_with_description(self):
        p = n.syllabus_plan(S("Unit 1\n- Limits"), S("Unit 1\n- Limits\n- Continuity\nUnit 2\n- Series"))
        self.assertEqual(p["kind"], "updated")
        self.assertIn("3 lines added", p["what"])
        p = n.syllabus_plan(S("Unit 1\n- Limits\n- Old"), S("Unit 1\n- Limits"))
        self.assertIn("1 removed", p["what"])
        self.assertIn("added", n.syllabus_plan(S(), S(pdf="https://x.org/a.pdf"))["what"])
        self.assertIn("changed", n.syllabus_plan(S(pdf="https://x.org/a.pdf"), S(pdf="https://x.org/b.pdf"))["what"])
        self.assertIn("removed", n.syllabus_plan(S(pdf="https://x.org/a.pdf"), S(pdf=""))["what"])

    def test_verified_flag_toggled_off_or_unrelated_fields_do_not_notify(self):
        self.assertIsNone(n.syllabus_plan(S(), S(verified=False)))


class Texts(unittest.TestCase):
    def test_event_text_has_title_description_date_and_publication_date(self):
        t, m = n.event_text("Hackathon", datetime(2026, 11, 12, 10, 0), "Hall A", "Build things. " * 30, date(2026, 10, 17))
        self.assertEqual(t, "New event: Hackathon")
        self.assertIn("Event date: Thu 12 Nov 2026, 10:00 AM at Hall A", m)
        self.assertIn("Published on 17 Oct 2026", m)
        self.assertIn("…", m)

    def test_syllabus_text_new_vs_update(self):
        t, m = n.syllabus_text({"kind": "published", "what": ""}, "Maths", "Mid-Term 1", date(2026, 10, 17))
        self.assertIn("published", t.lower()); self.assertIn("A syllabus has been published", m)
        t, m = n.syllabus_text({"kind": "updated", "what": "Syllabus topics changed (1 line added)."}, "Maths", "Mid-Term 1", date(2026, 10, 17))
        self.assertIn("updated", t.lower()); self.assertIn("1 line added", m)

    def test_links(self):
        self.assertEqual(n.event_link(5), "/events?event=5")
        self.assertEqual(n.syllabus_link(2, "mid1"), "/syllabus?subject=2&exam=mid1")


if __name__ == "__main__":
    unittest.main()
