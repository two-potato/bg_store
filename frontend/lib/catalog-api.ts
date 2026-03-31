import { siteUrl } from "@/lib/site";

export const catalogPageSize = 24;

type NullableString = string | null;

export type BrandSummary = {
  id: number;
  name: string;
  slug: string;
  description?: string;
  landing_body?: string;
  faq_title?: string;
  faq_body?: string;
  meta_title?: string;
  meta_description?: string;
  photo?: string;
  products_count?: number;
  categories_count?: number;
  collections_count?: number;
};

export type SeriesSummary = {
  id: number;
  name: string;
  brand?: BrandSummary | null;
};

export type CategorySummary = {
  id: number;
  name: string;
  slug: string;
  parent: number | null;
  description?: string;
  hero_title?: string;
  hero_text?: string;
  landing_body?: string;
  faq_title?: string;
  faq_body?: string;
  meta_title?: string;
  meta_description?: string;
  photo?: string;
  full_slug_path?: string;
  product_count?: number;
};

export type CollectionSummary = {
  id: number;
  name: string;
  slug: string;
  description?: string;
  hero_title?: string;
  hero_text?: string;
  landing_body?: string;
  faq_title?: string;
  faq_body?: string;
  meta_title?: string;
  meta_description?: string;
  photo?: string;
  is_active: boolean;
  is_featured: boolean;
  products_count?: number;
};

export type ProductImage = {
  url: string;
  alt: string;
  is_primary: boolean;
  ordering: number;
};

export type ProductTag = {
  id: number;
  name: string;
  slug: string;
};

export type Product = {
  id: number;
  sku: string;
  slug: string;
  manufacturer_sku: string;
  name: string;
  brand: BrandSummary | null;
  series: SeriesSummary | null;
  category: number | null;
  category_detail?: CategorySummary | null;
  country_of_origin: NullableString;
  material: string;
  purpose: string;
  color: NullableString;
  diameter_mm: NullableString;
  height_mm: NullableString;
  length_mm: NullableString;
  width_mm: NullableString;
  volume_ml: NullableString;
  weight_g: NullableString;
  pack_qty: number;
  unit: string;
  barcode: string;
  price: string;
  stock_qty: number;
  min_order_qty?: number;
  lead_time_days?: number;
  is_new: boolean;
  is_promo: boolean;
  flavor: string;
  composition: string;
  shelf_life: string;
  description?: string;
  attributes: Record<string, string>;
  images: ProductImage[];
  tags: ProductTag[];
  seller: string | null;
};

export type CatalogFilters = {
  brand?: string;
  brand_slug?: string;
  category?: string;
  category_path?: string;
  include_descendants?: boolean;
  collection?: string;
  collection_slug?: string;
  series?: string;
  q?: string;
  is_new?: string;
  is_promo?: string;
  page?: number;
  limit?: number;
};

export type SearchMeta = {
  provider: string | null;
  effectiveQuery: string | null;
  rewrittenQuery: string | null;
};

const backendApiUrl = (process.env.BACKEND_API_URL || "http://backend:8000/api").replace(/\/$/, "");

