import fs from "node:fs/promises";
import path from "node:path";
import { assertBrowserHealth, captureStorefrontPages, defaultBaseUrl, ensureDir } from "./storefront_browser_flow.mjs";

const baseUrl = defaultBaseUrl;
const baselineDir = process.env.VISUAL_BASELINE_DIR || "tests/visual-baselines/storefront";

async function main() {
  await fs.rm(baselineDir, { recursive: true, force: true });
  await ensureDir(baselineDir);

  const result = await captureStorefrontPages({
    baseUrl,
    artifactDir: baselineDir,
  });
  assertBrowserHealth(result);

  const screenshots = Object.values(result.screenshots)
    .map((filePath) => path.relative(process.cwd(), filePath))
    .sort();

  console.log(`Updated visual baselines for ${baseUrl}`);
  console.log(screenshots.join("\n"));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
