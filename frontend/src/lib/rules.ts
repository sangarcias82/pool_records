/**
 * Editing norm rules in the SPA: a text draft per row and the minimal PATCH body for it.
 *
 * Bounds are sent as typed ("7,0", "" to clear) and validated by the server (min <= max, physical range, at least
 * one bound), whose translated message is shown; the browser only decides *what changed*.
 */
import type { Classification, NormRule, NormRulePatch } from "../api/types";
import { parseDecimal } from "./evaluation";

export interface RuleDraft {
  min_value: string;
  max_value: string;
  classification: Classification;
  active: boolean;
}

export function draftFromRule(rule: NormRule): RuleDraft {
  return {
    min_value: rule.min_value === null ? "" : String(rule.min_value),
    max_value: rule.max_value === null ? "" : String(rule.max_value),
    classification: rule.classification,
    active: rule.active,
  };
}

/** ``true`` when the typed bound means something else than the stored one (unparseable text counts as a change). */
function boundChanged(text: string, stored: number | null): boolean {
  const parsed = parseDecimal(text);
  return Number.isNaN(parsed) || parsed !== stored;
}

/** PATCH body with only the changed fields; empty object when nothing changed. */
export function ruleChanges(rule: NormRule, draft: RuleDraft): NormRulePatch {
  const patch: NormRulePatch = {};
  if (boundChanged(draft.min_value, rule.min_value)) patch.min_value = draft.min_value.trim() === "" ? null : draft.min_value;
  if (boundChanged(draft.max_value, rule.max_value)) patch.max_value = draft.max_value.trim() === "" ? null : draft.max_value;
  if (draft.classification !== rule.classification) patch.classification = draft.classification;
  if (draft.active !== rule.active) patch.active = draft.active;
  return patch;
}
