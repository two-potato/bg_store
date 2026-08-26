"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/account", label: "Главная", meta: "Buyer workspace" },
  { href: "/account/orders", label: "Заказы", meta: "История и статусы" },
  { href: "/account/settings", label: "Настройки", meta: "Профиль и контакты" },
  { href: "/account/preferences", label: "Предпочтения", meta: "Коммуникации" },
  { href: "/account/addresses", label: "Адреса", meta: "Книга доставок" },
  { href: "/account/legal", label: "Компании", meta: "B2B workspace" },
  { href: "/account/notifications", label: "Уведомления", meta: "События" },
  { href: "/account/favorites", label: "Избранное", meta: "Buyer shortlist" },
  { href: "/account/lists", label: "Списки закупки", meta: "Procurement lists" },
  { href: "/account/saved-searches", label: "Сохранённые поиски", meta: "Фильтры каталога" },
  { href: "/cart", label: "Корзина", meta: "Purchase flow" },
];

function isActive(pathname: string, href: string) {
  if (href === "/account") {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AccountNav() {
  const pathname = usePathname();

  return (
    <nav className="servio-account-nav" aria-label="Навигация buyer account">
      <div className="servio-account-nav__group">
        <span className="servio-account-nav__title">Buyer surfaces</span>
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`servio-account-nav__link ${isActive(pathname, item.href) ? "is-active" : ""}`}
          >
            <strong>{item.label}</strong>
            <span>{item.meta}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
