export type HeroMetric = {
  value: string;
  label: string;
};

export type Signal = {
  title: string;
  body: string;
};

export type JourneyCard = {
  eyebrow: string;
  title: string;
  body: string;
  href: string;
  points: string[];
};

export type Principle = {
  title: string;
  body: string;
};

export type HeroShowcase = {
  title: string;
  body: string;
  image: string;
  alt: string;
  featured?: boolean;
};

export type PromoBanner = {
  kicker: string;
  title: string;
  body: string;
  href: string;
  image: string;
  alt: string;
};

export const heroMetrics: HeroMetric[] = [
  { value: "Next live", label: "публичная витрина уже работает отдельным контуром" },
  { value: "SEO-safe", label: "SSR и same-origin delivery остаются частью edge-контура" },
  { value: "Backend core", label: "checkout, auth и orders не уезжают во frontend" },
];

export const heroTrustPoints = [
  "Каталог для ресторанов, кафе, баров и отелей",
  "Поставщики в одном окне",
  "Повторные закупки без ручной рутины",
];

export const heroShowcase: HeroShowcase[] = [
  {
    title: "Операционный каталог",
    body: "От кухни до сервировки и упаковки.",
    image: "/static/shopfront/hero/servio-hero-main.svg",
    alt: "Каталог Servio",
    featured: true,
  },
  {
    title: "Бар и стекло",
    body: "Форматы для винной карты, коктейлей и сервиса.",
    image: "/static/shopfront/hero/servio-hero-bar.svg",
    alt: "Барное направление Servio",
  },
  {
    title: "Сервировка и подача",
    body: "Коллекции для зала, банкетов и room service.",
    image: "/static/shopfront/hero/servio-hero-tableware.svg",
    alt: "Сервировка и подача Servio",
  },
];

export const promoBanners: PromoBanner[] = [
  {
    kicker: "Коллекции",
    title: "Кураторские подборки под конкретный сценарий закупки",
    body: "Подготовили витринный слой для repeat purchase и навигации по рабочим наборам.",
    href: "/collections",
    image: "/static/shopfront/hero/servio-hero-tableware.svg",
    alt: "Коллекции Servio",
  },
  {
    kicker: "Бренды",
    title: "Брендовые витрины без случайного e-commerce шума",
    body: "Отдельные маршруты брендов уже готовы к дальнейшему data-driven наполнению.",
    href: "/brands",
    image: "/static/shopfront/hero/servio-hero-main.svg",
    alt: "Бренды Servio",
  },
  {
    kicker: "Для поставщиков",
    title: "Подключайте ассортимент к Servio",
    body: "Seller wave идёт позже, но narrative и entry points уже живут в новом storefront.",
    href: "/suppliers",
    image: "/static/shopfront/hero/servio-hero-bar.svg",
    alt: "Поставщики Servio",
  },
];

export const operatingSignals: Signal[] = [
  {
    title: "Современная визуальная система",
    body: "Чистая типографика, многослойные поверхности, аккуратное движение и mobile-first rhythm вместо устаревшего шаблонного вида.",
  },
  {
    title: "Поэтапная миграция по маршрутам",
    body: "Публичные страницы уже идут через Next, а transactional-сценарии остаются на стабильном Django-контуре до готовности API bridge.",
  },
  {
    title: "Польза важнее новизны",
    body: "Новая оболочка делает discovery понятнее: меньше визуального шума, яснее CTA и заметнее ключевые направления уже с первого экрана.",
  },
];

export const journeyCards: JourneyCard[] = [
  {
    eyebrow: "Путь покупателя",
    title: "Главная и витрина теперь ощущаются как продукт, а не как набор шаблонов.",
    body: "Новый public storefront делает навигацию короче, текстовые иерархии чище, а ключевые разделы заметнее уже с первого экрана.",
    href: "/buyers",
    points: ["mobile-first первый экран", "читаемые карточки разделов", "быстрый вход в разделы каталога"],
  },
  {
    eyebrow: "Доверие поставщика",
    title: "Поставщикам и брендам показываем более серьёзный marketplace narrative.",
    body: "Мы уводим визуальный язык от случайного e-commerce UI к более сильной B2B/B2C подаче: бренды, коллекции и policy surfaces выглядят спокойнее и дороже.",
    href: "/suppliers",
    points: ["редакционные блоки", "контрастные trust-панели", "лучше плотность информации"],
  },
  {
    eyebrow: "Контентные поверхности",
    title: "Статические и SEO-важные страницы стали частью единой системы.",
    body: "About, FAQ, payment, returns, delivery и contacts теперь живут в одном визуальном ритме и готовы к дальнейшему наполнению данными.",
    href: "/about",
    points: ["единая оболочка", "чёткие section patterns", "готовность к typed content feeds"],
  },
];

export const principles: Principle[] = [
  {
    title: "Сначала public surfaces",
    body: "Мы расширяем новый storefront там, где выигрыш в UX максимальный, а migration risk минимальный.",
  },
  {
    title: "Backend остаётся ядром",
    body: "Бизнес-логика, pricing, checkout, auth и seller workflows не расползаются во frontend и не дублируются.",
  },
  {
    title: "Release-safe rollout",
    body: "Любой срез можно откатить edge-переключателем, не трогая данные и не ломая рабочий backend-контур.",
  },
];
