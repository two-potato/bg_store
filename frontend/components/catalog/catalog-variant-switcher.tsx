 import Link from "next/link";

type CatalogVariant = "a" | "b" | "c" | "d";

 type CatalogVariantSwitcherProps = {
   active: CatalogVariant;
 };

const variants: Array<{ id: CatalogVariant; label: string; href: string; description: string }> = [
   {
     id: "a",
     label: "A",
     href: "/catalog-a",
     description: "Классика маркетплейса",
   },
   {
     id: "b",
     label: "B",
     href: "/catalog-b",
     description: "Mobile-first",
   },
  {
    id: "c",
    label: "C",
    href: "/catalog-c",
    description: "Быстрый выбор",
  },
  {
    id: "d",
    label: "D",
    href: "/catalog-d",
    description: "Mobile-only",
  },
];

 export function CatalogVariantSwitcher({ active }: CatalogVariantSwitcherProps) {
   return (
     <nav className="market-variant-switcher" aria-label="Переключение концепций каталога">
       {variants.map((variant) => (
         <Link
           key={variant.id}
           href={variant.href}
           className={`market-variant-switcher__item ${variant.id === active ? "is-active" : ""}`}
         >
           <span className="market-variant-switcher__label">{variant.label}</span>
           <span className="market-variant-switcher__desc">{variant.description}</span>
         </Link>
       ))}
     </nav>
   );
 }
