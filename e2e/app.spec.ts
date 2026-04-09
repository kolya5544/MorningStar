import { expect, test } from "@playwright/test";

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await page.getByRole("button", { name: "Log In" }).first().click();
  await page.getByPlaceholder("you@example.com").last().fill(email);
  await page.getByPlaceholder("********").fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:8000/api/test/reset");
});

test("restores session after reload and logs out cleanly", async ({ page }) => {
  await login(page, "user@example.com", "UserPass123");

  await expect(page.getByText("Your portfolios")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Your portfolios")).toBeVisible();

  await page.getByRole("button", { name: /logout/i }).click();
  await expect(page.getByText("Plan your future ahead!")).toBeVisible();
});

test("supports role-based CRUD and read-only behavior", async ({ page }) => {
  await login(page, "user@example.com", "UserPass123");

  await page.getByRole("button", { name: /new portfolio/i }).click();
  await page.getByPlaceholder("My portfolio").fill("Lab 5 Portfolio");
  await page.getByRole("button", { name: "Create" }).last().click();
  await expect(page.getByText("Lab 5 Portfolio")).toBeVisible();

  await page.getByText("Lab 5 Portfolio").click();
  await expect(page).toHaveURL(/\/dashboard\//);

  await page.getByRole("button", { name: /add asset/i }).click();
  await page.getByPlaceholder("BTC").fill("SOL");
  await page.getByPlaceholder("Bitcoin (optional)").fill("Solana");
  await page.getByRole("button", { name: /^Add$/ }).last().click();
  await expect(page.getByText("Solana")).toBeVisible();

  await login(page, "manager@example.com", "ManagerPass123");
  await expect(page.getByText("Available portfolios")).toBeVisible();
  await page.getByRole("button", { name: /User Core Portfolio/ }).first().click();
  await expect(page).toHaveURL(/\/dashboard\//);
  await expect(page.getByRole("button", { name: /add asset/i })).toHaveCount(0);

  await login(page, "admin@example.com", "AdminPass123");
  await page.goto("/control-panel");
  await expect(page.getByRole("button", { name: /delete/i }).first()).toBeVisible();
  const beforeDelete = await page.getByRole("button", { name: /delete/i }).count();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: /delete/i }).first().click();
  await expect(page.getByRole("button", { name: /delete/i })).toHaveCount(beforeDelete - 1);
});

test("filters, sorts and paginates dashboard data", async ({ page }) => {
  await login(page, "user@example.com", "UserPass123");

  await page.getByPlaceholder("Portfolio name or owner").fill("Paged");
  await expect(page).toHaveURL(/search=Paged/);

  await page.locator("select").nth(2).selectOption("name");
  await page.locator("select").nth(3).selectOption("asc");
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText(/page 2 of/i)).toBeVisible();
});

test("uploads, downloads and deletes portfolio files", async ({ page }) => {
  await login(page, "user@example.com", "UserPass123");
  await page.getByRole("button", { name: /User Core Portfolio/ }).first().click();
  await expect(page).toHaveURL(/\/dashboard\//);
  await page.getByRole("button", { name: /Bitcoin/ }).click();

  await page.locator('input[type="file"]').setInputFiles({
    name: "e2e-report.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("portfolio evidence", "utf-8"),
  });
  await expect(page.getByText("e2e-report.txt")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download" }).click();
  const download = await downloadPromise;
  expect(await download.suggestedFilename()).toBe("e2e-report.txt");

  await page.getByRole("button", { name: "Delete" }).last().click();
  await expect(page.getByText("e2e-report.txt")).not.toBeVisible();
});

test("handles external API success and failure paths", async ({ page }) => {
  await login(page, "user@example.com", "UserPass123");
  await page.getByRole("button", { name: /User Core Portfolio/ }).first().click();
  await expect(page).toHaveURL(/\/dashboard\//);
  await page.getByRole("button", { name: /Bitcoin/ }).click();

  await page.getByTitle("Import from Bybit").click();
  const importDialog = page.getByRole("dialog", { name: "Import from Bybit" });
  await expect(importDialog).toBeVisible();
  await importDialog.locator("input").nth(0).fill("good-key");
  await importDialog.locator('input[type="password"]').fill("good-secret");
  await importDialog.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("SOL")).toBeVisible();

  await page.getByTitle("Import from Bybit").click();
  await expect(importDialog).toBeVisible();
  await importDialog.locator("input").nth(0).fill("fail-key");
  await importDialog.locator('input[type="password"]').fill("good-secret");
  await importDialog.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("Bybit unavailable")).toBeVisible();
});
