"""Bring an existing database up to date WITHOUT committed migrations.

This project regenerates migrations on every deploy (`makemigrations && migrate`), and an already-deployed
database treats the regenerated 0001 as applied, so models/columns added later would never reach it.
`ensure_schema()` is idempotent: it creates missing tables and the missing User.section column, and does
nothing on a database that is already up to date (including a fresh one built by `migrate`)."""
from django.db import connection

from .models import AllotmentRow, AttendanceRecord, Event, Exam, ExamDocument, ExamManager, Notification, SyllabusEntry, User

NEW_MODELS = (SyllabusEntry, Exam, ExamDocument, ExamManager, AllotmentRow, AttendanceRecord)   # order matters (FKs)


# columns added to tables that already exist on a deployed database
NEW_COLUMNS = (
    (Notification, "kind"), (Notification, "link"), (Notification, "ref"), (Notification, "dedupe_key"),
    (Event, "is_published"), (Event, "target_group"), (Event, "target_sections"),
    (SyllabusEntry, "revision"),
)


def _columns(cur, model):
    return {c.name for c in connection.introspection.get_table_description(cur, model._meta.db_table)}


def ensure_schema():
    done = []
    with connection.cursor() as cur:
        tables = set(connection.introspection.table_names(cur))
        missing = [m for m in NEW_MODELS if m._meta.db_table not in tables]
        cols = {m: _columns(cur, m) for m in {User, Notification, Event, SyllabusEntry} if m._meta.db_table in tables}
        add = [(m, f) for m, f in NEW_COLUMNS if m in cols and m._meta.get_field(f).column not in cols[m]]
        need_section = "section" not in cols.get(User, {"section"})
        constraint = next(c for c in Notification._meta.constraints if c.name == "core_notif_user_dedupe_uniq")
        need_constraint = Notification in cols and constraint.name not in connection.introspection.get_constraints(cur, Notification._meta.db_table)
    if not (missing or need_section or add or need_constraint):
        return done                      # already up to date: don't even open a schema editor
    with connection.schema_editor() as editor:
        for model in missing:
            editor.create_model(model)
            done.append(model._meta.db_table)
        if need_section:
            editor.add_field(User, User._meta.get_field("section"))
            done.append("user.section")
        for m, f in add:
            editor.add_field(m, m._meta.get_field(f))
            done.append(f"{m._meta.db_table}.{f}")
        if need_constraint:
            editor.add_constraint(Notification, constraint)
            done.append("notification unique constraint")
    return done


INDEX = "core_user_section_roll_uniq"


def ensure_roll_unique_index():
    """DB-level guarantee: one roll number per section (case-insensitive). Returns (status, duplicates)."""
    from django.db import DatabaseError, connection as conn, transaction
    dups = duplicate_rolls()
    if dups:
        return "skipped: duplicate roll numbers exist, fix them first", dups
    sql = (f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON {User._meta.db_table} (section, UPPER(roll_no)) "
           "WHERE roll_no <> '' AND section <> ''")
    try:
        with transaction.atomic(), conn.cursor() as cur:
            cur.execute(sql)
    except DatabaseError as e:
        return f"not created: {e}", dups
    return "ok", dups


def duplicate_rolls():
    """[(section, roll_no, count)] for accounts that share a roll number inside one section."""
    from collections import Counter
    c = Counter()
    for sec, roll in User.objects.exclude(roll_no="").exclude(section="").values_list("section", "roll_no"):
        c[(sec, "".join(roll.split()).upper())] += 1
    return [(s, r, n) for (s, r), n in sorted(c.items()) if n > 1]
