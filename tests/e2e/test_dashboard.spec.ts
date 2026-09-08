import { test, expect } from "@playwright/test";

/**
 * E2E tests for the dashboard.
 * Requires the app to be running (docker compose up + make demo).
 * Run: npx playwright test tests/e2e/
 */

test.describe("Dashboard — Overview page", () => {
  test("loads and shows KPI cards", async ({ page }) => {
    await page.goto("/overview");
    await expect(page.getByText("Revenue at Risk")).toBeVisible();
    await expect(page.getByText("Revenue Recovered")).toBeVisible();
    await expect(page.getByText("Recovery Rate")).toBeVisible();
    await expect(page.getByText("Policy Violations")).toBeVisible();
  });

  test("shows synthetic data badge", async ({ page }) => {
    await page.goto("/overview");
    await expect(page.getByText(/synthetic data/i)).toBeVisible();
  });

  test("shows mode indicator", async ({ page }) => {
    await page.goto("/overview");
    // Must show either AI MODE or FALLBACK MODE — never hide it
    const modeIndicator = page.locator("text=/AI MODE|FALLBACK MODE/i");
    await expect(modeIndicator).toBeVisible();
  });
});

test.describe("Recovery Cases", () => {
  test("lists cases", async ({ page }) => {
    await page.goto("/cases");
    // Wait for table to load
    await expect(page.locator("table")).toBeVisible({ timeout: 10000 });
  });

  test("can filter by scenario", async ({ page }) => {
    await page.goto("/cases");
    await page.selectOption("select", "FAILED_PAYMENT");
    await page.waitForTimeout(1000);
    // Should still show table after filtering
    await expect(page.locator("table")).toBeVisible();
  });
});

test.describe("Simulation page", () => {
  test("shows run controls", async ({ page }) => {
    await page.goto("/simulation");
    await expect(page.getByText("Run Simulation")).toBeVisible();
    await expect(page.getByText("Simulation Runs")).toBeVisible();
  });
});

test.describe("Audit Trail", () => {
  test("loads audit table", async ({ page }) => {
    await page.goto("/audit");
    await expect(page.getByText("Audit Trail")).toBeVisible();
    await expect(page.getByText("append-only")).toBeVisible();
  });
});

test.describe("Policies page", () => {
  test("loads policy view", async ({ page }) => {
    await page.goto("/policies");
    await expect(page.getByText("Merchant Policies")).toBeVisible();
  });
});
