import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

export const defaultBaseUrl = (process.env.SMOKE_BASE_URL || "http://127.0.0.1:8080").replace(/\/+$/, "");
const baseHost = new URL(defaultBaseUrl).hostname;

const externalHosts = [
  "fonts.googleapis.com",
  "fonts.gstatic.com",
  "www.googletagmanager.com",
  "telegram.org",
  "complaexbar.ru",
  "d.clarity.ms",
];

export const storefrontPages = [
  {
    key: "home",
    url: "/",
    title: "Servio",
    viewport: { width: 1440, height: 960 },
    ready: async (page) => {
      await page.waitForFunction(() => !!document.querySelector("#main-content"));
    },
  },
  {
    key: "catalog",
    url: "/catalog/",
    title: "Каталог",
    viewport: { width: 1440, height: 960 },
    ready: async (page) => {
      await page.locator("section.catalog-layout-neo").waitFor();
    },
  },
  {
    key: "product",
    url: "/product/smoke-product/",
    title: "Smoke Product",
    viewport: { width: 1440, height: 960 },
    shellSelector: "body",
    ready: async () => {},
  },
  {
    key: "cart",
    url: "/cart/",
    title: "Корзина",
    viewport: { width: 1440, height: 960 },
    ready: async (page) => {
      await page.waitForFunction(() => !!document.querySelector("#main-content"));
    },
  },
  {
    key: "cart-filled",
    viewport: { width: 1440, height: 960 },
    navigate: async (page, baseUrl) => {
      await page.goto(`${baseUrl}/product/smoke-product/`, { waitUntil: "networkidle" });
      const productResponse = await page.context().request.get(`${baseUrl}/product/smoke-product/`);
      const pageHtml = await productResponse.text();
      const productIdMatch = pageHtml.match(/data-product-id="(\d+)"/);
      const productId = productIdMatch?.[1] || "";
      if (!productId) {
        throw new Error("cart-filled: missing product id on smoke product page");
      }
      const cookies = await page.context().cookies();
      const csrfCookie = cookies.find((cookie) => cookie.name === "csrftoken");
      const response = await page.context().request.post(`${baseUrl}/cart/add/`, {
        form: {
          product_id: productId,
          qty: "1",
          csrfmiddlewaretoken: csrfCookie?.value || "",
        },
        headers: {
          Origin: baseUrl,
          Referer: `${baseUrl}/product/smoke-product/`,
        },
      });
      if (!response.ok()) {
        throw new Error(`cart-filled: cart add request failed with ${response.status()}`);
      }
      await page.goto(`${baseUrl}/cart/`, { waitUntil: "networkidle" });
    },
    title: "Корзина",
    ready: async (page) => {
      await page.waitForFunction(() => !!document.querySelector("#main-content"));
      await page.waitForFunction(() => {
        const bodyText = document.body?.innerText || "";
        return bodyText.includes("Smoke Product");
      });
    },
  },
  {
    key: "checkout",
    url: "/checkout/",
    title: "Оформление заказа",
    viewport: { width: 1440, height: 960 },
    ready: async (page) => {
      await page.getByRole("heading", { name: /Корзина/i }).waitFor();
      await page.locator('form[hx-post="/checkout/submit/"]').waitFor();
    },
  },
  {
    key: "home-mobile",
    url: "/",
    title: "Servio",
    viewport: { width: 390, height: 844 },
    ready: async (page) => {
      await page.waitForFunction(() => !!document.querySelector("#main-content"));
      await page.waitForFunction(() => !!document.querySelector(".mobile-nav-mint-link"));
    },
  },
  {
    key: "catalog-mobile",
    url: "/catalog/",
    title: "Каталог",
    viewport: { width: 390, height: 844 },
    ready: async (page) => {
      await page.locator("section.catalog-layout-neo").waitFor();
      await page.waitForSelector('[data-carousel-track]');
    },
  },
  {
    key: "cart-mobile",
    url: "/cart/",
    title: "Корзина",
    viewport: { width: 390, height: 844 },
    ready: async (page) => {
      await page.waitForFunction(() => !!document.querySelector("#main-content"));
      await page.waitForFunction(() => !!document.querySelector(".mobile-nav-mint-link.is-active"));
    },
  },
];

