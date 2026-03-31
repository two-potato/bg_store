 import type { CatalogFilters, CategorySummary, Product } from "@/lib/catalog-api";

export type CatalogVariant = "a" | "b" | "c" | "d";

 export type CatalogUiFilters = {
   q?: string;
   sort?: string;
   view?: string;
   availability?: string;
   rating?: string;
   price_min?: string;
   price_max?: string;
 };

 export function readSearchParam(value: string | string[] | undefined) {
   if (Array.isArray(value)) {
     return value[0];
   }
   return value;
 }

 export function normalizeCatalogFilters(params: Record<string, string | string[] | undefined>) {
   const page = Number(readSearchParam(params.page));
 
   const filters: CatalogFilters = {
     brand: readSearchParam(params.brand),
     category: readSearchParam(params.category),
     series: readSearchParam(params.series),
     is_new: readSearchParam(params.is_new),
     is_promo: readSearchParam(params.is_promo),
     q: readSearchParam(params.q),
     page: Number.isFinite(page) && page > 0 ? page : 1,
   };
 
   const ui: CatalogUiFilters = {
     q: readSearchParam(params.q),
     sort: readSearchParam(params.sort) || "popular",
     view: readSearchParam(params.view) || "grid",
     availability: readSearchParam(params.availability),
     rating: readSearchParam(params.rating),
     price_min: readSearchParam(params.price_min),
     price_max: readSearchParam(params.price_max),
   };
 
   return { filters, ui };
 }

 export function buildCatalogVariantHref(
   variant: CatalogVariant,
   filters: CatalogFilters,
   ui: CatalogUiFilters,
   overrides: Partial<CatalogFilters & CatalogUiFilters>,
 ) {
   const params = new URLSearchParams();
   const nextFilters: CatalogFilters = { ...filters, ...overrides };
   const nextUi: CatalogUiFilters = { ...ui, ...overrides };
 
   if (nextFilters.brand) params.set("brand", nextFilters.brand);
   if (nextFilters.category) params.set("category", nextFilters.category);
   if (nextFilters.series) params.set("series", nextFilters.series);
   if (nextFilters.is_new) params.set("is_new", nextFilters.is_new);
   if (nextFilters.is_promo) params.set("is_promo", nextFilters.is_promo);
   if (nextFilters.q) params.set("q", nextFilters.q);
 
   if (nextUi.sort) params.set("sort", nextUi.sort);
   if (nextUi.view) params.set("view", nextUi.view);
   if (nextUi.availability) params.set("availability", nextUi.availability);
   if (nextUi.rating) params.set("rating", nextUi.rating);
   if (nextUi.price_min) params.set("price_min", nextUi.price_min);
   if (nextUi.price_max) params.set("price_max", nextUi.price_max);
 
   if (nextFilters.page && nextFilters.page > 1) {
     params.set("page", String(nextFilters.page));
   }
 
   const query = params.toString();
   return query ? `/catalog-${variant}?${query}` : `/catalog-${variant}`;
 }

export function filterProducts(products: Product[], ui: CatalogUiFilters) {
  let filtered = [...products];

  if (ui.availability === "in_stock") {
    filtered = filtered.filter((product) => product.stock_qty > 0);
  }

  if (ui.rating === "4plus") {
    filtered = filtered.filter((product) => {
      const raw =
        product.attributes?.rating_avg ??
        product.attributes?.rating ??
        product.attributes?.rating_value ??
        "0";
      const value = Number(raw);
      return Number.isFinite(value) && value >= 4;
    });
  }
 
   const minPrice = ui.price_min ? Number(ui.price_min) : null;
   const maxPrice = ui.price_max ? Number(ui.price_max) : null;
 
   if (Number.isFinite(minPrice)) {
     filtered = filtered.filter((product) => Number(product.price) >= (minPrice ?? 0));
   }
   if (Number.isFinite(maxPrice)) {
     filtered = filtered.filter((product) => Number(product.price) <= (maxPrice ?? 0));
   }
 
  return filtered;
}

 export function sortProducts(products: Product[], sort: string | undefined) {
   const sorted = [...products];
 
   if (sort === "price_asc") {
     sorted.sort((a, b) => Number(a.price) - Number(b.price));
     return sorted;
   }
   if (sort === "price_desc") {
     sorted.sort((a, b) => Number(b.price) - Number(a.price));
     return sorted;
   }
   if (sort === "new") {
     sorted.sort((a, b) => Number(b.is_new) - Number(a.is_new));
     return sorted;
   }
   if (sort === "promo") {
     sorted.sort((a, b) => Number(b.is_promo) - Number(a.is_promo));
     return sorted;
   }
 
   return sorted;
 }

 export function pickRootCategories(categories: CategorySummary[]) {
   return categories.filter((category) => category.parent === null).slice(0, 10);
 }
