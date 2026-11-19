import { expect, type Browser, type Page } from "@playwright/test";

export const USERS = {
  admin: "admin@aquacontrol.example",
  supervisor: "supervisor@aquacontrol.example",
  tech: "tech@aquacontrol.example",
} as const;
export type Role = keyof typeof USERS;

/** Sign in through the login page in the given UI language; lands on the dashboard. Works when already signed in. */
export async function signIn(page: Page, role: Role, lang: "en" | "es" = "en"): Promise<void> {
  await page.request.post("/api/auth/logout"); // the login page redirects signed-in users away
  await page.goto("/login");
  await page.locator(".lang-switch").getByRole("button", { name: lang.toUpperCase(), exact: true }).click();
  await page.fill("input[autocomplete=username]", USERS[role]);
  await page.fill("input[type=password]", "AquaDemo1!");
  await page.click("button[type=submit]");
  await expect(page.locator("[data-widget=today]")).toBeVisible();
}

/** JSON from the API with the page's session cookie. */
export async function api<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} -> ${response.status()}`).toBeTruthy();
  return (await response.json()) as T;
}

export async function patchRule(page: Page, code: string, body: Record<string, unknown>): Promise<void> {
  const rules = await api<{ id: number; parameter_code: string }[]>(page, "/api/norm-rules");
  const rule = rules.find((r) => r.parameter_code === code)!;
  const response = await page.request.patch(`/api/norm-rules/${rule.id}`, { data: body });
  expect(response.ok(), `PATCH ${code} -> ${response.status()}`).toBeTruthy();
}

export const PH_DEFAULT = { min_value: 7.2, max_value: 7.8, classification: "NORMATIVE", active: true };

/** Put the PH rule back to its planning default from a separate page (cleanup must not depend on the test's page). */
export async function resetPhRule(browser: Browser): Promise<void> {
  const page = await browser.newPage();
  await signIn(page, "admin");
  await patchRule(page, "PH", PH_DEFAULT);
  await page.close();
}
