import type { MarketingSection } from "@/components/page-sections";

export type MarketingMetric = {
  value: string;
  label: string;
};

export type MarketingLink = {
  href: string;
  label: string;
  caption: string;
};

export type MarketingPage = {
  slug: string;
  title: string;
  description: string;
  eyebrow: string;
  lead: string;
  intro: string;
  notice: string;
  metrics: MarketingMetric[];
  sections: MarketingSection[];
  related: MarketingLink[];
};

export const marketingPages: Record<string, MarketingPage> = {
  about: {
    slug: "about",
    title: "О платформе Servio",
    description:
      "Servio — маркетплейс HoReCa-поставок с новым public storefront на Next.js App Router и backend-first архитектурой.",
    eyebrow: "Marketplace narrative",
    lead: "Новый storefront ощущается как продуктовая витрина, а не как технический переходный слой.",
    intro:
      "Эта страница показывает, как Servio меняет визуальный язык и public UX, не перенося критическую доменную логику из Django в браузерный фронт.",
    notice:
      "Мы сознательно не переписываем работающий backend вслепую. В новую оболочку переезжают public SSR-surfaces, а transaction flows остаются на стабильном серверном ядре.",
    metrics: [
      { value: "SSR-first", label: "SEO и контентные страницы уже работают в новом рендер-контуре" },
      { value: "Safe rollout", label: "switch через nginx без data rewrite и без CORS-лабиринта" },
      { value: "Backend kept", label: "auth, pricing, orders и checkout остаются серверными" },
    ],
    sections: [
      {
        tag: "Foundation",
        title: "Что уже работает",
        body: "Каркас App Router, единый shell, runtime health endpoint и route-by-route rollout через nginx уже соединены в один public storefront layer.",
        points: [
          "same-origin delivery без CORS-разрастания",
          "роллаут по allowlist маршрутов",
          "rollback на уровне edge-конфига",
        ],
        emphasis: "Новый visual layer уже можно развивать независимо от HTML templates, не трогая backend-ядро.",
      },
      {
        tag: "Architecture",
        title: "Что остаётся на backend",
        body: "Django/DRF остаются source of truth для бизнес-логики, SEO-ядра, auth, orders, checkout и seller-domain.",
        emphasis: "Next управляет опытом и delivery, но не дублирует domain-решения.",
      },
    ],
    related: [
      { href: "/buyers", label: "Buyer UX wave", caption: "Как мы улучшаем discovery, readability и mobile rhythm." },
      { href: "/brands", label: "Discovery routes", caption: "Какие витринные поверхности уже готовы к Next rollout." },
      { href: "/faq", label: "Support content", caption: "Как content-heavy surfaces становятся частью единой системы." },
    ],
  },
  buyers: {
    slug: "buyers",
    title: "Для покупателей",
    description: "Покупательский контур Servio в новой storefront-архитектуре.",
    eyebrow: "Buyer journey",
    lead: "Public discovery ускоряется раньше, чем account и checkout, чтобы улучшение было заметно сразу.",
    intro:
      "Foundation готовит buyer-facing surfaces к более быстрому каталогу, более чистому PDP и предсказуемому mobile-first discovery без переноса бизнес-правил во frontend.",
    notice:
      "Buyer account и checkout специально не мигрируются первыми: сначала стабилизируем public discovery и контракты.",
    metrics: [
      { value: "Cleaner IA", label: "основные buyer routes становятся короче и понятнее визуально" },
      { value: "Mobile-first", label: "главные блоки уже проектируются от малого экрана вверх" },
      { value: "Search next", label: "следующая большая волна идёт в catalog и search surfaces" },
    ],
    sections: [
      {
        tag: "Priority",
        title: "Что улучшаем первым",
        body: "Home, catalog и публичные category, brand и collection surfaces дают максимум UX-эффекта при минимальном migration risk.",
        emphasis: "Покупатель сначала должен быстрее понимать, куда идти и что можно купить, а уже потом получать новый account-shell.",
      },
      {
        tag: "Quality gate",
        title: "Что проверяем",
        body: "SEO parity, mobile navigation, search discoverability, page speed, корректность metadata и analytics parity.",
      },
    ],
    related: [
      { href: "/collections", label: "Collections", caption: "Кураторские подборки как более лёгкий вход в ассортимент." },
      { href: "/brands", label: "Brands", caption: "Брендовая навигация как discovery layer новой витрины." },
      { href: "/payment", label: "Payment info", caption: "Информационные страницы тоже держат buyer confidence." },
    ],
  },
  suppliers: {
    slug: "suppliers",
    title: "Для поставщиков",
    description: "Поставщики остаются в безопасной seller-wave и не вовлекаются в ранний rollout storefront.",
    eyebrow: "Seller-safe rollout",
    lead: "Seller surfaces не должны стать жертвой раннего UI rewrite.",
    intro:
      "Seller-сценарии сознательно выведены в последнюю волну, потому что seller cabinet, offers, inventories и OMS-похожие контуры слишком критичны для раннего UI rewrite.",
    notice:
      "Новый storefront не должен ломать seller flows ради скорости migration. Сначала contracts, потом surfaces.",
    metrics: [
      { value: "Later wave", label: "seller cabinet и operations идут отдельным треком" },
      { value: "Contract-first", label: "сначала API discipline, затем новый UI" },
      { value: "No blind rewrite", label: "operational surfaces не переписываются без rollback path" },
    ],
    sections: [
      {
        tag: "Risk control",
        title: "Почему seller идёт последним",
        body: "HTML cabinet пока не имеет полного API-покрытия, а operational UX не прощает полуготовых bridge-решений.",
      },
      {
        tag: "Preparation",
        title: "Что готовим заранее",
        body: "Отдельный seller API track, release gates, observability и rollback-safe path switching.",
        emphasis: "Это позволяет сохранить доверие продавцов и не ломать операционный ритм marketplace.",
      },
    ],
    related: [
      { href: "/about", label: "Migration logic", caption: "Почему миграция идёт волнами, а не одним broad rewrite." },
      { href: "/promotions", label: "Merchandising layer", caption: "Что можно улучшать визуально без вмешательства в seller ops." },
      { href: "/contacts", label: "Contact surface", caption: "Какие bridge-точки полезны до seller API wave." },
    ],
  },
  delivery: {
    slug: "delivery",
    title: "Доставка и логистика",
    description: "Страница логистики в новом storefront.",
    eyebrow: "Static SSR wave",
    lead: "Сначала обновляем доверие и читаемость на public policy surfaces.",
    intro:
      "Delivery — хороший кандидат для первой публичной волны: индексируемая страница, low-risk surface и быстрый способ проверить metadata, layout и runtime routing на новом storefront.",
    notice:
      "Сами delivery rules, address logic и checkout delivery choices остаются на backend и не переезжают в эту волну.",
    metrics: [
      { value: "Policy surface", label: "легко проверяется на SEO, layout и route parity" },
      { value: "Low risk", label: "нет buyer-session зависимости и нет payment coupling" },
      { value: "Fast rollout", label: "идеальный кандидат для раннего Next delivery" },
    ],
    sections: [
      {
        tag: "Rollout",
        title: "Зачем переносить рано",
        body: "Это быстрый route-parity smoke для статических публичных страниц и хороший объект для first contentful rollout.",
      },
      {
        tag: "Boundary",
        title: "Что не трогаем",
        body: "Pickup, courier rules, address validation, reverse geocode и order submission остаются в Django и DRF до checkout wave.",
      },
    ],
    related: [
      { href: "/payment", label: "Оплата", caption: "Соседняя public surface, важная для buyer confidence." },
      { href: "/returns", label: "Возвраты", caption: "Policy pages должны работать в одном визуальном ритме." },
      { href: "/faq", label: "FAQ", caption: "Контентные ответы без вмешательства в transaction слой." },
    ],
  },
  payment: {
    slug: "payment",
    title: "Оплата",
    description: "Публичная payment surface в новом storefront.",
    eyebrow: "Public info surface",
    lead: "Информационная прозрачность важна не меньше самого checkout UI.",
    intro:
      "Payment page безопасна для раннего переноса как информационная страница. При этом платёжные сценарии и payment bootstrap остаются в backend checkout-ядре.",
    notice: "Fake payment, online payment event flows и guest payment pages пока не участвуют в rollout.",
    metrics: [
      { value: "Trust layer", label: "помогает укрепить buyer confidence до checkout wave" },
      { value: "Backend payment", label: "transport и payment status остаются в серверном контуре" },
      { value: "SEO-safe", label: "indexable страница без риска сломать бизнес-операции" },
    ],
    sections: [
      {
        tag: "Now",
        title: "Что готовим",
        body: "Чистую SEO-indexable страницу с новой shell-моделью и без разрыва analytics-пайплайна.",
      },
      {
        tag: "Later",
        title: "Что блокирует payment wave",
        body: "Полноценный checkout contract, guest access rules и payment status transport.",
      },
    ],
    related: [
      { href: "/delivery", label: "Delivery", caption: "Публичная логистическая информация в том же buyer trust layer." },
      { href: "/returns", label: "Returns", caption: "Политики возврата должны быть столь же прозрачны, как способы оплаты." },
      { href: "/contacts", label: "Contacts", caption: "Канал связи остаётся важен для дореформенного support path." },
    ],
  },
  returns: {
    slug: "returns",
    title: "Возврат и обмен",
    description: "Публичная legal page для Next storefront.",
    eyebrow: "Policy content",
    lead: "Policy content должен выглядеть так же уверенно, как и коммерческие поверхности.",
    intro:
      "Возвраты и policy content подходят для первой волны, потому что их можно безопасно перевести на новый runtime без изменения order-domain.",
    notice: "Claims, support tickets и order problem resolution остаются buyer-account backend flow.",
    metrics: [
      { value: "Legal clarity", label: "чёткая policy-коммуникация усиливает доверие к маркетплейсу" },
      { value: "No order rewrite", label: "споры и claims не переезжают без buyer API слоя" },
      { value: "Unified shell", label: "контентные страницы больше не выглядят чужеродно" },
    ],
    sections: [
      {
        tag: "Scope",
        title: "Что переносим",
        body: "Только публичный policy-content слой, metadata и layout.",
      },
      {
        tag: "Boundary",
        title: "Что остаётся в старом контуре",
        body: "Создание claims, support и order dispute operations.",
      },
    ],
    related: [
      { href: "/payment", label: "Payment", caption: "Покупателю важно видеть и оплату, и правила возврата в одном quality bar." },
      { href: "/faq", label: "FAQ", caption: "Частые вопросы усиливают policy content без перегруза UI." },
      { href: "/about", label: "О платформе", caption: "Контекст и доверие бренду поддерживают policy-reading journey." },
    ],
  },
  contacts: {
    slug: "contacts",
    title: "Контакты Servio",
    description: "Контакты и заявка связи в новом storefront-контуре.",
    eyebrow: "Contact surface",
    lead: "Даже форма контакта не должна выглядеть второстепенной или случайной.",
    intro:
      "Contacts — borderline surface: как страница она подходит для первой волны, а как форма требует аккуратного backend bridge. Поэтому новый storefront закладывает route и shell, но не переписывает server-side submission.",
    notice:
      "Форма заявки остаётся backend-first до тех пор, пока не будет явного typed transport для browser submission и errors.",
    metrics: [
      { value: "Bridge route", label: "публичный контент уже на Next, submission остаётся серверным" },
      { value: "UX-safe", label: "нет ложной интерактивности и нет выдуманных API" },
      { value: "Clear escalation", label: "surface готова к будущему typed form flow" },
    ],
    sections: [
      {
        tag: "Immediate",
        title: "Что можно включить быстро",
        body: "Контент, metadata, навигацию и page shell.",
      },
      {
        tag: "Next step",
        title: "Что переносим позже",
        body: "Форму, success и error states, а также аналитические события формы после явного API-решения.",
      },
    ],
    related: [
      { href: "/faq", label: "FAQ", caption: "Часть обращений должна закрываться до контакта через ясный self-service." },
      { href: "/about", label: "О платформе", caption: "Контакты сильнее работают в связке с понятной платформенной историей." },
      { href: "/payment", label: "Payment trust", caption: "Информационные страницы вместе формируют buyer confidence." },
    ],
  },
  faq: {
    slug: "faq",
    title: "FAQ",
    description: "FAQ-поверхность для раннего Next.js rollout.",
    eyebrow: "Support content",
    lead: "Поддержка начинается с понятной структуры информации, а не только с формы обращения.",
    intro:
      "FAQ — хороший low-risk surface для route parity и SSR-проверки. Он помогает проверить shell, scroll behavior и metadata без вмешательства в transaction flows.",
    notice: "Interactive support tooling и account-driven support scenarios остаются в Django.",
    metrics: [
      { value: "Low-risk route", label: "идеально подходит для раннего переключения на Next" },
      { value: "Readable content", label: "новый layout упрощает длинные информационные блоки" },
      { value: "A11y-first", label: "типографика и spacing ориентированы на реальную читаемость" },
    ],
    sections: [
      {
        tag: "Why now",
        title: "Для чего эта страница нужна сейчас",
        body: "Для быстрой проверки SSR, caching headers, robots и canonical parity, а также общей визуальной дисциплины нового storefront.",
      },
      {
        tag: "UX",
        title: "UX-фокус",
        body: "Читаемость, mobile typography, правильный page rhythm и отсутствие лишней клиентской перегрузки.",
      },
    ],
    related: [
      { href: "/contacts", label: "Contacts", caption: "Что делать, когда self-service всё же не закрывает вопрос." },
      { href: "/delivery", label: "Delivery", caption: "Один из ключевых buyer question clusters для FAQ." },
      { href: "/returns", label: "Returns", caption: "Policy sections и FAQ должны говорить на одном языке." },
    ],
  },
  brands: {
    slug: "brands",
    title: "Бренды",
    description: "Публичный directory layer для будущей migration wave брендов.",
    eyebrow: "Discovery directory",
    lead: "Brand browsing должен быть ближе к curated discovery, чем к голому списку ссылок.",
    intro:
      "Brands — один из лучших кандидатов для ранней discovery-волны. Это индексируемая структура, которая почти не зависит от buyer session и даёт понятный UX signal о новом storefront.",
    notice:
      "Brand detail pages и catalog filters будут подключаться отдельным backend contract layer поверх существующих shopfront services.",
    metrics: [
      { value: "Indexable", label: "отличный SEO-candidate для early Next rollout" },
      { value: "Discovery-first", label: "не зависит от checkout и session-critical сценариев" },
      { value: "Ready for API", label: "следующий шаг — typed directory feeds и filters" },
    ],
    sections: [
      {
        tag: "Why early",
        title: "Почему brands идут рано",
        body: "Они помогают проверить route switching, information architecture и directory-style layouts без cart и checkout complexity.",
      },
      {
        tag: "Next wave",
        title: "Что дальше",
        body: "Следом за directory surfaces пойдут category, collection и search-heavy discovery pages.",
      },
    ],
    related: [
      { href: "/collections", label: "Collections", caption: "Редакционные подборки помогают раскрыть брендовые маршруты." },
      { href: "/promotions", label: "Promotions", caption: "Merchandising layer дополняет directory surfaces." },
      { href: "/buyers", label: "Buyer UX", caption: "Зачем бренды важны для более короткого discovery path." },
    ],
  },
  collections: {
    slug: "collections",
    title: "Коллекции",
    description: "Коллекции как early discovery surface нового storefront.",
    eyebrow: "Curated discovery",
    lead: "Curated merchandising даёт витрине характер и быстрее ведёт к нужному контексту покупки.",
    intro:
      "Collections позволяют отработать curator-style discovery blocks, карточки и SSR routing без вмешательства в transaction ядро.",
    notice:
      "Collection detail pages, рекомендации и recovery-блоки будут подключаться только после typed storefront contracts.",
    metrics: [
      { value: "Curated UI", label: "витрина становится более редакционной и запоминающейся" },
      { value: "Card system", label: "на коллекциях отрабатывается язык карточек и секций" },
      { value: "Recommendation-ready", label: "следующий этап — данные и recommendation surfaces" },
    ],
    sections: [
      {
        tag: "Validation",
        title: "Что проверяем этой волной",
        body: "Grid rhythm, card language, metadata, mobile cards и route-level observability.",
      },
      {
        tag: "Discipline",
        title: "Чего не делаем",
        body: "Не тянем recommendation logic во frontend и не дублируем backend ranking внутри клиента.",
      },
    ],
    related: [
      { href: "/brands", label: "Brands", caption: "Collections и brands формируют общий discovery mesh." },
      { href: "/promotions", label: "Promotions", caption: "Кураторские и промо surfaces должны быть связаны визуально." },
      { href: "/blog", label: "Blog", caption: "Контентная редактура поддерживает curated витрину." },
    ],
  },
  promotions: {
    slug: "promotions",
    title: "Промо и предложения",
    description: "Промо-контур раннего публичного rollout.",
    eyebrow: "Merchandising surface",
    lead: "Промо должно ощущаться частью единой системы, а не набором случайных баннеров.",
    intro:
      "Promotions подходят для первой волны как merchandising surface: можно аккуратно запустить новый visual layer, не затрагивая купоны, скидки и checkout pricing logic.",
    notice: "Discounting, coupon resolution и pricing remain backend-only.",
    metrics: [
      { value: "Visual merchandising", label: "новый storefront усиливает промо без хаоса и visual noise" },
      { value: "Pricing stays server-side", label: "скидки и order totals не уезжают во frontend" },
      { value: "Campaign-ready", label: "surface готова к будущим merchandising API" },
    ],
    sections: [
      {
        tag: "Now",
        title: "Что переносим",
        body: "Публичный merchandising layer, статические блоки, SSR-маршрут и metadata.",
      },
      {
        tag: "Backend guardrail",
        title: "Что остаётся на месте",
        body: "Все реальные discount rules, order totals и checkout coupon validation.",
      },
    ],
    related: [
      { href: "/collections", label: "Collections", caption: "Продуманная кураторская витрина усиливает промо-слой." },
      { href: "/brands", label: "Brands", caption: "Промо должно поддерживать brand discovery, а не спорить с ним." },
      { href: "/buyers", label: "Buyer routes", caption: "Как промо встраивается в основной buyer journey." },
    ],
  },
  blog: {
    slug: "blog",
    title: "Блог",
    description: "Контентный блоговый маршрут для раннего SSR rollout.",
    eyebrow: "Content route",
    lead: "Контентный слой помогает storefront выглядеть как бренд, а не как сухой каталог.",
    intro:
      "Blog — это контентный SSR-полигон для новой storefront-платформы: идеален для SEO parity, routing checks и контроля page performance.",
    notice: "Полноценный CMS-пайплайн сюда не внедряется; текущая задача — foundation и route ownership.",
    metrics: [
      { value: "SEO proving ground", label: "контентные маршруты быстрее всего показывают parity нового контура" },
      { value: "Brand layer", label: "редакционный контент усиливает marketplace identity" },
      { value: "Performance visible", label: "контентные страницы хорошо показывают TTFB и rendering discipline" },
    ],
    sections: [
      {
        tag: "Value",
        title: "Почему это важно",
        body: "Контентные страницы быстро показывают, что новый App Router слой совместим с текущей SEO-моделью и edge delivery.",
      },
      {
        tag: "Control",
        title: "Что держим под контролем",
        body: "Metadata, canonical, robots, structured content rhythm и мгновенный rollback на Django.",
      },
    ],
    related: [
      { href: "/about", label: "О платформе", caption: "Брендовый рассказ должен поддерживаться и контентом, и витриной." },
      { href: "/brands", label: "Brands", caption: "Редакционный контент помогает лучше раскрывать брендовые направления." },
      { href: "/collections", label: "Collections", caption: "Контент и curated discovery работают сильнее вместе." },
    ],
  },
};

export const marketingPageSlugs = Object.keys(marketingPages);
