"""Exam seat-allotment rules. Pure Python (no Django) so the logic is unit-tested.

An allotment is a list of rows. A row is either
  * an individual row   (roll_to empty):   one roll number -> room (and optionally a seat), or
  * a range row         (roll_to filled):  every roll number from roll_from to roll_to -> room.
Roll numbers must end in digits (e.g. 21CS017, 2026BTECH045); a range needs the same prefix on both ends.
An optional section limits a row to students of that section (rows without a section apply to everyone).
Individual rows are exceptions and win over range rows; among ranges the narrowest wins.
Nothing here ever invents a room or a seat."""
import csv
import io
import re

_ROLL = re.compile(r"^(.*?)(\d+)$")
LIMITS = {"section": 10, "roll_from": 30, "roll_to": 30, "room": 60, "seat": 30, "note": 300}
MAX_ROWS = 5000
MAX_BYTES = 1_000_000


class ImportProblem(Exception):
    pass


def norm(value):
    return "".join(str(value or "").split()).upper()


def parse_roll(value):
    """-> (prefix, number) or None when the roll number does not end in digits."""
    m = _ROLL.match(norm(value))
    return (m.group(1), int(m.group(2))) if m else None


def _scope_ok(row_section, student_section):
    rs = norm(row_section)
    return not rs or rs == norm(student_section)


def _span(row):
    lo, hi = parse_roll(row["roll_from"]), parse_roll(row["roll_to"])
    return lo, hi


def validate_row(row):
    """List of problems with one row (empty list = fine)."""
    errs = []
    if not norm(row.get("roll_from")):
        errs.append("Roll number is required")
    if not str(row.get("room") or "").strip():
        errs.append("Room is required")
    for k, m in LIMITS.items():
        if len(str(row.get(k) or "")) > m:
            errs.append(f"{k} is too long")
    if norm(row.get("roll_to")):
        lo, hi = _span(row)
        if not lo or not hi:
            errs.append("Roll numbers in a range must end in digits")
        elif lo[0] != hi[0]:
            errs.append("Both ends of a range need the same prefix")
        elif lo[1] > hi[1]:
            errs.append("Range start is after range end")
    return errs


def resolve(roll, section, rows):
    """Best matching row for one student, or None. Never guesses."""
    roll = norm(roll)
    cand = [r for r in rows if _scope_ok(r.get("section"), section)]
    singles = [r for r in cand if not norm(r.get("roll_to")) and norm(r["roll_from"]) == roll]
    if singles:
        singles.sort(key=lambda r: 0 if norm(r.get("section")) else 1)      # section-specific first
        return dict(singles[0], kind="individual")
    p = parse_roll(roll)
    if not p:
        return None
    best = None
    for r in cand:
        if not norm(r.get("roll_to")):
            continue
        lo, hi = _span(r)
        if lo and hi and lo[0] == hi[0] == p[0] and lo[1] <= p[1] <= hi[1]:
            width = hi[1] - lo[1]
            if best is None or width < best[0]:
                best = (width, r)
    return dict(best[1], kind="range") if best else None


def find_conflicts(rows):
    """Human-readable problems that must be fixed before publishing."""
    out = []
    singles, ranges = {}, []
    for i, r in enumerate(rows, 1):
        for e in validate_row(r):
            out.append(f"Row {r.get('id') or i}: {e}")
        if norm(r.get("roll_to")):
            ranges.append(r)
        else:
            key = (norm(r.get("section")), norm(r.get("roll_from")))
            if key in singles:
                out.append(f"{key[1]}{' (' + key[0] + ')' if key[0] else ''} is listed twice")
            singles[key] = r
    for i, a in enumerate(ranges):
        for b in ranges[i + 1:]:
            la, ha = _span(a)
            lb, hb = _span(b)
            if not (la and ha and lb and hb) or la[0] != lb[0]:
                continue
            sa, sb = norm(a.get("section")), norm(b.get("section"))
            if sa and sb and sa != sb:
                continue
            if la[1] <= hb[1] and lb[1] <= ha[1] and str(a["room"]).strip().lower() != str(b["room"]).strip().lower():
                out.append(f"Ranges {norm(a['roll_from'])}-{norm(a['roll_to'])} ({a['room']}) and "
                           f"{norm(b['roll_from'])}-{norm(b['roll_to'])} ({b['room']}) overlap with different rooms")
    return out


_ALIASES = {"roll_no": "roll_from", "roll": "roll_from", "from": "roll_from", "to": "roll_to",
            "range_from": "roll_from", "range_to": "roll_to", "hall": "room", "bench": "seat", "notes": "note",
            "instructions": "note"}


def parse_csv(text):
    """-> (rows, errors). Required columns: roll_from (or roll_no) and room. Optional: roll_to, section, seat, note."""
    if not isinstance(text, str) or not text.strip():
        raise ImportProblem("The file is empty.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ImportProblem("The file is too large (limit 1 MB).")
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    heads = [_ALIASES.get((h or "").strip().lower(), (h or "").strip().lower()) for h in (reader.fieldnames or [])]
    missing = [c for c in ("roll_from", "room") if c not in heads]
    if missing:
        raise ImportProblem("Missing column(s): " + ", ".join(missing)
                            + ". Expected: roll_from (or roll_no), room; optional roll_to, section, seat, note.")
    reader.fieldnames = heads
    rows, errors = [], []
    for n, raw in enumerate(reader, start=2):
        if n - 1 > MAX_ROWS:
            raise ImportProblem(f"Too many rows (limit {MAX_ROWS}).")
        rec = {k: (v or "").strip() for k, v in raw.items() if k}
        if not any(rec.values()):
            continue
        row = {k: rec.get(k, "") for k in ("section", "roll_from", "roll_to", "room", "seat", "note")}
        row["roll_from"], row["roll_to"] = norm(row["roll_from"]), norm(row["roll_to"])
        row["section"] = norm(row["section"])
        errs = validate_row(row)
        if errs:
            errors.append({"row": n, "error": "; ".join(errs)})
        else:
            rows.append(row)
    return rows, errors
