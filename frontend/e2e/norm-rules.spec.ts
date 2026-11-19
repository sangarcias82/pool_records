import { expect, test } from "@playwright/test";
import { resetPhRule, signIn } from "./helpers";

test.afterEach(async ({ browser }) => {
  await resetPhRule(browser);
});

test("admin edits a rule inline with server validation", async ({ page }) => {
  await signIn(page, "admin");
  await page.getByRole("navigation").getByRole("link", { name: "Norm rules" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(10);
  await expect(page.getByText("Read only")).toHaveCount(0);
  const ph = page.locator("tr[data-rule=PH]").first();
  await ph.getByRole("button", { name: "Edit the pH rule" }).click();
  await page.fill("input[name=min_value]", "8");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator(".flash.error")).toHaveText("The minimum must be less than or equal to the maximum.");
  await page.fill("input[name=min_value]", "7,0");
  await expect(page.locator(".flash.error")).toHaveCount(0);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator(".flash[role=status]")).toHaveText("pH rule saved.");
  await expect(ph).toContainText("7.0 – 7.8");
  await expect(ph).toContainText("Alicia Navarro");

  await ph.getByRole("button", { name: "Edit the pH rule" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator(".flash[role=status]")).toHaveText("Nothing changed.");
  await ph.getByRole("button", { name: "Edit the pH rule" }).click();
  await page.press("input[name=min_value]", "Escape");
  await expect(page.locator("tr.editing")).toHaveCount(0);
});

for (const role of ["supervisor", "tech"] as const) {
  test(`${role} gets a read-only list`, async ({ page }) => {
    await signIn(page, role);
    await page.getByRole("navigation").getByRole("link", { name: "Norm rules" }).click();
    await expect(page.locator("tbody tr")).toHaveCount(10);
    await expect(page.getByText("Read only: only organization admins can change rules.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Edit/ })).toHaveCount(0);
    await expect(page.locator("table input, table select")).toHaveCount(0);
    const denied = await page.request.patch("/api/norm-rules/1", { data: { active: false } });
    expect(denied.status()).toBe(403);
  });
}
