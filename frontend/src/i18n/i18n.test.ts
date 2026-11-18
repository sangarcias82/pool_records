import { describe, expect, it } from "vitest";
import { en } from "./en";
import { es } from "./es";
import { translate } from "./translate";

describe("i18n", () => {
  it("keeps EN and ES keys in sync", () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
  });

  it("interpolates params and falls back to the key", () => {
    expect(translate("en", "home.welcome", { name: "Ana" })).toBe("Welcome, Ana.");
    expect(translate("es", "missing.key")).toBe("missing.key");
  });
});
