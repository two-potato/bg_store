import { chromium } from "playwright";

const baseUrl = (process.env.SMOKE_BASE_URL || "http://127.0.0.1:8080").replace(/\/+$/, "");
const smokeUser = process.env.BUYER_SMOKE_USER || "smoke-user";
const smokePassword = process.env.BUYER_SMOKE_PASSWORD || "smoke-pass-2026";

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function getCsrfToken(context) {
  const cookies = await context.cookies();
  return cookies.find((cookie) => cookie.name === "csrftoken")?.value || "";
}

function absoluteUrl(href) {
  return new URL(href, `${baseUrl}/`).toString();
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL: baseUrl });
  const page = await context.newPage();
  const errors = [];

  const noteFailure = (message) => {
    errors.push(message);
    console.error(`SMOKE FAIL: ${message}`);
  };

  try {
    await page.goto(`${baseUrl}/cart`, { waitUntil: "networkidle" });
    const cartTitle = await page.title();
    assert(cartTitle.includes("Корзина"), `unauth /cart: unexpected title "${cartTitle}"`);
    const cartHtml = await page.content();
    assert(
      !cartHtml.includes("http://localhost:8000/account/login/"),
      "unauth /cart: HTML still contains localhost login fallback",
    );
    console.log("Buyer smoke: unauth /cart passed");

    await page.goto(`${baseUrl}/account`, { waitUntil: "networkidle" });
    const accountHtml = await page.content();
    assert(
      !accountHtml.includes("http://localhost:8000/account/login/"),
      "unauth /account: HTML still contains localhost login fallback",
    );
    console.log("Buyer smoke: unauth /account passed");

    const loginLink = page.locator('a[href*="account/login/"]').first();
    await loginLink.waitFor();
    const loginHref = await loginLink.getAttribute("href");
    assert(loginHref, "unauth /account: missing login CTA href");
    assert(
      !loginHref.includes("localhost:8000"),
      `unauth /account: CTA still points to localhost (${loginHref})`,
    );

    const ctaResponse = await context.request.get(absoluteUrl(loginHref), {
      maxRedirects: 5,
    });
    if (ctaResponse.status() >= 400) {
      noteFailure(
        `unauth /account CTA target is not reachable: ${loginHref} -> HTTP ${ctaResponse.status()}`,
      );
    } else {
      console.log(`Buyer smoke: unauth CTA target reachable (${loginHref})`);
    }

    await context.request.get(`${baseUrl}/account/login/?next=%2Faccount`);
    const loginCsrfToken = await getCsrfToken(context);
    assert(loginCsrfToken, "auth flow: missing csrftoken before login");

    const loginResponse = await context.request.post(`${baseUrl}/account/login/?next=%2Faccount`, {
      form: {
        identifier: smokeUser,
        password: smokePassword,
        csrfmiddlewaretoken: loginCsrfToken,
      },
      headers: {
        Referer: `${baseUrl}/account/login/?next=%2Faccount`,
      },
      maxRedirects: 0,
    });
    assert(
      [301, 302, 303].includes(loginResponse.status()),
      `login submit returned ${loginResponse.status()} instead of redirect`,
    );

    await page.goto(`${baseUrl}/account`, { waitUntil: "networkidle" });

    const accountTitle = await page.title();
    assert(accountTitle.includes("Buyer Account"), `auth /account: unexpected title "${accountTitle}"`);
    const accountContent = await page.content();
    assert(
      accountContent.includes(smokeUser),
      "auth /account: buyer shell did not render authenticated username",
    );
    console.log("Buyer smoke: auth /account passed");

    const csrfToken = await getCsrfToken(context);
    assert(csrfToken, "auth flow: missing csrftoken cookie after login");

    const clearResponse = await context.request.post(`${baseUrl}/api/storefront/cart/clear/`, {
      data: {},
      headers: {
        accept: "application/json",
        "content-type": "application/json",
        "x-csrftoken": csrfToken,
        "x-requested-with": "XMLHttpRequest",
      },
    });
    assert(clearResponse.ok(), `cart clear failed with ${clearResponse.status()}`);

    const productResponse = await context.request.get(
      `${baseUrl}/api/catalog/products/?slug=smoke-product&limit=1`,
    );
    assert(productResponse.ok(), `catalog lookup failed with ${productResponse.status()}`);
    const products = await productResponse.json();
    const smokeProduct = Array.isArray(products) ? products[0] : null;
    assert(smokeProduct?.id, "catalog lookup: smoke-product not found");

    const addResponse = await context.request.post(`${baseUrl}/api/storefront/cart/add/`, {
      data: { product_id: smokeProduct.id, qty: 1 },
      headers: {
        accept: "application/json",
        "content-type": "application/json",
        "x-csrftoken": csrfToken,
        "x-requested-with": "XMLHttpRequest",
      },
    });
    assert(addResponse.ok(), `cart add failed with ${addResponse.status()}`);
    console.log("Buyer smoke: cart add passed");

    const checkoutResponse = await context.request.post(`${baseUrl}/checkout/submit/`, {
      form: {
        customer_type: "individual",
        payment_method: "cash",
        delivery_method: "courier",
        customer_name: "Smoke Buyer",
        customer_email: "smoke@example.com",
        customer_phone: "+79990001122",
        address_text: "Moscow, Smoke street, 1",
        csrfmiddlewaretoken: csrfToken,
      },
      headers: {
        Referer: `${baseUrl}/checkout/`,
      },
      maxRedirects: 0,
    });
    assert(
      [301, 302, 303].includes(checkoutResponse.status()),
      `checkout submit returned ${checkoutResponse.status()} instead of redirect`,
    );
    const orderLocation = checkoutResponse.headers()["location"];
    assert(orderLocation, "checkout submit: missing redirect location");
    const orderUrl = absoluteUrl(orderLocation);
    const orderIdMatch = orderUrl.match(/\/account\/orders\/(\d+)\/?$/);
    assert(orderIdMatch, `checkout redirect did not point to buyer order detail (${orderUrl})`);
    const orderId = orderIdMatch[1];
    console.log(`Buyer smoke: checkout created order ${orderId}`);

    await page.goto(`${baseUrl}/account/orders`, { waitUntil: "networkidle" });
    const ordersHtml = await page.content();
    assert(
      ordersHtml.includes(`/account/orders/${orderId}`),
      `orders list does not contain freshly created order ${orderId}`,
    );
    console.log("Buyer smoke: orders list passed");

    await page.goto(`${baseUrl}/account/orders/${orderId}`, { waitUntil: "networkidle" });
    await page.locator("h1").filter({ hasText: `Заказ #${orderId}` }).waitFor();
    const reorderButton = page.getByRole("button", { name: "Повторить заказ" });
    await reorderButton.waitFor();
    await reorderButton.click();
    await page.waitForSelector(".servio-order-reorder__result");
    const detailHtml = await page.content();
    assert(
      /Все позиции добавлены|Часть позиций добавлена|Позиции не удалось добавить/.test(detailHtml),
      "order detail: reorder result message did not render",
    );
    console.log("Buyer smoke: order detail + reorder passed");

    await page.goto(`${baseUrl}/cart`, { waitUntil: "networkidle" });
    const finalCartHtml = await page.content();
    assert(finalCartHtml.includes("Smoke Product"), "cart after reorder does not contain Smoke Product");
    console.log("Buyer smoke: cart after reorder passed");

    if (errors.length) {
      throw new Error(errors.join("\n"));
    }

    console.log(`Buyer wave smoke passed for ${baseUrl}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
