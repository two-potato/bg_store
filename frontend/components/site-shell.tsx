import Link from "next/link";
import type { PropsWithChildren } from "react";

const navItems = [
  { href: "/catalog", label: "Каталог", featured: true },
  { href: "/brands", label: "Бренды" },
  { href: "/collections", label: "Коллекции" },
  { href: "/promotions", label: "Спецпредложения" },
  { href: "/buyers", label: "Покупателям" },
  { href: "/suppliers", label: "Поставщикам" },
  { href: "/delivery", label: "Доставка" },
  { href: "/faq", label: "FAQ" },
];

export function SiteShell({ children }: PropsWithChildren) {
  return (
    <div className="servio-frame">
      <div className="servio-shell">
        <a href="#content" className="servio-skip-link">
          Перейти к содержимому
        </a>

        <header className="servio-header">
          <div className="servio-header__toprow">
            <Link href="/" className="servio-brand" aria-label="Servio marketplace storefront">
              <picture>
                <source
                  media="(max-width: 720px)"
                  srcSet="/static/shopfront/big_logo_mobile.png?v=20260307-1"
                />
                <img
                  src="/static/shopfront/big_logo.png?v=20260307-5"
                  alt="Servio"
                  className="servio-brand__logo"
                />
              </picture>
            </Link>

            <form action="/search/" role="search" className="servio-header__search">
              <input
                type="search"
                name="q"
                placeholder="Поиск по каталогу HoReCa"
                className="servio-header__search-input"
                aria-label="Поиск по каталогу HoReCa"
              />
              <button type="submit" className="servio-header__search-btn">
                Найти
              </button>
            </form>

            <div className="servio-header__utility">
              <Link href="/account" className="servio-header__utility-link">
                Кабинет
              </Link>
              <Link href="/account/favorites" className="servio-header__utility-link">
                Избранное
              </Link>
              <Link href="/account/lists" className="servio-header__utility-link">
                Списки
              </Link>
              <Link href="/account/saved-searches" className="servio-header__utility-link">
                Поиски
              </Link>
              <Link
                href="/cart"
                className="servio-header__utility-link servio-header__utility-link--accent"
              >
                Корзина
              </Link>
            </div>
          </div>

          <div className="servio-header__cluster">
            <nav className="servio-nav" aria-label="Основная навигация публичного storefront">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`servio-nav__link ${item.featured ? "servio-nav__link--featured" : ""}`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="servio-header__actions">
              <Link href="/about" className="servio-button servio-button--ghost">
                О платформе
              </Link>
              <Link href="/contacts" className="servio-button servio-button--secondary">
                Контакты
              </Link>
            </div>
          </div>

        </header>

        <main id="content" className="servio-main">
          {children}
        </main>

        <footer className="servio-footer">
          <div className="servio-footer__block">
            <span className="servio-footer__title">Servio</span>
            <span>Профессиональные товары для HoReCa: посуда, стекло, барный инвентарь, упаковка, текстиль и расходные материалы.</span>
          </div>
          <div className="servio-footer__block">
            <span className="servio-footer__title">Каталог</span>
            <span>Бренды, коллекции, спецпредложения, категории и карточки товаров — всё в одном месте.</span>
          </div>
          <div className="servio-footer__block">
            <span className="servio-footer__title">Покупателям и поставщикам</span>
            <span>Удобная закупка, прозрачные условия, поддержка регулярных поставок и корпоративных заказов.</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
