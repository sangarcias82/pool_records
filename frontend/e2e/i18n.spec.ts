import { expect, test } from "@playwright/test";
import { en } from "../src/i18n/en";
import { es } from "../src/i18n/es";
import { signIn } from "./helpers";

/** English UI texts that must never appear on a Spanish page (longest literal part, whole words). */
const ENGLISH = Object.entries(en)
  .filter(([key, text]) => es[key] !== text)
  .map(([, text]) => text.split(/\{\w+\}/).map((part) => part.trim()).sort((a, b) => b.length - a.length)[0])
  .filter((part) => part.length >= 6);
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const PAGES = ["/", "/clients", "/measurements", "/measurements?status=OUT_OF_RANGE", "/measurements/new", "/norm-rules"];

for (const role of ["admin", "tech"] as const) {
  test(`Spanish pages show no English UI text (${role})`, async ({ page }) => {
    await signIn(page, role, "es");
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    for (const path of PAGES) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      // innerText is the text as displayed (CSS uppercases table headers): compare case-insensitively
      const text = await page.locator("body").innerText();
      const leaks = ENGLISH.filter((part) => new RegExp(`(^|\\W)${escape(part)}(\\W|$)`, "i").test(text));
      expect(leaks, `${path}: ${leaks.join(" | ")}`).toEqual([]);
    }
  });
}

test("Spanish API errors and preview in the form", async ({ page }) => {
  await signIn(page, "tech", "es");
  await page.goto("/measurements/new");
  await page.selectOption("select[name=pool_id]", { index: 1 });
  await page.selectOption("select[name=parameter_id]", { label: "Cloro libre (mg/L)" });
  await page.fill("input[name=value]", "25");
  await page.click("button[type=submit]");
  await expect(page.locator(".flash.error")).toHaveText("25 está fuera del rango posible de cloro libre.");
  await page.fill("input[name=value]", "0,5");
  await expect(page.locator(".preview .badge")).toContainText("Fuera de rango (bajo)");
});

test("switching language updates <html lang> and the labels", async ({ page }) => {
  await signIn(page, "tech", "en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.locator(".lang-switch").getByRole("button", { name: "ES", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.getByRole("navigation", { name: "Navegación principal" })).toContainText("Mediciones");
  await page.locator(".lang-switch").getByRole("button", { name: "EN", exact: true }).click();
});
