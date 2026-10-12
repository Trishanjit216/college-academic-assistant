"""Parse and validate exam seat-allotment CSV data. Pure Python (no Django) so it can be unit-tested.

Required columns: roll_no, exam_name, room, seat. Optional: student_name, exam_date (YYYY-MM-DD), instructions.
Nothing is invented: rows with missing required values or bad dates are rejected and reported, and duplicate
(roll_no, exam_name, exam_date) rows inside one file are rejected except the first occurrence."""
import csv
import io
from datetime import date

REQUIRED = ("roll_no", "exam_name", "room", "seat")
OPTIONAL = ("student_name", "exam_date", "instructions")
MAX_ROWS = 5000
MAX_BYTES = 1_000_000
LIMITS = {"roll_no": 30, "student_name": 150, "exam_name": 150, "room": 60, "seat": 30, "instructions": 500}


class ImportProblem(Exception):
    pass


def normalize_roll(value):
    return "".join((value or "").split()).upper()


def parse_csv(text):
    """Return (rows, errors). rows are clean dicts ready to save; errors are {"row": n, "error": str}."""
    if not isinstance(text, str) or not text.strip():
        raise ImportProblem("The file is empty.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ImportProblem("The file is too large (limit 1 MB).")
    text = text.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise ImportProblem("Missing column(s): " + ", ".join(missing) + ". Expected: "
                            + ", ".join(REQUIRED + OPTIONAL) + ".")
    reader.fieldnames = headers
    rows, errors, seen = [], [], set()
    for n, raw in enumerate(reader, start=2):             # row 1 is the header
        if n - 1 > MAX_ROWS:
            raise ImportProblem(f"Too many rows (limit {MAX_ROWS}).")
        rec = {k: (v or "").strip() for k, v in raw.items() if k}
        if not any(rec.values()):
            continue
        blank = [c for c in REQUIRED if not rec.get(c)]
        if blank:
            errors.append({"row": n, "error": "Missing " + ", ".join(blank)})
            continue
        long = [c for c, m in LIMITS.items() if len(rec.get(c, "")) > m]
        if long:
            errors.append({"row": n, "error": "Too long: " + ", ".join(long)})
            continue
        d = None
        if rec.get("exam_date"):
            try:
                d = date.fromisoformat(rec["exam_date"])
            except ValueError:
                errors.append({"row": n, "error": "exam_date must be YYYY-MM-DD"})
                continue
        roll = normalize_roll(rec["roll_no"])
        key = (roll, rec["exam_name"].lower(), d)
        if key in seen:
            errors.append({"row": n, "error": f"Duplicate of an earlier row for {roll} / {rec['exam_name']}"})
            continue
        seen.add(key)
        rows.append({"roll_no": roll, "exam_name": rec["exam_name"], "exam_date": d, "room": rec["room"],
                     "seat": rec["seat"], "student_name": rec.get("student_name", ""),
                     "instructions": rec.get("instructions", "")})
    return rows, errors
