"""Best-effort suggestions from an institute's seat-allotment PDF.

IMPORTANT: this only *suggests* rows. Layouts differ between institutes, so the output is shown to an authorised
person who must review/correct it before anything is saved, and nothing is published automatically.
Text extraction needs the `pypdf` package; scanned (image-only) PDFs contain no text and need OCR, which is not
available here - the caller is told so instead of getting invented data."""
import io
import re

ROOM_RE = re.compile(r"\b(?:room|hall|lab|rm)\b\.?\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z]{0,3}[\-/]?\d{1,4}[A-Za-z]?|[A-Z][A-Za-z0-9\-/]{0,12})", re.I)
RANGE_RE = re.compile(r"([A-Za-z0-9]*\d)\s*(?:to|-|–|—|till|upto)\s*([A-Za-z0-9]*\d)", re.I)
SECTION_RE = re.compile(r"\b(?:section|sec\.?)\s*[:\-]?\s*([A-Za-z]\s?\d{1,2})\b|\b([AB]\d{1,2})\b")
MAX_LINES = 4000


class ExtractionUnavailable(Exception):
    pass


def extract_text(data):
    try:
        from pypdf import PdfReader
    except ImportError as e:                                          # pragma: no cover
        raise ExtractionUnavailable("Automatic extraction is not installed on the server. Use CSV import instead.") from e
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        raise ExtractionUnavailable("This PDF could not be read for text extraction.") from e


def suggest_rows(text):
    """-> {"text_found": bool, "rows": [...], "ignored": int}. Each row carries the source line for checking."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()][:MAX_LINES]
    if not lines:
        return {"text_found": False, "rows": [], "ignored": 0}
    rows, ignored = [], 0
    room = section = ""
    for line in lines:
        m_room = ROOM_RE.search(line)
        m_sec = SECTION_RE.search(line)
        ranges = [r for r in RANGE_RE.findall(line)
                  if not (m_room and r[0] in m_room.group(0) and r[1] in m_room.group(0))]
        if m_sec:
            section = (m_sec.group(1) or m_sec.group(2)).replace(" ", "").upper()
        if m_room:
            room = m_room.group(1).strip()
        if not ranges:
            if not (m_room or m_sec):
                ignored += 1
            continue
        if not room:
            ignored += 1
            continue
        for a, b in ranges:
            rows.append({"section": section, "roll_from": a.upper(), "roll_to": b.upper(), "room": room,
                         "seat": "", "note": "", "source": line[:160]})
    return {"text_found": True, "rows": rows, "ignored": ignored}
