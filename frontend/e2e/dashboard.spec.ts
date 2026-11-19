import { expect, test } from "@playwright/test";
import { api, signIn } from "./helpers";

type Dashboard = {
  measurements: { today: number; out_of_range_last_7_days: number };
  windows: { timezone: string; today_from: string; last_7_days_from: string };
};

test("widgets show the API numbers and open exactly the counted rows", async ({ page }) => {
  await signIn(page, "supervisor");
  const dash = await api<Dashboard>(page, "/api/dashboard");
  const today = page.locator("[data-widget=today]");
  const out = page.locator("[data-widget=out-of-range]");
  await expect(today.locator("strong")).toHaveText(String(dash.measurements.today));
  await expect(out.locator("strong")).toHaveText(String(dash.measurements.out_of_range_last_7_days));
  await expect(page.getByText(`Days are counted in ${dash.windows.timezone}`)).toBeVisible();
  expect(dash.measurements.out_of_range_last_7_days).toBeGreaterThan(0); // demo data
  await expect(out).toHaveClass(/alert/);

  await out.click();
  await expect(page).toHaveURL(/status=OUT_OF_RANGE/);
  await expect(page.locator("tbody tr")).toHaveCount(dash.measurements.out_of_range_last_7_days);
  await expect(page.locator("tbody tr:not([data-status=OUT_OF_RANGE])")).toHaveCount(0);
  await expect(page.locator(".chip")).toContainText("Measured since");
  await page.locator(".chip button").click();
  await expect(page).not.toHaveURL(/measured_from/);

  await page.getByRole("navigation").getByRole("link", { name: "Dashboard" }).click();
  await today.click();
  await expect(page.locator("tbody tr")).toHaveCount(Math.min(dash.measurements.today, 200));
});
