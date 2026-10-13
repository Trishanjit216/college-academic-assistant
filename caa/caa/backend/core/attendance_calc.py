"""Attendance maths for the personal tracker. Pure Python.

percentage = present / (present + absent) * 100.   Holidays are left out of the denominator.
Sessions with no record are NOT counted (they are neither present nor absent). With no present+absent
sessions the percentage is None ("Not enough data"). Every figure is based on self-recorded data."""
import math
from collections import Counter, defaultdict

PRESENT, ABSENT, HOLIDAY = "present", "absent", "holiday"
REASONS = {"illness": "Illness", "personal": "Personal reason", "family": "Family reason",
           "transport": "Transport or travel issue", "college": "College event or approved activity", "other": "Other"}


def percent(present, absent):
    d = present + absent
    return None if d == 0 else round(present / d * 100, 1)


def sessions_needed(present, absent, target):
    """Consecutive future sessions to attend to reach `target` %. 0 = already there; None = not reachable."""
    if not 0 < target <= 100 or present + absent == 0:
        return None
    if present / (present + absent) * 100 >= target:
        return 0
    if target >= 100:
        return None
    return math.ceil((target / 100 * (present + absent) - present) / (1 - target / 100))


def can_miss(present, absent, target):
    """How many further sessions could be missed while staying at or above `target` % (0 if already below)."""
    if not 0 < target <= 100 or present == 0:
        return None
    if present / (present + absent) * 100 < target:
        return 0
    return max(0, math.floor(present / (target / 100) - present - absent))


def summarize(records, target=None):
    """records: iterable of dicts {date (datetime.date), subject (id or None), status, reason}."""
    recs = list(records)
    c = Counter(r["status"] for r in recs)
    p, a, h = c[PRESENT], c[ABSENT], c[HOLIDAY]
    by_subject, by_month, reasons = defaultdict(Counter), defaultdict(Counter), Counter()
    for r in recs:
        by_subject[r.get("subject")][r["status"]] += 1
        by_month[r["date"].strftime("%Y-%m")][r["status"]] += 1
        if r["status"] == ABSENT:
            reasons[r.get("reason") or "unspecified"] += 1
    out = {
        "total": len(recs), "present": p, "absent": a, "holiday": h,
        "counted": p + a, "percentage": percent(p, a),
        "subjects": [{"subject": s, "present": v[PRESENT], "absent": v[ABSENT], "holiday": v[HOLIDAY],
                      "percentage": percent(v[PRESENT], v[ABSENT])} for s, v in by_subject.items()],
        "months": [{"month": m, "present": v[PRESENT], "absent": v[ABSENT], "holiday": v[HOLIDAY],
                    "percentage": percent(v[PRESENT], v[ABSENT])} for m, v in sorted(by_month.items())],
        "reasons": [{"reason": k, "label": REASONS.get(k, "Not specified"), "count": n} for k, n in reasons.most_common()],
        "basis": "Present sessions ÷ (present + absent sessions). Holidays and days with no record are not counted.",
    }
    if target:
        out["target"] = {"percent": target, "attend_needed": sessions_needed(p, a, target), "can_miss": can_miss(p, a, target),
                         "note": "An estimate from your own records, not your official college attendance."}
    out["insights"] = insights(out)
    return out


def insights(s):
    tips = []
    if s["counted"] == 0:
        return ["Record a few days to see your attendance summary."]
    months = s["months"]
    if months and months[-1]["absent"]:
        n = months[-1]["absent"]
        tips.append(f"You recorded {n} absence{'s' if n != 1 else ''} in {months[-1]['month']}. "
                    "Review the reasons and plan your upcoming classes.")
    if s["reasons"]:
        top = s["reasons"][0]
        tips.append(f"Your most common recorded reason for absence is \"{top['label']}\" ({top['count']}).")
    if s["percentage"] is not None:
        t = s.get("target")
        if t and t["attend_needed"]:
            tips.append(f"To reach {t['percent']:g}% you would need to attend about {t['attend_needed']} more "
                        "session(s) in a row (an estimate from your own records).")
        elif t and t["attend_needed"] == 0 and t["can_miss"] is not None:
            tips.append(f"You are at or above {t['percent']:g}%. You could miss roughly {t['can_miss']} more session(s) "
                        "and stay there (an estimate).")
    t = s.get("target")
    if t:
        low = [x for x in s["subjects"] if x["subject"] is not None and x["percentage"] is not None and x["percentage"] < t["percent"]]
        if low:
            tips.append(f"{len(low)} subject(s) are below your {t['percent']:g}% target in your own records. Check them first.")
    return tips or ["Keep recording regularly to see trends."]
