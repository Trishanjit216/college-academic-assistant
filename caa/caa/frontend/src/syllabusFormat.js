// Turns the plain-text syllabus an administrator types into structured units/topics/subtopics.
//   Unit 1: Limits            <- a line starting with Unit / Module / Chapter / Part / "1." starts a unit
//   - Epsilon-delta           <- "-", "*" or a bullet is a topic
//   -- Examples               <- "--" is a subtopic of the previous topic
const UNIT_RE = /^(unit|module|chapter|part|section)\b|^\d+\s*[.):]\s+\S/i;

export function parseSyllabus(text) {
  const out = { intro: [], units: [] };
  let unit = null;
  let item = null;
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (/^--+\s*\S/.test(line) || (/^[-*•]\s*[-*•]\s*\S/.test(line))) {
      const sub = line.replace(/^[-*•\s]+/, "");
      if (!unit) { unit = { title: "", items: [] }; out.units.push(unit); }
      if (!item) { item = { text: "", subs: [] }; unit.items.push(item); }
      item.subs.push(sub);
    } else if (/^[-*•]\s*\S/.test(line)) {
      if (!unit) { unit = { title: "", items: [] }; out.units.push(unit); }
      item = { text: line.replace(/^[-*•]\s*/, ""), subs: [] };
      unit.items.push(item);
    } else if (UNIT_RE.test(line)) {
      unit = { title: line, items: [] };
      out.units.push(unit);
      item = null;
    } else if (!unit) {
      out.intro.push(line);
    } else {
      item = { text: line, subs: [] };
      unit.items.push(item);
    }
  }
  return out;
}

export const EXAMS = [
  { key: "mid1", label: "Mid-Term 1" },
  { key: "mid2", label: "Mid-Term 2" },
  { key: "end", label: "End-Semester" },
];
