import { expect, test } from "@playwright/test";
const header =
  "customer_id,email,country,signup_date,order_amount,currency,payment_method,order_status,product_category,quantity,discount_percent,last_login_date";
const good =
  "C1,alice@example.com,DE,2026-04-01,125.50,EUR,card,completed,electronics,2,10,2026-04-10";
test("upload, inspect analytics, reopen history, preview and handle failure", async ({
  page,
}, info) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/");
  await page.getByLabel("CSV file").setInputFiles({
    name: "portfolio-demo.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      [
        header,
        good,
        good.replace("C1", "C2").replace("125.50", "1500"),
        good.replace("alice@example.com", "invalid"),
      ].join("\n"),
    ),
  });
  await page.getByRole("button", { name: "Preview validation" }).click();
  await page.getByRole("button", { name: "Upload and Analyze CSV" }).click();
  await expect(
    page.getByRole("heading", { name: "portfolio-demo.csv" }),
  ).toBeVisible();
  // The accepted job survives a refresh while it may still be active.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "portfolio-demo.csv" }),
  ).toBeVisible();
  await expect(page.getByText("33.3% invalid")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "Validation", exact: true }).click();
  await expect(
    page.getByText("email must be valid", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Anomalies", exact: true }).click();
  await expect(page.getByText("High-value order detected.")).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: info.outputPath("dashboard.png"),
    fullPage: true,
  });
  await page.reload();
  await page.getByRole("button", { name: /#\d+ · portfolio-demo.csv/ }).click();
  await expect(
    page.getByRole("heading", { name: "portfolio-demo.csv" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Generate insights" }).click();
  await expect(page.getByRole("alert")).toContainText("LLM not configured");
  await page.getByRole("button", { name: "Preview files" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("customer_id", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByLabel("CSV file")
    .setInputFiles({
      name: "bad-header.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("email\nbad@example.com"),
    });
  await expect(
    page.getByText("Map all 12 fields to different columns before previewing."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Preview validation" }),
  ).toBeDisabled();
  await page
    .getByLabel("CSV file")
    .setInputFiles({
      name: "header-only.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(header + "\n"),
    });
  await page.getByRole("button", { name: "Preview validation" }).click();
  await page.getByRole("button", { name: "Upload and Analyze CSV" }).click();
  await expect(
    page.getByRole("heading", { name: "header-only.csv" }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "CSV contains no data records",
    { timeout: 20000 },
  );
  expect(failures).toEqual([]);
});
test("mobile layout has no horizontal page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /File Intake/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("map partner columns, save a template, correct rejected data and preserve the original", async ({
  page,
}) => {
  const partnerHeaders = header
    .split(",")
    .map((field) =>
      field.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    )
    .join(",");
  const csv = [
    partnerHeaders,
    good,
    good.replace("C1,", "C2,").replace("alice@example.com", "bad-email"),
  ].join("\n");
  await page.goto("/");
  await page
    .getByLabel("CSV file")
    .setInputFiles({
      name: "partner-transactions.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
  await expect(page.getByLabel("Map email")).toHaveValue("Email");
  await page.getByText("Save this configuration", { exact: true }).click();
  await page.getByLabel("Template name").fill("Partner import");
  await page
    .getByRole("button", { name: "Save new template", exact: true })
    .click();
  await expect(
    page.getByText(
      "Saved Partner import, version 1. Preview before processing.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Preview validation" }).click();
  await expect(page.getByText("Preview · first 2 records")).toBeVisible();
  await page.getByRole("button", { name: "Upload and Analyze CSV" }).click();
  await expect(page.getByText("50.0% invalid")).toBeVisible({ timeout: 20000 });
  const parent = new URL(page.url()).searchParams.get("job")!;
  await page.getByRole("button", { name: "Validation", exact: true }).click();
  await page.getByRole("button", { name: "Email", exact: true }).click();
  const explorer = page.getByRole("region", { name: "Dataset explorer" });
  await expect(explorer.getByLabel("Error category")).toHaveValue("Email");
  await expect(explorer.getByText(/1 matching records/)).toBeVisible();
  await explorer
    .getByRole("button", { name: "Correct record 3", exact: true })
    .click();
  await explorer
    .getByLabel("Record 3 email", { exact: true })
    .fill("bob@example.com");
  await explorer
    .getByRole("button", { name: "Validate corrections", exact: true })
    .click();
  await expect(
    explorer.getByText("Field validation passed.", { exact: true }),
  ).toBeVisible();
  await explorer
    .getByRole("button", { name: "Reprocess corrected dataset" })
    .click();
  await expect(
    page.getByRole("region", { name: "Correction comparison" }),
  ).toBeVisible({ timeout: 20000 });
  await expect(
    page.getByText("Accepted: 1 → 2 · Rejected: 1 → 0"),
  ).toBeVisible();
  const child = new URL(page.url()).searchParams.get("job")!;
  expect(child).not.toBe(parent);
  await page.reload();
  await expect(
    page.getByText("Accepted: 1 → 2 · Rejected: 1 → 0"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: `Open original job #${parent}` })
    .click();
  await expect(page.getByText("50.0% invalid")).toBeVisible();
  await page.getByRole("button", { name: `Open correction #${child}` }).click();
  await expect(page.getByText("0.0% invalid")).toBeVisible();
  // A fresh import reuses the saved template after a reload.
  await page
    .getByLabel("CSV file")
    .setInputFiles({
      name: "partner-next.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
  await page
    .getByLabel("Saved import template")
    .selectOption({ label: "Partner import · v1" });
  await expect(page.getByLabel("Map email")).toHaveValue("Email");
  await page.getByRole("button", { name: "Preview validation" }).click();
  await expect(page.getByText("Preview · first 2 records")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("job navigation requires discarding drafts and submitted corrections leave no stale guard", async ({
  page, request,
}) => {
  await page.goto("/");
  await page.getByLabel("CSV file").setInputFiles({
    name: "draft-parent.csv", mimeType: "text/csv",
    buffer: Buffer.from([header, good, good.replace("C1,", "C2,").replace("alice@example.com", "bad-email")].join("\n")),
  });
  await page.getByRole("button", { name: "Preview validation", exact: true }).click();
  await page.getByRole("button", { name: "Upload and Analyze CSV", exact: true }).click();
  await expect(page.getByText("50.0% invalid")).toBeVisible({ timeout: 20000 });
  const parent = new URL(page.url()).searchParams.get("job")!;
  const accepted = await request.post("http://127.0.0.1:8011/api/v1/uploads", {
    multipart: { file: { name: "draft-target.csv", mimeType: "text/csv", buffer: Buffer.from([header, good].join("\n")) } },
  });
  expect(accepted.status()).toBe(202);
  const target = (await accepted.json()).job_id;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  const explorer = page.getByRole("region", { name: "Dataset explorer" });
  const edit = async () => {
    await explorer.getByRole("button", { name: "Correct record 3", exact: true }).click();
    await explorer.getByLabel("Record 3 email", { exact: true }).fill("fixed@example.com");
    await explorer.getByRole("button", { name: "Validate corrections", exact: true }).click();
    await expect(explorer.getByRole("button", { name: "Reprocess corrected dataset", exact: true })).toBeEnabled();
  };
  await edit();
  const parentUrl = page.url();
  const openTarget = page.getByRole("button", { name: `#${target} · draft-target.csv`, exact: true });
  await openTarget.click();
  const dialog = page.getByRole("dialog", { name: "Discard unsaved corrections?" });
  await expect(dialog).toBeVisible();
  await expect(page).toHaveURL(parentUrl);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(parentUrl);
  await expect(explorer.getByLabel("Record 3 email", { exact: true })).toHaveValue("fixed@example.com");
  await expect(explorer.getByText("Field validation passed.", { exact: true })).toBeVisible();
  await expect(explorer.getByRole("button", { name: "Reprocess corrected dataset", exact: true })).toBeEnabled();
  await openTarget.click();
  await dialog.getByRole("button", { name: "Discard", exact: true }).click();
  await expect(page.getByRole("heading", { name: "draft-target.csv", exact: true })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`job=${target}(?:&|$)`));
  await page.getByRole("button", { name: `#${parent} · draft-parent.csv`, exact: true }).click();
  await expect(explorer.getByText("1 record with unsaved corrections", { exact: true })).toHaveCount(0);
  await explorer.getByRole("button", { name: "Correct record 3", exact: true }).click();
  await expect(explorer.getByLabel("Record 3 email", { exact: true })).toHaveValue("bad-email");
  await edit();
  await explorer.getByRole("button", { name: "Reprocess corrected dataset", exact: true }).click();
  await expect(page.getByRole("region", { name: "Correction comparison" })).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("Accepted: 1 → 2 · Rejected: 1 → 0")).toBeVisible();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: `Open original job #${parent}`, exact: true }).click();
  await expect(page).toHaveURL(parentUrl);
  await expect(dialog).not.toBeVisible();
});
