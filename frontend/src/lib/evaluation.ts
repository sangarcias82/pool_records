/**
 * Browser mirror of the server's create-time evaluation (app/services/evaluation.py) and decimal parsing
 * (app/utils.parse_float). Used for the live preview of the capture form; the server evaluates again on save
 * and its result is the one stored.
 *
 * Both implementations run the same cases: ./evaluation.cases.json (vitest here, pytest on the server).
 */
import type { Classification, Direction, MeasurementStatus, NormRule, WaterParameter } from "../api/types";

export interface RuleBounds {
  id: number;
  min_value: number | null;
  max_value: number | null;
  classification: Classification;
}

export interface Evaluation {
  status: MeasurementStatus;
  direction: Direction | null;
  rule_id: number | null;
  rule_min: number | null;
  rule_max: number | null;
  rule_classification: Classification | null;
}

/** Same grammar as the server: optional sign, digits with one decimal point or comma, optional exponent. */
const DECIMAL = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

/** ``"7,4"`` / ``"7.4"`` -> 7.4; blank -> null; anything else -> NaN (the server answers ``err.number``). */
export function parseDecimal(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (!text) return null;
  if (!DECIMAL.test(text)) return Number.NaN;
  const value = Number(text);
  return Number.isFinite(value) ? value : Number.NaN;
}

/** OK inside [min, max] (inclusive, a null bound is open), OUT_OF_RANGE + LOW/HIGH outside, NO_RULE without a rule. */
export function evaluate(value: number, rule: RuleBounds | null): Evaluation {
  if (rule === null) {
    return { status: "NO_RULE", direction: null, rule_id: null, rule_min: null, rule_max: null, rule_classification: null };
  }
  const snapshot = {
    rule_id: rule.id,
    rule_min: rule.min_value,
    rule_max: rule.max_value,
    rule_classification: rule.classification,
  };
  if (rule.min_value !== null && value < rule.min_value) return { status: "OUT_OF_RANGE", direction: "LOW", ...snapshot };
  if (rule.max_value !== null && value > rule.max_value) return { status: "OUT_OF_RANGE", direction: "HIGH", ...snapshot };
  return { status: "OK", direction: null, ...snapshot };
}

/** The organization's active rule for the parameter (what the server uses), or null -> NO_RULE. */
export function activeRuleFor(rules: NormRule[], parameterId: number): NormRule | null {
  return rules.find((rule) => rule.parameter_id === parameterId && rule.active) ?? null;
}

/** Server rejects values outside the parameter's physical range (``err.rule_range``) before evaluating. */
export function isPhysicallyPossible(value: number, parameter: WaterParameter): boolean {
  const below = parameter.physical_min !== null && value < parameter.physical_min;
  const above = parameter.physical_max !== null && value > parameter.physical_max;
  return !below && !above;
}

export type Preview =
  | { kind: "incomplete" }
  | { kind: "invalid" }
  | { kind: "impossible"; value: number }
  | { kind: "evaluated"; value: number; evaluation: Evaluation };

/** What the capture form shows while typing: the same decision path as ``create_measurement``. */
export function previewMeasurement(text: string, parameter: WaterParameter | null, rules: NormRule[]): Preview {
  const value = parseDecimal(text);
  if (parameter === null || value === null) return { kind: "incomplete" };
  if (Number.isNaN(value)) return { kind: "invalid" };
  if (!isPhysicallyPossible(value, parameter)) return { kind: "impossible", value };
  return { kind: "evaluated", value, evaluation: evaluate(value, activeRuleFor(rules, parameter.id)) };
}
