import { expect, test } from "@playwright/test";
import { signIn, type Role } from "./helpers";

test("the built SPA is served at / (not the 'not built' message)", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page.locator("input[type=password]")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("not built");
});

for (const role of ["admin", "supervisor", "tech"] as Role[]) {
  test(`${role} can open every page from the nav`, async ({ page }) => {
    await signIn(page, role);
    for (const [link, ready] of [
      ["Clients & pools", "table"],
      ["Measurements", "table.measurements tbody tr"],
      ["Norm rules", "table.rules tbody tr"],
      ["Dashboard", "[data-widget=today]"],
    ]) {
      await page.getByRole("navigation").getByRole("link", { name: link }).click();
      await expect(page.locator(ready).first()).toBeVisible();
    }
  });
}

test("deep links load through the history fallback", async ({ page }) => {
  await signIn(page, "tech");
  await page.goto("/measurements/new?pool_id=1");
  await expect(page.locator("select[name=pool_id]")).toHaveValue("1");
  await page.goto("/does-not-exist");
  await expect(page.getByText("Page not found")).toBeVisible();
});
