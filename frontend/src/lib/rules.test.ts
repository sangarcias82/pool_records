import { describe, expect, it } from "vitest";
import type { NormRule } from "../api/types";
import { draftFromRule, ruleChanges } from "./rules";

const PH: NormRule = {
  id: 1, parameter_id: 1, parameter_code: "PH", parameter_name: "pH", unit: null, decimals: 1,
  min_value: 7.2, max_value: 7.8, classification: "NORMATIVE", source_notes: null, active: true,
  updated_at: null, updated_by_name: null,
};
const COMBINED: NormRule = { ...PH, id: 4, parameter_code: "COMBINED_CHLORINE", min_value: null, max_value: 0.2 };
const ORP: NormRule = { ...PH, id: 9, parameter_code: "ORP", min_value: 650, max_value: null, active: false };

describe("draftFromRule", () => {
  it("turns bounds into editable text, null into empty", () => {
    expect(draftFromRule(PH)).toEqual({ min_value: "7.2", max_value: "7.8", classification: "NORMATIVE", active: true });
    expect(draftFromRule(COMBINED).min_value).toBe("");
    expect(draftFromRule(ORP)).toEqual({ min_value: "650", max_value: "", classification: "NORMATIVE", active: false });
  });
});

describe("ruleChanges", () => {
  it("is empty when nothing changed, including the same number typed differently", () => {
    expect(ruleChanges(PH, draftFromRule(PH))).toEqual({});
    expect(ruleChanges(PH, { ...draftFromRule(PH), min_value: " 7,2 ", max_value: "7.80" })).toEqual({});
    expect(ruleChanges(COMBINED, { ...draftFromRule(COMBINED), min_value: "  " })).toEqual({});
  });
  it("sends only changed bounds, as typed", () => {
    expect(ruleChanges(PH, { ...draftFromRule(PH), min_value: "7,0" })).toEqual({ min_value: "7,0" });
    expect(ruleChanges(PH, { ...draftFromRule(PH), max_value: "" })).toEqual({ max_value: null });
    expect(ruleChanges(COMBINED, { ...draftFromRule(COMBINED), min_value: "0" })).toEqual({ min_value: "0" });
    expect(ruleChanges(ORP, { ...draftFromRule(ORP), max_value: "800" })).toEqual({ max_value: "800" });
    expect(ruleChanges(ORP, { ...draftFromRule(ORP), active: true, min_value: "" })).toEqual({ active: true, min_value: null });
  });
  it("lets the server judge text it cannot parse", () => {
    expect(ruleChanges(PH, { ...draftFromRule(PH), min_value: "abc" })).toEqual({ min_value: "abc" });
  });
  it("includes classification and active when they change", () => {
    const draft = { ...draftFromRule(PH), classification: "COMPLEMENTARY" as const, active: false };
    expect(ruleChanges(PH, draft)).toEqual({ classification: "COMPLEMENTARY", active: false });
  });
});
