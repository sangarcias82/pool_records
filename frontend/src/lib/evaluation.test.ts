import { describe, expect, it } from "vitest";
import type { NormRule, WaterParameter } from "../api/types";
import shared from "./evaluation.cases.json";
import { activeRuleFor, evaluate, isPhysicallyPossible, parseDecimal, previewMeasurement, type RuleBounds } from "./evaluation";

// Same cases as tests/test_evaluation.py on the server.
type EvalCase = { name: string; value: number; rule: RuleBounds | null; expected: { status: string; direction: string | null } };
type ParseCase = { input: string; expected?: number | null; invalid?: boolean };

const PH: WaterParameter = {
  id: 1, code: "PH", name: "pH", unit: null, decimals: 1, physical_min: 0, physical_max: 14, sort_order: 10, active: true,
};
const TDS: WaterParameter = { ...PH, id: 10, code: "TDS", name: "Total dissolved solids", unit: "mg/L", physical_max: null };

function rule(overrides: Partial<NormRule> = {}): NormRule {
  return {
    id: 1, parameter_id: 1, parameter_code: "PH", parameter_name: "pH", unit: null, decimals: 1,
    min_value: 7.2, max_value: 7.8, classification: "NORMATIVE", source_notes: null, active: true,
    updated_at: null, updated_by_name: null, ...overrides,
  };
}

describe("shared contract with the server", () => {
  it.each((shared.evaluate as EvalCase[]).map((c) => [c.name, c] as const))("evaluate: %s", (_name, c) => {
    const result = evaluate(c.value, c.rule);
    expect({ status: result.status, direction: result.direction }).toEqual(c.expected);
    expect([result.rule_id, result.rule_min, result.rule_max, result.rule_classification]).toEqual(
      c.rule ? [c.rule.id, c.rule.min_value, c.rule.max_value, c.rule.classification] : [null, null, null, null],
    );
  });

  it.each((shared.parse_decimal as ParseCase[]).map((c) => [JSON.stringify(c.input), c] as const))("parseDecimal(%s)", (_label, c) => {
    const parsed = parseDecimal(c.input);
    if (c.invalid) expect(parsed).toBeNaN();
    else expect(parsed).toBe(c.expected);
  });
});

describe("activeRuleFor", () => {
  it("returns the active rule of the parameter only", () => {
    const rules = [rule({ id: 3, parameter_id: 3, active: false }), rule({ id: 1 }), rule({ id: 2, parameter_id: 2 })];
    expect(activeRuleFor(rules, 1)?.id).toBe(1);
    expect(activeRuleFor(rules, 3)).toBeNull(); // inactive -> NO_RULE, like the server
    expect(activeRuleFor(rules, 99)).toBeNull();
  });
});

describe("isPhysicallyPossible", () => {
  it("uses the parameter's physical bounds, open when null", () => {
    expect([isPhysicallyPossible(0, PH), isPhysicallyPossible(14, PH)]).toEqual([true, true]);
    expect([isPhysicallyPossible(-0.1, PH), isPhysicallyPossible(15, PH)]).toEqual([false, false]);
    expect(isPhysicallyPossible(1e6, TDS)).toBe(true);
    expect(isPhysicallyPossible(5, { ...PH, physical_min: null, physical_max: null })).toBe(true);
  });
});

describe("previewMeasurement", () => {
  const rules = [rule()];
  it("waits for a parameter and a value", () => {
    expect(previewMeasurement("7,4", null, rules)).toEqual({ kind: "incomplete" });
    expect(previewMeasurement("  ", PH, rules)).toEqual({ kind: "incomplete" });
  });
  it("flags text the server would reject", () => {
    expect(previewMeasurement("7,4,1", PH, rules)).toEqual({ kind: "invalid" });
    expect(previewMeasurement("15", PH, rules)).toEqual({ kind: "impossible", value: 15 });
  });
  it("evaluates against the active rule", () => {
    const low = previewMeasurement("6,9", PH, rules);
    expect(low.kind === "evaluated" && [low.value, low.evaluation.status, low.evaluation.direction]).toEqual([6.9, "OUT_OF_RANGE", "LOW"]);
    const ok = previewMeasurement("7.8", PH, rules);
    expect(ok.kind === "evaluated" && ok.evaluation.status).toBe("OK");
    const noRule = previewMeasurement("7,4", PH, [rule({ active: false })]);
    expect(noRule.kind === "evaluated" && noRule.evaluation.status).toBe("NO_RULE");
  });
});
