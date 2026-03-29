import { expect, test } from "@playwright/test";

const email = process.env.QA_EMAIL;
const password = process.env.QA_PASSWORD;

test("login and dashboard access", async ({ page }) => {
  test.skip(!email || !password, "QA_EMAIL and QA_PASSWORD must be set.");

  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email!);
  await page.getByLabel(/password/i).fill(password!);
  await page.getByRole("button", { name: /sign in/i }).click();

  await expect(page).toHaveURL(/dashboard|\/$/);
  await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
});
