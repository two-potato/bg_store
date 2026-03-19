import fs from "node:fs/promises";
import path from "node:path";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";
import { assertBrowserHealth, captureStorefrontPages, defaultBaseUrl, ensureDir, storefrontPages } from "./storefront_browser_flow.mjs";

const baseUrl = defaultBaseUrl;
const baselineDir = process.env.VISUAL_BASELINE_DIR || "tests/visual-baselines/storefront";
const currentDir = process.env.VISUAL_CURRENT_DIR || "output/playwright/current";
const diffDir = process.env.VISUAL_DIFF_DIR || "output/playwright/diff";
const diffPixelThreshold = Number(process.env.VISUAL_DIFF_PIXEL_THRESHOLD || "250");
const matchThreshold = Number(process.env.VISUAL_MATCH_THRESHOLD || "0.1");

async function readPng(filePath) {
  const buffer = await fs.readFile(filePath);
  return PNG.sync.read(buffer);
}

async function writePng(filePath, image) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, PNG.sync.write(image));
}

async function main() {
  await fs.rm(currentDir, { recursive: true, force: true });
  await fs.rm(diffDir, { recursive: true, force: true });
  await ensureDir(currentDir);
  await ensureDir(diffDir);

  const result = await captureStorefrontPages({
    baseUrl,
    artifactDir: currentDir,
  });
  assertBrowserHealth(result);

  const failures = [];

  for (const spec of storefrontPages) {
    const filename = `smoke-${spec.key}.png`;
    const baselinePath = path.join(baselineDir, filename);
    const currentPath = path.join(currentDir, filename);
    const diffPath = path.join(diffDir, filename);

    try {
      await fs.access(baselinePath);
    } catch {
      failures.push(`${spec.key}: missing baseline ${path.relative(process.cwd(), baselinePath)}`);
      continue;
    }

    const baseline = await readPng(baselinePath);
    const current = await readPng(currentPath);

    if (baseline.width !== current.width || baseline.height !== current.height) {
      failures.push(
        `${spec.key}: size mismatch baseline=${baseline.width}x${baseline.height} current=${current.width}x${current.height}`
      );
      continue;
    }

    const diff = new PNG({ width: baseline.width, height: baseline.height });
    const diffPixels = pixelmatch(baseline.data, current.data, diff.data, baseline.width, baseline.height, {
      threshold: matchThreshold,
    });

    if (diffPixels > diffPixelThreshold) {
      await writePng(diffPath, diff);
      failures.push(
        `${spec.key}: ${diffPixels} pixels differ, see ${path.relative(process.cwd(), diffPath)}`
      );
    }
  }

  if (failures.length) {
    throw new Error(["Visual regression detected:", ...failures].join("\n"));
  }

  console.log(`Visual regression check passed for ${baseUrl}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
