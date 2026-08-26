 import Link from "next/link";

 import { CatalogProductCard } from "@/components/catalog/catalog-product-card";
 import { CatalogVariantSwitcher } from "@/components/catalog/catalog-variant-switcher";
 import {
   buildCatalogVariantHref,
   filterProducts,
   normalizeCatalogFilters,
   pickRootCategories,
   sortProducts,
   type CatalogUiFilters,
   type CatalogVariant,
 } from "@/lib/catalog-variant-utils";
 import { getCatalogPageData, type BrandSummary, type CategorySummary } from "@/lib/catalog-api";
 import { getStorefrontCartSnapshot, getStorefrontSessionBootstrap } from "@/lib/buyer-account-api";

 type CatalogVariantPageProps = {
   variant: CatalogVariant;
   searchParams: Promise<Record<string, string | string[] | undefined>>;
 };

 const sortOptions = [
   { value: "popular", label: "Популярное" },
   { value: "price_asc", label: "Цена по возрастанию" },
   { value: "price_desc", label: "Цена по убыванию" },
   { value: "promo", label: "Скидки" },
   { value: "new", label: "Новинки" },
 ];

 const grocerySortSegments = [
   { value: "popular", label: "Популярное" },
   { value: "price_asc", label: "Цена" },
   { value: "promo", label: "Скидки" },
 ];

 function resolveHeading(
   variant: CatalogVariant,
   selectedBrand: BrandSummary | undefined,
   selectedCategory: CategorySummary | undefined,
 ) {
   if (selectedCategory) {
     return {
       title: selectedCategory.name,
       copy: "Категория с быстрым отбором по цене, наличию и рейтингу. Всё самое важное видно сразу.",
     };
   }
   if (selectedBrand) {
     return {
       title: selectedBrand.name,
       copy: "Брендовая выдача с фокусом на цену, наличие и скорость выбора.",
     };
   }
  return {
    title:
      variant === "d"
        ? "Каталог быстрой закупки"
        : variant === "c"
        ? "Каталог для быстрого выбора"
        : variant === "b"
          ? "Каталог для мобильных закупок"
          : "Каталог Servio",
    copy:
      variant === "d"
        ? "Mobile-only лента для быстрого набора корзины."
        : variant === "c"
        ? "Минимум действий: выбирайте нужное и сразу добавляйте в корзину."
        : variant === "b"
          ? "Mobile-first каталог для быстрых повторных закупок."
          : "Классический каталог с понятными фильтрами и сравнением.",
  };
}

 function renderFilterForm(
   variant: CatalogVariant,
   filters: CatalogUiFilters,
   catalogFilters: Record<string, string | undefined>,
   options?: { hideSearch?: boolean; hideSort?: boolean },
 ) {
   const formAction = `/catalog-${variant}`;
   return (
      <form className="market-filters" action={formAction}>
        {catalogFilters.brand ? <input type="hidden" name="brand" value={catalogFilters.brand} /> : null}
        {catalogFilters.category ? <input type="hidden" name="category" value={catalogFilters.category} /> : null}
        {catalogFilters.series ? <input type="hidden" name="series" value={catalogFilters.series} /> : null}
        {filters.q ? <input type="hidden" name="q" value={filters.q} /> : null}
        <input type="hidden" name="page" value="1" />
        <input type="hidden" name="view" value={filters.view || "grid"} />
       {options?.hideSearch ? null : (
         <div className="market-filter-group">
           <label className="market-filter-label" htmlFor={`q-${variant}`}>
             Поиск
           </label>
           <input
             id={`q-${variant}`}
             type="search"
             name="q"
             defaultValue={filters.q}
             placeholder="Например: соусники, стаканы, перчатки"
             className="market-input"
           />
         </div>
       )}
 
       <div className="market-filter-group">
         <span className="market-filter-label">Цена</span>
         <div className="market-range">
           <input
             type="number"
             inputMode="numeric"
             name="price_min"
             placeholder="От"
             defaultValue={filters.price_min}
             className="market-input"
           />
           <input
             type="number"
             inputMode="numeric"
             name="price_max"
             placeholder="До"
             defaultValue={filters.price_max}
             className="market-input"
           />
         </div>
       </div>
 
       <div className="market-filter-group">
         <span className="market-filter-label">Наличие</span>
         <label className="market-check">
           <input type="radio" name="availability" value="" defaultChecked={!filters.availability} />
           <span>Все</span>
         </label>
         <label className="market-check">
           <input
             type="radio"
             name="availability"
             value="in_stock"
             defaultChecked={filters.availability === "in_stock"}
           />
           <span>В наличии</span>
         </label>
       </div>
 
       <div className="market-filter-group">
         <span className="market-filter-label">Рейтинг</span>
         <label className="market-check">
           <input
             type="radio"
             name="rating"
             value=""
             defaultChecked={!filters.rating}
           />
           <span>Любой</span>
         </label>
         <label className="market-check">
           <input
             type="radio"
             name="rating"
             value="4plus"
             defaultChecked={filters.rating === "4plus"}
           />
           <span>4+ и выше</span>
         </label>
       </div>
 
       <div className="market-filter-group">
         <span className="market-filter-label">Подборки</span>
         <label className="market-check">
           <input type="checkbox" name="is_new" value="true" defaultChecked={catalogFilters.is_new === "true"} />
           <span>Новинки</span>
         </label>
         <label className="market-check">
           <input type="checkbox" name="is_promo" value="true" defaultChecked={catalogFilters.is_promo === "true"} />
           <span>Скидки</span>
         </label>
       </div>
 
       {options?.hideSort ? null : (
         <div className="market-filter-group">
           <label className="market-filter-label" htmlFor={`sort-${variant}`}>
             Сортировка
           </label>
           <select id={`sort-${variant}`} name="sort" defaultValue={filters.sort} className="market-select">
             {sortOptions.map((option) => (
               <option key={option.value} value={option.value}>
                 {option.label}
               </option>
             ))}
           </select>
         </div>
       )}
 
       <div className="market-filter-actions">
         <button type="submit" className="market-button">
           Применить
         </button>
       </div>
     </form>
   );
 }

 export async function CatalogVariantPage({ variant, searchParams }: CatalogVariantPageProps) {
   const resolvedParams = await searchParams;
   const { filters, ui } = normalizeCatalogFilters(resolvedParams);
 
   try {
     const [{ products, brands, categories, page, hasNextPage }, session] = await Promise.all([
       getCatalogPageData(filters),
       getStorefrontSessionBootstrap().catch(() => null),
     ]);
 
     const cartSnapshot = await getStorefrontCartSnapshot().catch(() => null);
     const cartMap = new Map<number, number>();
     cartSnapshot?.cart?.items?.forEach((item) => cartMap.set(item.product.id, item.qty));
 
     const selectedBrand = brands.find((brand) => String(brand.id) === filters.brand);
     const selectedCategory = categories.find((category) => String(category.id) === filters.category);
     const heading = resolveHeading(variant, selectedBrand, selectedCategory);
     const rootCategories = pickRootCategories(categories);
     const featuredBrands = brands.slice(0, 10);
 
     const filtered = filterProducts(products, ui);
     const sortedProducts = sortProducts(filtered, ui.sort);
 
    const cartCount = session?.cart_badge?.count || 0;
    const cartSubtotal = session?.cart_badge?.subtotal || "0 ₽";
    const cartUrl = session?.urls?.cart || "/cart";
    const activeFilterCount = [
      ui.availability,
      ui.rating,
      ui.price_min,
      ui.price_max,
      filters.is_new,
      filters.is_promo,
      filters.brand,
      filters.series,
    ].filter(Boolean).length;

    return (
      <div className={`market-catalog market-catalog--${variant}`}>
        {variant === "d" ? (
          <header className="market-catalog__header market-catalog__header--d">
            <div className="market-d-header">
              <form action={`/catalog-${variant}`} className="market-search market-search--compact market-search--d">
                <input
                  type="search"
                  name="q"
                  defaultValue={ui.q}
                  placeholder="Найти товар"
                  className="market-search__input"
                  aria-label="Поиск по каталогу"
                />
                <button type="submit" className="market-button market-button--primary">
                  Найти
                </button>
              </form>
              <Link href={cartUrl} className="market-cart-chip" aria-label="Открыть корзину">
                {cartCount} · {cartSubtotal}
              </Link>
            </div>
          </header>
        ) : variant === "c" ? (
          <header className="market-catalog__header market-catalog__header--c">
            <div className="market-c-header__top">
              <form action={`/catalog-${variant}`} className="market-search market-search--compact">
                 <input
                   type="search"
                   name="q"
                   defaultValue={ui.q}
                   placeholder="Быстрый поиск по товарам"
                   className="market-search__input"
                   aria-label="Поиск по каталогу"
                 />
                 <button type="submit" className="market-button market-button--primary">
                   Найти
                 </button>
               </form>
               <div className="market-c-header__meta">
                 <Link href={cartUrl} className="market-cart-entry" aria-label="Открыть корзину">
                   {cartCount} · {session?.cart_badge?.subtotal || "0 ₽"}
                 </Link>
                 <Link href={session?.urls?.account || "/account"} className="market-account-chip">
                   Аккаунт
                 </Link>
               </div>
             </div>
             <div className="market-c-header__bottom">
               <div className="market-c-departments" aria-label="Отделы">
                 {rootCategories.map((category) => (
                   <Link
                     key={category.id}
                     href={buildCatalogVariantHref(variant, filters, ui, { category: String(category.id), page: 1 })}
                     className={`market-chip ${String(category.id) === filters.category ? "is-active" : ""}`}
                   >
                     {category.name}
                   </Link>
                 ))}
               </div>
               <div className="market-c-modes" aria-label="Быстрые режимы">
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { availability: "in_stock", page: 1 })}
                   className={`market-chip ${ui.availability === "in_stock" ? "is-active" : ""}`}
                 >
                   В наличии
                 </Link>
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { is_promo: "true", page: 1 })}
                   className={`market-chip ${filters.is_promo ? "is-active" : ""}`}
                 >
                   Скидки
                 </Link>
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { price_max: "500", page: 1 })}
                   className={`market-chip ${ui.price_max === "500" ? "is-active" : ""}`}
                 >
                   До 500
                 </Link>
               </div>
             </div>
           </header>
         ) : (
           <header className="market-catalog__header">
             <div>
               <p className="market-kicker">Каталог Servio</p>
               <h1 className="market-title">{heading.title}</h1>
               <p className="market-lead">{heading.copy}</p>
             </div>
             <div className="market-header-actions">
               <form action={`/catalog-${variant}`} className="market-search">
                 <input
                   type="search"
                   name="q"
                   defaultValue={ui.q}
                   placeholder="Поиск по товарам, брендам и категориям"
                   className="market-search__input"
                   aria-label="Поиск по каталогу"
                 />
                 <button type="submit" className="market-button market-button--primary">
                   Найти
                 </button>
               </form>
              <CatalogVariantSwitcher active={variant} />
              <Link href={cartUrl} className="market-cart-entry" aria-label="Открыть корзину">
                Корзина
                <span>{cartCount}</span>
              </Link>
            </div>
          </header>
        )}

        {variant === "c" || variant === "d" ? null : (
          <section className="market-catalog__chips">
            <Link
              href={buildCatalogVariantHref(variant, filters, ui, { category: undefined, page: 1 })}
               className={`market-chip ${!filters.category ? "is-active" : ""}`}
             >
               Все категории
             </Link>
             {rootCategories.map((category) => (
               <Link
                 key={category.id}
                 href={buildCatalogVariantHref(variant, filters, ui, { category: String(category.id), page: 1 })}
                 className={`market-chip ${String(category.id) === filters.category ? "is-active" : ""}`}
               >
                 {category.name}
               </Link>
             ))}
           </section>
         )}
 
         {variant === "a" ? (
           <div className="market-layout">
             <aside className="market-layout__filters">
               {renderFilterForm(variant, ui, {
                 brand: filters.brand,
                 category: filters.category,
                 series: filters.series,
                 is_new: filters.is_new,
                 is_promo: filters.is_promo,
               }, {
                 hideSearch: true,
                 hideSort: true,
               })}
               <div className="market-filter-group">
                 <span className="market-filter-label">Бренды</span>
                 <div className="market-brand-list">
                   {featuredBrands.map((brand) => (
                     <Link
                       key={brand.id}
                       href={buildCatalogVariantHref(variant, filters, ui, { brand: String(brand.id), page: 1 })}
                       className={`market-chip ${String(brand.id) === filters.brand ? "is-active" : ""}`}
                     >
                       {brand.name}
                     </Link>
                   ))}
                 </div>
               </div>
             </aside>
             <main className="market-layout__results">
               <div className="market-results-header">
                 <div className="market-results-meta">
                   <span>Показано: {sortedProducts.length}</span>
                   <span>Страница: {page}</span>
                 </div>
                 <div className="market-results-tools">
                   <Link
                     href={buildCatalogVariantHref(variant, filters, ui, { view: "grid" })}
                     className={`market-toggle ${ui.view === "grid" ? "is-active" : ""}`}
                   >
                     Сетка
                   </Link>
                   <Link
                     href={buildCatalogVariantHref(variant, filters, ui, { view: "list" })}
                     className={`market-toggle ${ui.view === "list" ? "is-active" : ""}`}
                   >
                     Список
                   </Link>
                 </div>
               </div>
               <section className={`market-product-grid ${ui.view === "list" ? "is-list" : ""}`}>
                 {sortedProducts.map((product) => (
                   <CatalogProductCard
                     key={product.id}
                     product={product}
                     variant="a"
                     csrfToken={session?.session.csrf_token || ""}
                     cartUrl={cartUrl}
                     initialQty={cartMap.get(product.id) || 0}
                   />
                 ))}
               </section>
             </main>
           </div>
         ) : null}
 
         {variant === "b" ? (
           <div className="market-mobile-layout">
             <details className="market-mobile-filters">
               <summary className="market-mobile-filters__summary">Фильтры и сортировка</summary>
               {renderFilterForm(variant, ui, {
                 brand: filters.brand,
                 category: filters.category,
                 series: filters.series,
                 is_new: filters.is_new,
                 is_promo: filters.is_promo,
               }, {
                 hideSearch: true,
               })}
             </details>
             <section className="market-product-list">
               {sortedProducts.map((product) => (
                 <CatalogProductCard
                   key={product.id}
                   product={product}
                   variant="b"
                   csrfToken={session?.session.csrf_token || ""}
                   cartUrl={cartUrl}
                   initialQty={cartMap.get(product.id) || 0}
                 />
               ))}
             </section>
             <div className="market-sticky-cart">
               <Link href={cartUrl} className="market-button market-button--primary">
                 В корзину ({cartCount})
               </Link>
               <span>Быстрый переход после добавлений</span>
             </div>
           </div>
         ) : null}
 
        {variant === "c" ? (
          <div className="market-fast-layout">
            <section className="market-fast-controls">
               <div className="market-fast-row">
                 {grocerySortSegments.map((option) => (
                   <Link
                     key={option.value}
                     href={buildCatalogVariantHref(variant, filters, ui, { sort: option.value })}
                     className={`market-segment ${ui.sort === option.value ? "is-active" : ""}`}
                   >
                     {option.label}
                   </Link>
                 ))}
                 <details className="market-sort-more">
                   <summary>Ещё</summary>
                   <div className="market-sort-more__menu">
                     {sortOptions
                       .filter((option) => !grocerySortSegments.some((segment) => segment.value === option.value))
                       .map((option) => (
                         <Link
                           key={option.value}
                           href={buildCatalogVariantHref(variant, filters, ui, { sort: option.value })}
                           className={`market-sort-more__item ${ui.sort === option.value ? "is-active" : ""}`}
                         >
                           {option.label}
                         </Link>
                       ))}
                   </div>
                 </details>
               </div>
               <div className="market-fast-row">
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { availability: "in_stock", page: 1 })}
                   className={`market-chip ${ui.availability === "in_stock" ? "is-active" : ""}`}
                 >
                   В наличии
                 </Link>
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { is_promo: "true", page: 1 })}
                   className={`market-chip ${filters.is_promo ? "is-active" : ""}`}
                 >
                   Скидки
                 </Link>
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { price_max: "500", page: 1 })}
                   className={`market-chip ${ui.price_max === "500" ? "is-active" : ""}`}
                 >
                   Цена
                 </Link>
                 <Link
                   href={buildCatalogVariantHref(variant, filters, ui, { rating: "4plus", page: 1 })}
                   className={`market-chip ${ui.rating === "4plus" ? "is-active" : ""}`}
                 >
                   4+
                 </Link>
                 <details className="market-filters-advanced">
                   <summary>Фильтры</summary>
                  <div className="market-filters-advanced__sheet">
                    {renderFilterForm(variant, ui, {
                      brand: filters.brand,
                      category: filters.category,
                      series: filters.series,
                      is_new: filters.is_new,
                      is_promo: filters.is_promo,
                    }, {
                      hideSearch: true,
                      hideSort: true,
                    })}
                  </div>
                </details>
              </div>
            </section>
             <section className="market-product-list market-product-list--dense">
               {sortedProducts.map((product) => (
                 <CatalogProductCard
                   key={product.id}
                   product={product}
                   variant="c"
                   csrfToken={session?.session.csrf_token || ""}
                   cartUrl={cartUrl}
                   initialQty={cartMap.get(product.id) || 0}
                 />
               ))}
             </section>
             <div className="market-sticky-cart">
               <Link href={cartUrl} className="market-button market-button--primary">
                 Перейти в корзину ({cartCount})
               </Link>
               <span>Быстрый выбор без лишних экранов</span>
             </div>
          </div>
        ) : null}

        {variant === "d" ? (
          <div className="market-d-layout">
            <div className="market-d-shell">
              <nav className="market-d-rail" aria-label="Отделы">
                <Link
                  href={buildCatalogVariantHref(variant, filters, ui, { category: "", page: 1 })}
                  className={`market-chip ${!filters.category ? "is-active" : ""}`}
                >
                  Все
                </Link>
                {rootCategories.map((category) => (
                  <Link
                    key={category.id}
                    href={buildCatalogVariantHref(variant, filters, ui, { category: String(category.id), page: 1 })}
                    className={`market-chip ${String(category.id) === filters.category ? "is-active" : ""}`}
                  >
                    {category.name}
                  </Link>
                ))}
              </nav>
              <div className="market-d-controls">
                <div className="market-fast-row">
                  {grocerySortSegments.map((option) => (
                    <Link
                      key={option.value}
                      href={buildCatalogVariantHref(variant, filters, ui, { sort: option.value })}
                      className={`market-segment ${ui.sort === option.value ? "is-active" : ""}`}
                    >
                      {option.label}
                    </Link>
                  ))}
                  <details className="market-sort-more">
                    <summary>Ещё</summary>
                    <div className="market-sort-more__menu">
                      {sortOptions
                        .filter((option) => !grocerySortSegments.some((segment) => segment.value === option.value))
                        .map((option) => (
                          <Link
                            key={option.value}
                            href={buildCatalogVariantHref(variant, filters, ui, { sort: option.value })}
                            className={`market-sort-more__item ${ui.sort === option.value ? "is-active" : ""}`}
                          >
                            {option.label}
                          </Link>
                        ))}
                    </div>
                  </details>
                </div>
                <div className="market-fast-row market-d-filters">
                  <Link
                    href={buildCatalogVariantHref(variant, filters, ui, {
                      availability: ui.availability === "in_stock" ? "" : "in_stock",
                      page: 1,
                    })}
                    className={`market-chip ${ui.availability === "in_stock" ? "is-active" : ""}`}
                  >
                    В наличии
                  </Link>
                  <Link
                    href={buildCatalogVariantHref(variant, filters, ui, {
                      is_promo: filters.is_promo ? "" : "true",
                      page: 1,
                    })}
                    className={`market-chip ${filters.is_promo ? "is-active" : ""}`}
                  >
                    Скидки
                  </Link>
                  <details className={`market-price-pop ${ui.price_min || ui.price_max ? "is-active" : ""}`}>
                    <summary className="market-chip">Цена</summary>
                    <div className="market-price-pop__panel">
                      <div className="market-price-pop__presets">
                        <Link
                          href={buildCatalogVariantHref(variant, filters, ui, {
                            price_min: "",
                            price_max: "500",
                            page: 1,
                          })}
                          className="market-chip"
                        >
                          до 500
                        </Link>
                        <Link
                          href={buildCatalogVariantHref(variant, filters, ui, {
                            price_min: "500",
                            price_max: "1500",
                            page: 1,
                          })}
                          className="market-chip"
                        >
                          500–1500
                        </Link>
                        <Link
                          href={buildCatalogVariantHref(variant, filters, ui, {
                            price_min: "1500",
                            price_max: "",
                            page: 1,
                          })}
                          className="market-chip"
                        >
                          от 1500
                        </Link>
                      </div>
                      <form action={`/catalog-${variant}`} className="market-price-pop__form">
                        {filters.brand ? <input type="hidden" name="brand" value={filters.brand} /> : null}
                        {filters.category ? <input type="hidden" name="category" value={filters.category} /> : null}
                        {filters.series ? <input type="hidden" name="series" value={filters.series} /> : null}
                        {filters.is_new ? <input type="hidden" name="is_new" value={filters.is_new} /> : null}
                        {filters.is_promo ? <input type="hidden" name="is_promo" value={filters.is_promo} /> : null}
                        {ui.q ? <input type="hidden" name="q" value={ui.q} /> : null}
                        {ui.sort ? <input type="hidden" name="sort" value={ui.sort} /> : null}
                        {ui.availability ? <input type="hidden" name="availability" value={ui.availability} /> : null}
                        {ui.rating ? <input type="hidden" name="rating" value={ui.rating} /> : null}
                        <input type="hidden" name="page" value="1" />
                        <div className="market-range">
                          <input
                            type="number"
                            inputMode="numeric"
                            name="price_min"
                            placeholder="От"
                            defaultValue={ui.price_min}
                            className="market-input"
                          />
                          <input
                            type="number"
                            inputMode="numeric"
                            name="price_max"
                            placeholder="До"
                            defaultValue={ui.price_max}
                            className="market-input"
                          />
                        </div>
                        <div className="market-price-pop__actions">
                          <button type="submit" className="market-button market-button--primary">
                            Применить
                          </button>
                          <Link
                            href={buildCatalogVariantHref(variant, filters, ui, {
                              price_min: "",
                              price_max: "",
                              page: 1,
                            })}
                            className="market-button"
                          >
                            Сбросить
                          </Link>
                        </div>
                      </form>
                    </div>
                  </details>
                  <Link
                    href={buildCatalogVariantHref(variant, filters, ui, {
                      rating: ui.rating === "4plus" ? "" : "4plus",
                      page: 1,
                    })}
                    className={`market-chip ${ui.rating === "4plus" ? "is-active" : ""}`}
                  >
                    4+
                  </Link>
                  <details className="market-filters-advanced">
                    <summary>
                      {activeFilterCount > 0 ? `Фильтры (${activeFilterCount})` : "Фильтры"}
                    </summary>
                    <div className="market-filters-advanced__sheet">
                      {renderFilterForm(
                        variant,
                        ui,
                        {
                          brand: filters.brand,
                          category: filters.category,
                          series: filters.series,
                          is_new: filters.is_new,
                          is_promo: filters.is_promo,
                        },
                        {
                          hideSearch: true,
                          hideSort: true,
                        },
                      )}
                      <div className="market-filter-group">
                        <span className="market-filter-label">Бренды</span>
                        <div className="market-brand-list">
                          {featuredBrands.map((brand) => (
                            <Link
                              key={brand.id}
                              href={buildCatalogVariantHref(variant, filters, ui, { brand: String(brand.id), page: 1 })}
                              className={`market-chip ${String(brand.id) === filters.brand ? "is-active" : ""}`}
                            >
                              {brand.name}
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  </details>
                </div>
              </div>
              <section className="market-product-list market-product-list--dense market-product-list--d">
                {sortedProducts.map((product) => (
                  <CatalogProductCard
                    key={product.id}
                    product={product}
                    variant="d"
                    csrfToken={session?.session.csrf_token || ""}
                    cartUrl={cartUrl}
                    initialQty={cartMap.get(product.id) || 0}
                  />
                ))}
              </section>
            </div>
            {cartCount > 0 ? (
              <div className="market-d-dock" role="region" aria-label="Корзина">
                <div className="market-d-dock__summary">
                  {cartCount} · {cartSubtotal}
                </div>
                <Link href={cartUrl} className="market-button market-button--primary">
                  В корзину
                </Link>
              </div>
            ) : null}
          </div>
        ) : null}
 
         <footer className="market-catalog__footer">
           <div className="market-pagination">
             {filters.page && filters.page > 1 ? (
               <Link
                 href={buildCatalogVariantHref(variant, filters, ui, { page: (filters.page || 1) - 1 })}
                 className="market-button"
               >
                 Предыдущая страница
               </Link>
             ) : null}
             {hasNextPage ? (
               <Link
                 href={buildCatalogVariantHref(variant, filters, ui, { page: (filters.page || 1) + 1 })}
                 className="market-button market-button--primary"
               >
                 Следующая страница
               </Link>
             ) : (
               <span className="market-pagination__end">Вы дошли до конца доступной страницы.</span>
             )}
           </div>
         </footer>
       </div>
     );
   } catch (error) {
     return (
       <section className="market-empty-state">
         <h1>Каталог временно недоступен</h1>
         <p>Не удалось получить данные из backend API. Попробуйте позже.</p>
         <p className="market-error">{String(error instanceof Error ? error.message : error)}</p>
       </section>
     );
   }
 }
