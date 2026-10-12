import { Field } from "./ui.jsx";
import { sectionsFor } from "../sections.js";

/** Group + Section pickers. The section list depends on the group, is disabled until a group is chosen,
 *  and is cleared whenever the group changes so an invalid combination can't remain selected. */
export default function GroupSection({ groups, group, section, onChange, idPrefix = "" }) {
  const g = groups.find((x) => String(x.id) === String(group));
  const options = g ? sectionsFor(g.name) : [];
  const noSections = g && options.length === 0;
  return (
    <>
      <Field label="Lab group (optional)" htmlFor={`${idPrefix}group`}>
        <select id={`${idPrefix}group`} value={group} onChange={(e) => onChange({ group: e.target.value, section: "" })}>
          <option value="">Select your group</option>
          {groups.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
      </Field>
      <Field label="Section (optional)" htmlFor={`${idPrefix}section`}
        hint={!g ? "Choose your group first to pick a section." : noSections ? "This group has no sections." : undefined}>
        <select id={`${idPrefix}section`} value={section} disabled={!g || noSections}
          onChange={(e) => onChange({ group, section: e.target.value })}>
          <option value="">{!g ? "Select your group first" : noSections ? "No sections for this group" : "Select your section"}</option>
          {options.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </Field>
    </>
  );
}
