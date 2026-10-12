"""Bring an existing database up to date WITHOUT committed migrations.

This project regenerates migrations on every deploy (`makemigrations && migrate`), and an already-deployed
database treats the regenerated 0001 as applied, so models/columns added later would never reach it.
`ensure_schema()` is idempotent: it creates missing tables and the missing User.section column, and does
nothing on a database that is already up to date (including a fresh one built by `migrate`)."""
from django.db import connection

from .models import SeatAllotment, SyllabusEntry, User


def ensure_schema():
    done = []
    with connection.cursor() as cur:
        tables = set(connection.introspection.table_names(cur))
        cols = {c.name for c in connection.introspection.get_table_description(cur, User._meta.db_table)}
    missing = [m for m in (SyllabusEntry, SeatAllotment) if m._meta.db_table not in tables]
    need_section = "section" not in cols
    if not missing and not need_section:
        return done                      # already up to date: don't even open a schema editor
    with connection.schema_editor() as editor:
        for model in missing:
            editor.create_model(model)
            done.append(model._meta.db_table)
        if need_section:
            editor.add_field(User, User._meta.get_field("section"))
            done.append("user.section")
    return done
