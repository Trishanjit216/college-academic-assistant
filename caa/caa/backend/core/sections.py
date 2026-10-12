"""Group / section rules for the sign-up and profile forms. Pure Python (no Django) so it is easy to test.

Group "Group A" allows sections A1..A12, "Group B" allows B1..B12. A section can never be saved without a
matching group, so an invalid combination cannot exist."""
import re

_GROUP_RE = re.compile(r"^\s*group\s+([A-Za-z])\s*$", re.I)
SECTION_COUNT = 12


def group_letter(group_name):
    m = _GROUP_RE.match(group_name or "")
    return m.group(1).upper() if m else None


def allowed_sections(group_name):
    letter = group_letter(group_name)
    return [f"{letter}{i}" for i in range(1, SECTION_COUNT + 1)] if letter in ("A", "B") else []


def check(group_name, section):
    """Return an error message, or None when (group, section) is a valid combination. Empty section is fine."""
    section = (section or "").strip().upper()
    if not section:
        return None
    if not group_name:
        return "Select your group before choosing a section."
    allowed = allowed_sections(group_name)
    if not allowed:
        return "Sections are only available for Group A and Group B."
    if section not in allowed:
        return f"Section {section} does not belong to {group_name}. Choose {allowed[0]} to {allowed[-1]}."
    return None
