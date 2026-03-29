import { expect, test } from "@playwright/test";
import path from "node:path";

const email = process.env.QA_EMAIL;
const password = process.env.QA_PASSWORD;
const sampleFile = process.env.QA_SAMPLE_FILE;

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email!);
  await page.getByLabel(/password/i).fill(password!);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("upload flow reaches job page", async ({ page }) => {
  test.skip(!email || !password, "QA_EMAIL and QA_PASSWORD must be set.");
  test.skip(!sampleFile, "QA_SAMPLE_FILE must be set for upload flow.");

  await login(page);
  await page.goto("/upload");

  await page.setInputFiles('input[type="file"]', path.resolve(sampleFile!));
  await page.getByRole("button", { name: /submit for processing/i }).click();

  await expect(page).toHaveURL(/\/jobs\//);
  await expect(page.getByRole("heading", { name: /job/i })).toBeVisible();
});