async function fetchStorefrontResponse<T>(
  path: string,
  params?: URLSearchParams,
): Promise<{ data: T; headers: Headers }> {
  const query = params?.toString();
  const response = await fetch(`${backendApiUrl}${path}${query ? `?${query}` : ""}`, {
    cache: "no-store",
    headers: {
      accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Storefront API error: ${response.status} for ${path}`);
  }

  return {
    data: (await response.json()) as T,
    headers: response.headers,
  };
}

async function fetchStorefrontJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const response = await fetchStorefrontResponse<T>(path, params);
  return response.data;
}

function appendParam(params: URLSearchParams, key: string, value: string | number | boolean | undefined) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  if (typeof value === "boolean") {
    params.set(key, value ? "true" : "false");
    return;
  }
  params.set(key, String(value));
}

function buildCatalogProductParams(filters: CatalogFilters, limit: number, page: number) {
  const params = new URLSearchParams();

  appendParam(params, "brand", filters.brand);
  appendParam(params, "brand_slug", filters.brand_slug);
  appendParam(params, "category", filters.category);
  appendParam(params, "category_path", normalizeSlugPath(filters.category_path));
  appendParam(params, "include_descendants", filters.include_descendants);
  appendParam(params, "collection", filters.collection);
  appendParam(params, "collection_slug", filters.collection_slug);
  appendParam(params, "series", filters.series);
  appendParam(params, "q", filters.q?.trim());
  appendParam(params, "is_new", filters.is_new);
  appendParam(params, "is_promo", filters.is_promo);
  appendParam(params, "limit", limit);
  appendParam(params, "offset", (page - 1) * limit);

  return params;
}

function extractSearchMeta(headers: Headers): SearchMeta | null {
  const provider = headers.get("x-servio-search-provider");
  const effectiveQuery = headers.get("x-servio-search-effective-query");
  const rewrittenQuery = headers.get("x-servio-search-rewritten-query");

  if (!provider && !effectiveQuery && !rewrittenQuery) {
    return null;
  }

  return {
    provider,
    effectiveQuery,
    rewrittenQuery,
  };
}

export async function getCatalogPageData(filters: CatalogFilters) {
  const productList = await getProductList(filters);
  const [brands, categories, collections] = await Promise.all([
    getBrands(),
    getCategories(),
    getCollections(),
  ]);

  return {
    ...productList,
    brands,
    categories,
    collections,
  };
}

export async function getProductList(filters: CatalogFilters) {
  const page = Math.max(1, Number(filters.page) || 1);
  const limit = Math.max(1, Number(filters.limit) || catalogPageSize);
  const params = buildCatalogProductParams(filters, limit, page);
  const response = await fetchStorefrontResponse<Product[]>("/catalog/products/", params);

  return {
    products: response.data,
    page,
    limit,
    hasNextPage: response.data.length === limit,
    searchMeta: extractSearchMeta(response.headers),
  };
}

export async function getProductBySlug(slug: string) {
  const params = new URLSearchParams({ slug, limit: "1" });
  const products = await fetchStorefrontJson<Product[]>("/catalog/products/", params);
  return products[0] || null;
}

export async function getRelatedProducts(product: Product, limit = 4) {
  const params = new URLSearchParams({ limit: String(Math.max(limit + 1, 6)) });

  if (product.brand?.id) {
    params.set("brand", String(product.brand.id));
  } else if (product.category) {
    params.set("category", String(product.category));
  } else {
    return [];
  }

  const products = await fetchStorefrontJson<Product[]>("/catalog/products/", params);
  return products.filter((item) => item.id !== product.id).slice(0, limit);
}

export async function getBrands() {
  return fetchStorefrontJson<BrandSummary[]>("/catalog/brands/");
}

export async function getCollections() {
  return fetchStorefrontJson<CollectionSummary[]>("/catalog/collections/");
}

export async function getCategories() {
  return fetchStorefrontJson<CategorySummary[]>("/catalog/categories/");
}

export async function getDiscoveryDirectoryData() {
  const [brands, categories, collections] = await Promise.all([
    getBrands(),
    getCategories(),
    getCollections(),
  ]);

  return {
    brands,
    categories,
    collections,
  };
}

export async function getBrandBySlug(slug: string) {
  const normalized = slug.trim();
  if (!normalized) {
    return null;
  }
  const brands = await getBrands();
  return brands.find((brand) => brand.slug === normalized) || null;
}

export async function getCollectionBySlug(slug: string) {
  const normalized = slug.trim();
  if (!normalized) {
    return null;
  }
  const collections = await getCollections();
  return collections.find((collection) => collection.slug === normalized) || null;
}

export async function getCategoryByPath(slugPath: string) {
  const normalized = normalizeSlugPath(slugPath);
  if (!normalized) {
    return null;
  }
  const categories = await getCategories();
  return categories.find((category) => normalizeSlugPath(category.full_slug_path) === normalized) || null;
}

export function normalizeSlugPath(value: string | null | undefined) {
  return (value || "")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean)
    .join("/");
}

export function pickText(...values: Array<string | null | undefined>) {
  for (const value of values) {
    if (!value) {
      continue;
    }
    const normalized = value.replace(/\s+/g, " ").trim();
    if (normalized) {
      return normalized;
    }
  }
  return "";
}

export function normalizeAssetUrl(url: string | null | undefined) {
  if (!url) {
    return "/static/shopfront/product-placeholder.svg";
  }

  try {
    if (url.startsWith("/")) {
      return new URL(url, siteUrl()).toString();
    }

    const parsed = new URL(url);
    if (["localhost", "127.0.0.1", "0.0.0.0", "backend"].includes(parsed.hostname)) {
      return new URL(`${parsed.pathname}${parsed.search}`, siteUrl()).toString();
    }
    return parsed.toString();
  } catch {
    return url;
  }
}

export function getPrimaryImage(product: Product) {
  const primary = product.images.find((image) => image.is_primary);
  return primary || product.images[0] || null;
}

export function formatPrice(value: string | number | null | undefined) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "Цена по запросу";
  }
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(value: string | number | null | undefined, suffix: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return null;
  }
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(amount)} ${suffix}`;
}

export function productFactList(product: Product) {
  return [
    product.category_detail?.name ? `Категория: ${product.category_detail.name}` : null,
    product.material ? `Материал: ${product.material}` : null,
    product.color ? `Цвет: ${product.color}` : null,
    product.country_of_origin ? `Страна: ${product.country_of_origin}` : null,
    formatNumber(product.volume_ml, "мл") ? `Объём: ${formatNumber(product.volume_ml, "мл")}` : null,
  ].filter(Boolean) as string[];
}

export function productDimensionEntries(product: Product) {
  return [
    { label: "Диаметр", value: formatNumber(product.diameter_mm, "мм") },
    { label: "Высота", value: formatNumber(product.height_mm, "мм") },
    { label: "Длина", value: formatNumber(product.length_mm, "мм") },
    { label: "Ширина", value: formatNumber(product.width_mm, "мм") },
    { label: "Объём", value: formatNumber(product.volume_ml, "мл") },
    { label: "Вес", value: formatNumber(product.weight_g, "г") },
  ].filter((entry) => entry.value);
}
