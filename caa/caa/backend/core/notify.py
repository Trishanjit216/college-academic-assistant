"""In-app notifications for newly published events and new/updated syllabus entries.

Rules (kept here so they are easy to read and test):
  * Event: notified when it becomes PUBLISHED (created published, or draft -> published). Drafts notify nobody.
    Audience: sections (e.g. "A1, A3") if given, else one group, else every student. Faculty/admins are not notified.
  * Syllabus: an entry counts as PUBLISHED once it is VERIFIED and has content or a PDF link
    (set NOTIFY_ON_UNVERIFIED_SYLLABUS=1 to notify on any saved content instead).
    published first time -> "published"; later change to content / PDF link -> "updated"; anything else -> nothing.
  * Duplicates are impossible: every notification carries a dedupe key and the database enforces one per (user, key).
  * Unpublishing or deleting an event, or deleting a syllabus entry, removes its notifications (no dead links).
The pure helpers below need no database. Signal receivers at the bottom wire them to the models."""
import hashlib
import logging
import re
from collections import Counter

log = logging.getLogger(__name__)
SECTION_SPLIT = re.compile(r"[,\s;]+")


# ---------------- pure helpers ----------------
def parse_sections(text):
    """'a1, A3;b2' -> ['A1','A3','B2'] (order kept, duplicates dropped). Raises ValueError for an invalid section."""
    out = []
    for tok in SECTION_SPLIT.split((text or "").strip()):
        if not tok:
            continue
        t = tok.upper()
        if not re.fullmatch(r"[AB](?:[1-9]|1[0-2])", t):
            raise ValueError(f"'{tok}' is not a valid section. Use A1 to A12 or B1 to B12, separated by commas.")
        if t not in out:
            out.append(t)
    return out


def norm_lines(text):
    return [" ".join(l.split()) for l in (text or "").splitlines() if l.strip()]


def norm_content(text):
    return "\n".join(norm_lines(text))


def diff_summary(old, new):
    """'3 lines added, 1 removed' (line-based, whitespace-insensitive)."""
    a, b = Counter(norm_lines(old)), Counter(norm_lines(new))
    added, removed = sum((b - a).values()), sum((a - b).values())
    bits = []
    if added:
        bits.append(f"{added} line{'s' if added != 1 else ''} added")
    if removed:
        bits.append(f"{removed} removed")
    return ", ".join(bits)


def is_published(state, require_verified=True):
    """state: {'content','pdf_url','verified'} or None."""
    if not state:
        return False
    has_material = bool((state.get("content") or "").strip() or (state.get("pdf_url") or "").strip())
    return has_material and (bool(state.get("verified")) or not require_verified)


def syllabus_plan(old, new, require_verified=True):
    """Decide what (if anything) to announce. old/new are state dicts (old None when the entry is new).
    Returns None or {'kind': 'published'|'updated', 'what': str}."""
    if not is_published(new, require_verified):
        return None
    if not is_published(old, require_verified):
        return {"kind": "published", "what": ""}
    changes = []
    if norm_content(old.get("content")) != norm_content(new.get("content")):
        d = diff_summary(old.get("content"), new.get("content"))
        changes.append("Syllabus topics changed" + (f" ({d})" if d else ""))
    o_pdf, n_pdf = (old.get("pdf_url") or "").strip(), (new.get("pdf_url") or "").strip()
    if o_pdf != n_pdf:
        changes.append("Official PDF link " + ("added" if not o_pdf else "removed" if not n_pdf else "changed"))
    if not changes:
        return None
    return {"kind": "updated", "what": ". ".join(changes) + "."}


def short(text, n=140):
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def event_text(name, start, venue, description, published_on):
    """(title, message) for a new event. `start` / `published_on` are already local datetimes / dates."""
    lines = []
    if description:
        lines.append(short(description))
    when = start.strftime("%a %d %b %Y, %I:%M %p").replace(" 0", " ")
    lines.append(f"Event date: {when}" + (f" at {venue}" if venue else ""))
    lines.append(f"Published on {published_on.strftime('%d %b %Y').lstrip('0')}")
    return f"New event: {name}", "\n".join(lines)


def syllabus_text(plan, subject_name, exam_label, published_on):
    if plan["kind"] == "published":
        title = f"Syllabus published: {subject_name} ({exam_label})"
        msg = f"A syllabus has been published for {subject_name} — {exam_label}."
    else:
        title = f"Syllabus updated: {subject_name} ({exam_label})"
        msg = f"The {exam_label} syllabus for {subject_name} has been updated. {plan['what']}".strip()
    return title, f"{msg}\nOn {published_on.strftime('%d %b %Y').lstrip('0')}"


