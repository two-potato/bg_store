import { CatalogVariantPage } from "@/components/catalog/catalog-variant-page";

type CatalogVariantProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default function CatalogVariantD({ searchParams }: CatalogVariantProps) {
  return <CatalogVariantPage variant="d" searchParams={searchParams} />;
}
