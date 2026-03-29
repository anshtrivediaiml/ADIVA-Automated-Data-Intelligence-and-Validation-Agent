import { expect, test } from "@playwright/test";

const email = process.env.QA_EMAIL;
const password = process.env.QA_PASSWORD;

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email!);
  await page.getByLabel(/password/i).fill(password!);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("main authenticated navigation works", async ({ page }) => {
  test.skip(!email || !password, "QA_EMAIL and QA_PASSWORD must be set.");

  await login(page);

  await page.getByRole("link", { name: "Jobs", exact: true }).click();
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("heading", { name: /jobs/i })).toBeVisible();

  await page.getByRole("link", { name: "Reviews", exact: true }).click();
  await expect(page).toHaveURL(/\/reviews$/);
  await expect(page.getByRole("heading", { name: /review queue/i })).toBeVisible();

  await page.getByRole("link", { name: "Upload", exact: true }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole("heading", { name: /upload document/i })).toBeVisible();
});
