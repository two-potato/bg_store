 import type { Metadata } from "next";

 import { CatalogVariantPage } from "@/components/catalog/catalog-variant-page";

 export const dynamic = "force-dynamic";

 export const metadata: Metadata = {
   title: "Каталог A — классика",
   description: "Классический marketplace-каталог Servio с фильтрами и сравнением.",
 };

 type CatalogVariantProps = {
   searchParams: Promise<Record<string, string | string[] | undefined>>;
 };

 export default function CatalogVariantA({ searchParams }: CatalogVariantProps) {
   return <CatalogVariantPage variant="a" searchParams={searchParams} />;
 }
