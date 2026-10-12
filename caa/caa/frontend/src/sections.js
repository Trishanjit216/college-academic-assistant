// Group -> section rules. Must match backend/core/sections.py.
const GROUP_RE = /^\s*group\s+([A-Za-z])\s*$/i;

export function groupLetter(name) {
  const m = GROUP_RE.exec(name || "");
  return m ? m[1].toUpperCase() : null;
}

export function sectionsFor(name) {
  const l = groupLetter(name);
  return l === "A" || l === "B" ? Array.from({ length: 12 }, (_, i) => `${l}${i + 1}`) : [];
}

/** Returns an error message, or "" when (group, section) is a valid combination. */
export function checkSection(groupName, section) {
  if (!section) return "";
  if (!groupName) return "Select your group before choosing a section.";
  const list = sectionsFor(groupName);
  if (!list.length) return "Sections are only available for Group A and Group B.";
  if (!list.includes(section)) return `Section ${section} does not belong to ${groupName}.`;
  return "";
}