export async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

function isExternalNoise(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== baseHost && parsed.hostname !== "127.0.0.1" && parsed.hostname !== "localhost") {
      return true;
    }
    return externalHosts.some((host) => parsed.hostname === host);
  } catch {
    return false;
  }
}

async function assertCoreShell(page, pageName, expectedTitle, shellSelector = "#main-content") {
  await page.waitForFunction((selector) => !!document.querySelector(selector), shellSelector);
  const title = await page.title();
  if (!title || !title.includes(expectedTitle)) {
    throw new Error(`${pageName}: unexpected title "${title}"`);
  }
  const hasTailwindAsset = await page.evaluate(() =>
    Array.from(document.querySelectorAll('link[rel="stylesheet"]')).some((node) =>
      (node.getAttribute("href") || "").includes("/static/css/app.css")
    )
  );
  if (!hasTailwindAsset) {
    throw new Error(`${pageName}: /static/css/app.css was not loaded`);
  }
}

export async function captureStorefrontPages({
  baseUrl = defaultBaseUrl,
  artifactDir,
} = {}) {
  const pageErrors = [];
  const requestFailures = [];
  const consoleErrors = [];
  const screenshots = {};

  await ensureDir(artifactDir);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: storefrontPages[0].viewport || { width: 1440, height: 960 },
    baseURL: baseUrl,
  });
  await context.addInitScript(() => {
    const style = document.createElement("style");
    style.setAttribute("data-visual-stability", "1");
    style.textContent = `
      *,
      *::before,
      *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
      html {
        scroll-behavior: auto !important;
      }
    `;
    document.addEventListener("DOMContentLoaded", () => {
      document.head.appendChild(style);
    });
  });
  const page = await context.newPage();

  await page.route("**/*", async (route) => {
    if (isExternalNoise(route.request().url())) {
      await route.abort();
      return;
    }
    await route.continue();
  });

  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !/ERR_FAILED|ERR_NAME_NOT_RESOLVED|ERR_ABORTED/.test(message.text())
    ) {
      consoleErrors.push(message.text());
    }
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (!isExternalNoise(url)) {
      requestFailures.push(`${request.failure()?.errorText || "requestfailed"} ${url}`);
    }
  });

  try {
    for (const spec of storefrontPages) {
      console.log(`Capturing ${spec.key}`);
      if (spec.viewport) {
        await page.setViewportSize(spec.viewport);
      }
      if (spec.url) {
        await page.goto(`${baseUrl}${spec.url}`, { waitUntil: "networkidle" });
      } else if (spec.navigate) {
        await spec.navigate(page, baseUrl);
        await page.waitForLoadState("networkidle");
      }
      await assertCoreShell(page, spec.key, spec.title, spec.shellSelector);
      await spec.ready(page);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(150);
      const screenshotPath = path.join(artifactDir, `smoke-${spec.key}.png`);
      await page.screenshot({ path: screenshotPath });
      screenshots[spec.key] = screenshotPath;
    }
  } finally {
    await browser.close();
  }

  return {
    pageErrors,
    requestFailures,
    consoleErrors,
    screenshots,
  };
}

export function assertBrowserHealth(result) {
  if (result.pageErrors.length || result.requestFailures.length || result.consoleErrors.length) {
    throw new Error(
      [
        result.pageErrors.length ? `pageErrors:\n${result.pageErrors.join("\n")}` : "",
        result.consoleErrors.length ? `consoleErrors:\n${result.consoleErrors.join("\n")}` : "",
        result.requestFailures.length ? `requestFailures:\n${result.requestFailures.join("\n")}` : "",
      ]
        .filter(Boolean)
        .join("\n\n")
    );
  }
}
