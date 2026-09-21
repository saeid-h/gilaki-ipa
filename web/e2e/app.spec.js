import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const clip = join(dirname(fileURLToPath(import.meta.url)), "../../api/tests/fixtures/clip.wav");

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("gilaki.apiBase", "http://127.0.0.1:18741");
    localStorage.removeItem("gilaki.lastIpa");
  });
});

test("has no API key field", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/api key/i)).toHaveCount(0);
  await expect(page.locator("#apiBase")).toHaveCount(1);
});

test("pasted base URL reaches mock health via presets", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#status")).toHaveAttribute("data-kind", "ready", { timeout: 15000 });
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByTestId("api-base")).toHaveValue("http://127.0.0.1:18741");
});

test("file upload shows mapped headline, optional IPA, remap, lossy, RTL", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#status")).toHaveAttribute("data-kind", "ready", { timeout: 15000 });
  await page.getByTestId("file").setInputFiles(clip);
  const mapped = page.getByTestId("mapped");
  await expect(mapped).toHaveText("مٚشٚنآ", { timeout: 20000 });
  await expect(page.getByTestId("ipa")).toBeHidden();

  const mappedSize = await mapped.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  await page.getByTestId("show-ipa").click();
  const ipa = page.getByTestId("ipa");
  await expect(ipa).toBeVisible();
  await expect(ipa).toContainText("ə");
  const ipaSize = await ipa.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(mappedSize).toBeGreaterThan(ipaSize);

  await expect(page.locator("#transcript")).toHaveAttribute("dir", "rtl");

  await page.getByTestId("chip-academic-latin").click();
  await expect(mapped).toHaveText("məšənå");
  await expect(page.locator("#transcript")).toHaveAttribute("dir", "ltr");

  await page.getByTestId("chip-lossy-persian").click();
  await expect(page.locator("#lossy")).toBeVisible();
  await expect(mapped).not.toContainText("ə");
  await expect(mapped).not.toContainText("ٚ");
});

test("settings URL field is the public default before init override", async ({ page }) => {
  const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../app.js"), "utf8");
  expect(html).toContain("https://1404kingstreet.com/gilaki-api");
});
