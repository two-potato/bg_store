 import type { Metadata } from "next";

 import { CatalogVariantPage } from "@/components/catalog/catalog-variant-page";

 export const dynamic = "force-dynamic";

 export const metadata: Metadata = {
   title: "Каталог B — mobile-first",
   description: "Mobile-first каталог Servio для быстрых закупок и минимального числа кликов.",
 };

 type CatalogVariantProps = {
   searchParams: Promise<Record<string, string | string[] | undefined>>;
 };

 export default function CatalogVariantB({ searchParams }: CatalogVariantProps) {
   return <CatalogVariantPage variant="b" searchParams={searchParams} />;
 }
