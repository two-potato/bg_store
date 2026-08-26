 import type { Metadata } from "next";

 import { CatalogVariantPage } from "@/components/catalog/catalog-variant-page";

 export const dynamic = "force-dynamic";

 export const metadata: Metadata = {
   title: "Каталог C — быстрый выбор",
   description: "Супермаркетный быстрый выбор Servio: плотная выдача и быстрый add-to-cart.",
 };

 type CatalogVariantProps = {
   searchParams: Promise<Record<string, string | string[] | undefined>>;
 };

 export default function CatalogVariantC({ searchParams }: CatalogVariantProps) {
   return <CatalogVariantPage variant="c" searchParams={searchParams} />;
 }
