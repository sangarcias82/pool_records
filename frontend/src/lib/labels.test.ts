import { describe, expect, it } from "vitest";
import { translate } from "../i18n/translate";
import { paramLabel } from "./labels";

describe("paramLabel", () => {
  it("translates known codes and falls back to the catalog name", () => {
    expect(paramLabel((k) => translate("es", k), "FREE_CHLORINE", "Free chlorine")).toBe("Cloro libre");
    expect(paramLabel((k) => translate("en", k), "FREE_CHLORINE", "x")).toBe("Free chlorine");
    expect(paramLabel((k) => translate("es", k), "ORP", "Oxidation-reduction potential")).toBe("Oxidation-reduction potential");
  });
});