def event_link(event_id):
    return f"/events?event={event_id}"


def syllabus_link(subject_id, exam):
    return f"/syllabus?subject={subject_id}&exam={exam}"


# ---------------- database side ----------------
def _models():
    from .models import Event, Notification, SyllabusEntry, User
    return Event, Notification, SyllabusEntry, User


def event_recipients(event):
    """Active students (and moderators, who are students too) in the event's audience."""
    _, _, _, User = _models()
    qs = User.objects.filter(is_active=True, role__in=[User.STUDENT, User.MODERATOR])
    secs = parse_sections(event.target_sections)
    if secs:
        return qs.filter(section__in=secs)
    if event.target_group_id:
        return qs.filter(group_id=event.target_group_id)
    return qs


def _bulk(users, **fields):
    """Insert one notification per user; the unique (user, dedupe_key) constraint silently drops repeats."""
    _, Notification, _, _ = _models()
    ids = list(users.values_list("id", flat=True)) if hasattr(users, "values_list") else list(users)
    Notification.objects.bulk_create([Notification(user_id=i, **fields) for i in ids], ignore_conflicts=True, batch_size=500)
    return len(ids)


def notify_event_published(event):
    from django.utils import timezone
    title, msg = event_text(event.name, timezone.localtime(event.start), event.venue, event.description, timezone.localdate())
    return _bulk(event_recipients(event), kind="event", title=title[:200], message=msg, link=event_link(event.pk),
                 ref=f"event:{event.pk}", dedupe_key=f"event:{event.pk}:published")


def notify_syllabus(entry, plan):
    from django.utils import timezone
    _, _, _, User = _models()
    title, msg = syllabus_text(plan, entry.subject.name, entry.get_exam_display(), timezone.localdate())
    users = User.objects.filter(is_active=True, role__in=[User.STUDENT, User.MODERATOR])
    return _bulk(users, kind="syllabus", title=title[:200], message=msg, link=syllabus_link(entry.subject_id, entry.exam),
                 ref=f"syllabus:{entry.pk}", dedupe_key=f"syllabus:{entry.pk}:r{entry.revision}")


def remove_for(ref):
    _, Notification, _, _ = _models()
    return Notification.objects.filter(ref=ref).delete()[0]


# ---------------- signal receivers (connected in apps.py) ----------------
def _require_verified():
    from django.conf import settings
    return not getattr(settings, "NOTIFY_ON_UNVERIFIED_SYLLABUS", False)


def event_pre_save(sender, instance, **kw):
    was = None
    if instance.pk:
        was = sender.objects.filter(pk=instance.pk).values_list("is_published", flat=True).first()
    instance._was_published = bool(was)


def event_post_save(sender, instance, created, **kw):
    from django.db import transaction
    was = getattr(instance, "_was_published", False)
    try:
        with transaction.atomic():
            if instance.is_published and (created or not was):
                notify_event_published(instance)
            elif was and not instance.is_published:
                remove_for(f"event:{instance.pk}")        # unpublished: nothing may point at a hidden event
    except Exception:                                          # a notification problem must never block saving the event
        log.exception("event notification failed for event %s", instance.pk)


def event_post_delete(sender, instance, **kw):
    try:
        remove_for(f"event:{instance.pk}")
    except Exception:
        log.exception("could not clean notifications of deleted event %s", instance.pk)


def _state(obj):
    return {"content": obj.content, "pdf_url": obj.pdf_url, "verified": obj.verified}


def syllabus_pre_save(sender, instance, **kw):
    instance._notify_plan = None
    old = None
    if instance.pk:
        row = sender.objects.filter(pk=instance.pk).values("content", "pdf_url", "verified", "revision").first()
        old = row
    plan = syllabus_plan(old, _state(instance), _require_verified())
    if plan:
        instance.revision = ((old or {}).get("revision") or 0) + 1
        instance._notify_plan = plan


def syllabus_post_save(sender, instance, created, **kw):
    from django.db import transaction
    plan = getattr(instance, "_notify_plan", None)
    instance._notify_plan = None
    if not plan:
        return
    try:
        with transaction.atomic():
            notify_syllabus(instance, plan)
    except Exception:
        log.exception("syllabus notification failed for entry %s", instance.pk)


def syllabus_post_delete(sender, instance, **kw):
    try:
        remove_for(f"syllabus:{instance.pk}")
    except Exception:
        log.exception("could not clean notifications of deleted syllabus entry %s", instance.pk)
