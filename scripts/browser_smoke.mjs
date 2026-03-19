import { assertBrowserHealth, captureStorefrontPages, defaultBaseUrl } from "./storefront_browser_flow.mjs";

async function main() {
  const artifactDir = process.env.SMOKE_ARTIFACT_DIR || "output/playwright";
  const baseUrl = defaultBaseUrl;
  const result = await captureStorefrontPages({ baseUrl, artifactDir });
  assertBrowserHealth(result);
  console.log(`Browser smoke passed for ${baseUrl}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
