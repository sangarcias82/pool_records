import { expect, test, type Page } from "@playwright/test";
import { api, patchRule, resetPhRule, signIn } from "./helpers";

type Row = { id: number; status: string; direction: string | null; notes: string | null };

async function openForm(page: Page, pool = "Club Deportivo Las Palmas — Semiolímpica", parameter = "pH") {
  await page.goto("/measurements/new");
  await page.selectOption("select[name=pool_id]", { label: pool });
  await page.selectOption("select[name=parameter_id]", { label: parameter });
}

test.afterEach(async ({ browser }) => {
  await resetPhRule(browser); // rules back to the planning default
});

test("list: three badge colors, filters kept in the URL, counts equal the API", async ({ page }) => {
  await signIn(page, "tech");
  await page.getByRole("navigation").getByRole("link", { name: "Measurements" }).click();
  for (const kind of ["ok", "out", "none"]) await expect(page.locator(`tbody .badge.${kind}`).first()).toBeVisible();
  const out = await api<Row[]>(page, "/api/measurements?status=OUT_OF_RANGE&limit=200");
  await page.getByLabel("Status").selectOption("OUT_OF_RANGE");
  await expect(page).toHaveURL(/status=OUT_OF_RANGE/);
  await expect(page.locator("tbody tr")).toHaveCount(out.length);
  await page.getByLabel("Pool").selectOption({ label: "Hotel Brisa Marina — Jacuzzi" });
  const jacuzzi = await api<Row[]>(page, "/api/measurements?status=OUT_OF_RANGE&pool_id=3&limit=200");
  await expect(page.locator("tbody tr")).toHaveCount(jacuzzi.length);
  await page.reload(); // filters survive a reload (they live in the URL)
  await expect(page.locator("tbody tr")).toHaveCount(jacuzzi.length);
});

test("preview follows the server rules while typing", async ({ page }) => {
  await signIn(page, "tech");
  await openForm(page);
  await expect(page.locator(".preview-rule")).toContainText("7.2 – 7.8");
  const badge = page.locator(".preview .badge");
  for (const [value, status, text] of [
    ["7,4", "OK", "Within range"],
    ["6,9", "OUT_OF_RANGE", "Out of range (low)"],
    ["8.1", "OUT_OF_RANGE", "Out of range (high)"],
    ["7.8", "OK", "Within range"], // bounds are inclusive
  ]) {
    await page.fill("input[name=value]", value);
    await expect(badge).toHaveAttribute("data-status", status);
    await expect(badge).toContainText(text);
  }
  await page.fill("input[name=value]", "15");
  await expect(page.locator(".preview")).toHaveAttribute("data-preview-kind", "impossible");
  await page.fill("input[name=value]", "7,4,1");
  await expect(page.locator(".preview")).toHaveAttribute("data-preview-kind", "invalid");
  await page.selectOption("select[name=parameter_id]", { label: "Total chlorine (mg/L)" });
  await page.fill("input[name=value]", "2");
  await expect(badge).toHaveAttribute("data-status", "NO_RULE");
});

test("saving stores what the preview showed, once, even if Save is clicked twice", async ({ page }) => {
  await signIn(page, "tech");
  const before = (await api<Row[]>(page, "/api/measurements?limit=200&pool_id=1")).length;
  await openForm(page);
  await page.fill("input[name=value]", "8,1");
  const note = `e2e: double click ${Date.now()}`; // unique: the database may hold earlier runs
  await page.fill("textarea[name=notes]", note);
  await page.locator("button[type=submit]").dblclick();
  await expect(page.locator(".flash[role=status]")).toContainText(/Saved MES-\d{8}-\d{4,}: Out of range \(high\)\./);
  await expect(page.locator(".flash[role=status]")).not.toContainText("preview differed");
  const rows = await api<Row[]>(page, "/api/measurements?limit=200&pool_id=1");
  expect(rows.length).toBe(before + 1);
  expect(rows.filter((r) => r.notes === note)).toHaveLength(1);
  await expect(page.locator("tbody tr").first()).toContainText(note);
});

test("server errors are shown in the form and cleared by editing", async ({ page }) => {
  await signIn(page, "tech");
  await openForm(page);
  await page.fill("input[name=value]", "15");
  await page.click("button[type=submit]");
  await expect(page.locator(".flash.error")).toHaveText("15 is outside the possible range of pH.");
  await page.fill("input[name=value]", "7,5");
  await expect(page.locator(".flash.error")).toHaveCount(0);
});

test("a rule changed after opening the form: the saved result wins and the user is told", async ({ page, browser }) => {
  await signIn(page, "tech");
  await openForm(page);
  await page.fill("input[name=value]", "7,9");
  await expect(page.locator(".preview .badge")).toHaveAttribute("data-status", "OUT_OF_RANGE"); // 7.2 – 7.8
  const admin = await browser.newPage();
  await signIn(admin, "admin");
  await patchRule(admin, "PH", { max_value: 8.5 }); // meanwhile an admin widens the rule
  await admin.close();
  await page.click("button[type=submit]");
  const flash = page.locator(".flash[role=status]");
  await expect(flash).toContainText("Within range");
  await expect(flash).toContainText("The live preview differed");
});
