import { headers } from "next/headers";

import { backendBridgeUrl } from "@/lib/storefront-bridge";

export class BridgeApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "BridgeApiError";
    this.status = status;
    this.payload = payload;
  }
}

export type BridgeUser = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  phone: string;
  contact_email: string;
  role: string | null;
  discount: string;
  seller_store: {
    id: number | null;
    name: string;
    slug: string;
  };
  telegram: {
    id: number | null;
    username: string;
    linked: boolean;
  };
};

export type BridgeSessionBootstrap = {
  ok: boolean;
  session: {
    authenticated: boolean;
    session_key: string;
    csrf_token: string;
  };
  user: BridgeUser | null;
  cart_badge: {
    count: number;
    subtotal: string;
  };
  urls: {
    login: string;
    logout: string;
    account: string;
    cart: string;
  };
};

export type BridgeCartLineItem = {
  product: {
    id: number;
    slug: string;
    name: string;
    sku: string;
    brand: string;
    category: string;
    image_url: string;
    price: string;
    stock_qty: number;
    min_order_qty: number;
  };
  qty: number;
  row_total: string;
  seller: {
    id: number | null;
    name: string;
    slug: string;
  };
};

export type BridgeCartGroup = {
  title: string;
  slug: string;
  subtotal: string;
  items: BridgeCartLineItem[];
};

export type BridgeCartSnapshot = {
  items: BridgeCartLineItem[];
  seller_groups: BridgeCartGroup[];
  seller_count: number;
  cart_count: number;
  is_empty: boolean;
  subtotal: string;
  discount_percent: string;
  discount_amount: string;
  coupon_discount_amount: string;
  profile_discount_amount: string;
  total: string;
  coupon: {
    code: string;
    validation_error: string;
  };
};

export type BridgeCartResponse = {
  ok: boolean;
  cart: BridgeCartSnapshot;
};

export type BridgeOrderShort = {
  id: number;
  status: string;
  status_display: string;
  approval_status: string;
  approval_status_display: string;
  payment_method: string;
  delivery_method: string;
  subtotal: string;
  discount_amount: string;
  total: string;
  created_at: string;
  updated_at: string;
  legal_entity: {
    id: number | null;
    name: string;
  };
  detail_url: string;
};

export type BridgeAccountBootstrap = {
  ok: boolean;
  user: BridgeUser;
  profile: {
    id: number;
    photo_url: string;
    role: string | null;
  };
  metrics: {
    orders_count: number;
    favorites_count: number;
    saved_searches_count: number;
    entities_count: number;
    addresses_count: number;
  };
  queues: {
    recent_orders: BridgeOrderShort[];
    unpaid_orders: BridgeOrderShort[];
  };
  links: {
    orders: string;
    addresses: string;
    legal: string;
    notifications: string;
    preferences: string;
  };
};

export type BridgeOrderDetail = {
  id: number;
  status: string;
  status_display: string;
  split_status: string;
  split_status_display: string;
  approval_status: string;
  approval_status_display: string;
  customer_type: string;
  customer_type_display: string;
  payment_method: string;
  payment_method_display: string;
  delivery_method: string;
  delivery_method_display: string;
  subtotal: string;
  discount_amount: string;
  total: string;
  customer_comment: string;
  coupon_code: string;
  source_channel: string;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  approved_by: {
    id: number | null;
    username: string;
  };
  placed_by: {
    id: number | null;
    username: string;
  };
  legal_entity: {
    id: number | null;
    name: string;
  };
  delivery_address: {
    id: number | null;
    label: string;
    city: string;
    street: string;
    postcode: string;
  };
  items: Array<{
    id: number;
    product_id: number;
    name: string;
    qty: number;
    canceled_qty: number;
    active_qty: number;
    price: string;
    row_total: string;
    seller_offer_id: number | null;
    product: {
      id: number;
      slug: string;
      name: string;
      sku: string;
      image_url: string;
    };
  }>;
  seller_splits: Array<{
    id: number;
    seller_id: number;
    seller_name: string;
    seller_store_name: string;
    items_count: number;
    subtotal: string;
    status: string;
    status_display: string;
  }>;
  approval: {
    required_count: number;
    approved_count: number;
    can_approve: boolean;
    policy: {
      enabled: boolean;
      require_comment: boolean;
      required_approvals_count: number;
      max_pending_hours: number;
    };
    logs: Array<{
      id: number;
      actor_id: number;
      actor_username: string;
      decision: string;
      decision_display: string;
      comment: string;
      created_at: string;
    }>;
  };
  tracking: {
    available: boolean;
    shipments: Array<{
      id: number;
      seller_order_id: number;
      seller_id: number;
      seller_name: string;
      seller_store_name: string;
      tracking_number: string;
      delivery_method: string;
      warehouse_name: string;
      status: string;
      status_display: string;
      packed_at: string | null;
      shipped_at: string | null;
      delivered_at: string | null;
    }>;
    tracking_url: string;
  };
  payment: {
    demo_enabled: boolean;
    can_retry: boolean;
    retry_url: string;
    invoice_url: string;
    fake_payment: {
      provider_payment_id: string;
      status: string;
      status_display: string;
      last_event: string;
      amount: string;
    };
  };
  support: {
    claims_count: number;
    open_claims_count: number;
    support_tickets_count: number;
    open_support_tickets_count: number;
    claims: Array<{
      id: number;
      claim_type: string;
      claim_type_display: string;
      status: string;
      status_display: string;
      message: string;
      seller_response: string;
      resolution_comment: string;
      created_by_username: string;
      responded_by_username: string;
      created_at: string;
      updated_at: string;
    }>;
    support_tickets: Array<{
      id: number;
      topic: string;
      topic_display: string;
      status: string;
      status_display: string;
      subject: string;
      message: string;
      resolution_comment: string;
      created_by_username: string;
      created_at: string;
      updated_at: string;
    }>;
  };
  timeline: Array<{
    key: string;
    title: string;
    state: "done" | "pending" | "issue";
    label: string;
    timestamp: string | null;
  }>;
  actions: {
    can_reorder: boolean;
    can_cancel: boolean;
    reorder_url: string;
    legacy_detail_url: string;
  };
};

export type BridgeOrderDetailResponse = {
  ok: boolean;
  order: BridgeOrderDetail;
};

export type BridgeOrderReorderResponse = {
  ok: boolean;
  reorder: {
    order_id: number;
    result_type: "full" | "partial" | "none";
    summary: {
      requested_lines: number;
      added_lines: number;
      adjusted_lines: number;
      unavailable_lines: number;
      total_requested_qty: number;
      total_added_qty: number;
    };
    added: Array<{
      product_id: number;
      product_name: string;
      requested_qty: number;
      added_qty: number;
      cart_qty: number;
    }>;
    adjusted: Array<{
      product_id: number;
      product_name: string;
      requested_qty: number;
      added_qty: number;
      cart_qty: number;
      reason: string;
    }>;
    unavailable: Array<{
      product_id: number;
      product_name: string;
      requested_qty: number;
      reason: string;
    }>;
    cart_url: string;
  };
  cart: BridgeCartSnapshot;
};

export type BridgeValidationErrorPayload = {
  ok: false;
  error: string;
  fields?: Record<string, string[]>;
  non_field_errors?: string[];
};

export type BridgeAccountSettings = {
  full_name: string;
  contact_email: string;
  phone: string;
  photo_url: string;
  username: string;
  email: string;
  role: string | null;
  discount: string;
  telegram: {
    id: number | null;
    username: string;
    linked: boolean;
  };
};

export type BridgeAccountSettingsResponse = {
  ok: boolean;
  settings: BridgeAccountSettings;
};

export type BridgeAccountPreferences = {
  notify_email_orders: boolean;
  notify_email_marketing: boolean;
  notify_telegram_orders: boolean;
  notify_telegram_marketing: boolean;
  telegram_linked: boolean;
};

export type BridgeAccountPreferencesResponse = {
  ok: boolean;
  preferences: BridgeAccountPreferences;
};

export type BridgeAccountAddress = {
  id: number;
  legal_entity: {
    id: number;
    name: string;
  };
  label: string;
  country: string;
  city: string;
  street: string;
  postcode: string;
  details: string;
  latitude: number | null;
  longitude: number | null;
  is_default: boolean;
  updated_at: string;
};

export type BridgeAccountAddressesResponse = {
  ok: boolean;
  addresses: BridgeAccountAddress[];
};

export type BridgeAccountAddressResponse = {
  ok: boolean;
  address: BridgeAccountAddress;
};

export type BridgeAccountLegalEntityResponse = {
  ok: boolean;
  memberships: Array<{
    id: number;
    legal_entity: {
      id: number;
      name: string;
      inn: string;
      bik: string;
      checking_account: string;
      bank_name: string;
    };
    role: {
      code: string;
      name: string;
    };
  }>;
  company_workspaces: Array<{
    company_id: number;
    display_name: string;
    legal_entity_id: number;
    membership_role: string;
    approval_policy: {
      enabled: boolean;
      auto_approve_below: string;
      required_approvals_count: number;
      require_comment: boolean;
    };
  }>;
  creation_requests: Array<{
    id: number;
    name: string;
    inn: string;
    bik: string;
    checking_account: string;
    bank_name: string;
    status: {
      code: string;
      name: string;
    };
    created_at: string;
  }>;
};

export type BridgeAccountNotificationsResponse = {
  ok: boolean;
  notifications: Array<{
    at: string;
    title: string;
    subtitle: string;
    href: string;
  }>;
};

export type BridgeToolProduct = {
  id: number;
  slug: string;
  sku: string;
  name: string;
  image_url: string;
  price: string;
  stock_qty: number;
  min_order_qty: number;
  brand_name: string;
  qty?: number;
  item_id?: number;
};

export type BridgeFavoritesResponse = {
  ok: boolean;
  favorites: BridgeToolProduct[];
  counts: {
    favorites: number;
    saved_lists: number;
  };
};

export type BridgeFavoriteToggleResponse = {
  ok: boolean;
  favorited: boolean;
  product_id: number;
};

export type BridgeSavedListSummary = {
  id: number;
  name: string;
  description: string;
  source: string;
  is_public: boolean;
  share_token: string;
  items_count: number;
  updated_at: string;
};

export type BridgeSavedListsResponse = {
  ok: boolean;
  saved_lists: BridgeSavedListSummary[];
};

export type BridgeSavedListCreateResponse = {
  ok: boolean;
  saved_list: {
    id: number;
    name: string;
    description: string;
    source: string;
    is_public: boolean;
    share_token: string;
  };
};

export type BridgeSavedListDetailResponse = {
  ok: boolean;
  saved_list: {
    id: number;
    name: string;
    description: string;
    source: string;
    is_public: boolean;
    share_token: string;
    share_url: string;
    items: Array<{
      id: number;
      quantity: number;
      note: string;
      ordering: number;
      product: BridgeToolProduct;
    }>;
  };
};

export type BridgeSavedListMutateResponse = {
  ok: boolean;
};

export type BridgeSavedListMoveToCartResponse = {
  ok: boolean;
  moved_items: number;
  cart: BridgeCartSnapshot;
};

export type BridgeSavedSearch = {
  id: number;
  name: string;
  querystring: string;
  created_at: string;
};

export type BridgeSavedSearchesResponse = {
  ok: boolean;
  saved_searches: BridgeSavedSearch[];
};

export type BridgeSavedSearchCreateResponse = {
  ok: boolean;
  saved_search: BridgeSavedSearch;
};

type BridgeRequestOptions = {
  method?: "GET" | "POST";
  body?: Record<string, unknown> | null;
  csrfToken?: string | null;
};

async function currentCookieHeader() {
  const requestHeaders = await headers();
  return requestHeaders.get("cookie") || "";
}

async function bridgeRequest<T>(
  path: string,
  { method = "GET", body = null, csrfToken = null }: BridgeRequestOptions = {},
): Promise<T> {
  const cookieHeader = await currentCookieHeader();
  const hasBody = method !== "GET" && body !== null;

  const response = await fetch(backendBridgeUrl(path), {
    method,
    cache: "no-store",
    headers: {
      accept: "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
      ...(hasBody ? { "content-type": "application/json" } : {}),
      ...(csrfToken ? { "x-csrftoken": csrfToken } : {}),
      ...(method !== "GET" ? { "x-requested-with": "XMLHttpRequest" } : {}),
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new BridgeApiError(
      `Bridge request failed: ${path}`,
      response.status,
      payload,
    );
  }

  return payload as T;
}

export async function getStorefrontSessionBootstrap() {
  return bridgeRequest<BridgeSessionBootstrap>("/api/storefront/session/bootstrap/");
}

export async function getStorefrontCartSnapshot() {
  return bridgeRequest<BridgeCartResponse>("/api/storefront/cart/");
}

export async function getStorefrontAccountBootstrap() {
  return bridgeRequest<BridgeAccountBootstrap>(
    "/api/storefront/account/bootstrap/",
  );
}

export async function getStorefrontOrderDetail(orderId: number) {
  return bridgeRequest<BridgeOrderDetailResponse>(
    `/api/storefront/orders/${orderId}/`,
  );
}

export async function getStorefrontAccountSettings() {
  return bridgeRequest<BridgeAccountSettingsResponse>(
    "/api/storefront/account/settings/",
  );
}

export async function getStorefrontAccountPreferences() {
  return bridgeRequest<BridgeAccountPreferencesResponse>(
    "/api/storefront/account/preferences/",
  );
}

export async function getStorefrontAccountAddresses() {
  return bridgeRequest<BridgeAccountAddressesResponse>(
    "/api/storefront/account/addresses/",
  );
}

export async function getStorefrontAccountLegalEntities() {
  return bridgeRequest<BridgeAccountLegalEntityResponse>(
    "/api/storefront/account/legal-entities/",
  );
}

export async function getStorefrontAccountNotifications() {
  return bridgeRequest<BridgeAccountNotificationsResponse>(
    "/api/storefront/account/notifications/",
  );
}

export async function getStorefrontFavorites() {
  return bridgeRequest<BridgeFavoritesResponse>("/api/storefront/tools/favorites/");
}

export async function getStorefrontSavedLists() {
  return bridgeRequest<BridgeSavedListsResponse>("/api/storefront/tools/lists/");
}

export async function getStorefrontSavedListDetail(listId: number) {
  return bridgeRequest<BridgeSavedListDetailResponse>(
    `/api/storefront/tools/lists/${listId}/`,
  );
}

export async function getStorefrontSavedSearches() {
  return bridgeRequest<BridgeSavedSearchesResponse>(
    "/api/storefront/tools/saved-searches/",
  );
}

export async function mutateStorefrontCart(
  path: "/api/storefront/cart/add/" | "/api/storefront/cart/update/" | "/api/storefront/cart/remove/" | "/api/storefront/cart/clear/",
  body: Record<string, unknown>,
  csrfToken: string,
) {
  return bridgeRequest<BridgeCartResponse>(path, {
    method: "POST",
    body,
    csrfToken,
  });
}

export async function toggleStorefrontFavorite(productId: number, csrfToken: string) {
  return bridgeRequest<BridgeFavoriteToggleResponse>(
    "/api/storefront/tools/favorites/toggle/",
    {
      method: "POST",
      body: { product_id: productId },
      csrfToken,
    },
  );
}

export async function createStorefrontSavedList(
  name: string,
  description: string,
  csrfToken: string,
) {
  return bridgeRequest<BridgeSavedListCreateResponse>("/api/storefront/tools/lists/", {
    method: "POST",
    body: { name, description },
    csrfToken,
  });
}

export async function toggleStorefrontSavedListPublic(
  listId: number,
  csrfToken: string,
) {
  return bridgeRequest<{ ok: boolean; is_public: boolean; share_token: string }>(
    `/api/storefront/tools/lists/${listId}/toggle-public/`,
    {
      method: "POST",
      body: {},
      csrfToken,
    },
  );
}

export async function deleteStorefrontSavedList(listId: number, csrfToken: string) {
  return bridgeRequest<BridgeSavedListMutateResponse>(
    `/api/storefront/tools/lists/${listId}/delete/`,
    {
      method: "POST",
      body: {},
      csrfToken,
    },
  );
}

export async function moveStorefrontSavedListToCart(
  listId: number,
  csrfToken: string,
) {
  return bridgeRequest<BridgeSavedListMoveToCartResponse>(
    `/api/storefront/tools/lists/${listId}/move-to-cart/`,
    {
      method: "POST",
      body: {},
      csrfToken,
    },
  );
}

export async function removeItemFromStorefrontSavedList(
  listId: number,
  itemId: number,
  csrfToken: string,
) {
  return bridgeRequest<BridgeSavedListMutateResponse>(
    `/api/storefront/tools/lists/${listId}/remove-item/`,
    {
      method: "POST",
      body: { item_id: itemId },
      csrfToken,
    },
  );
}

export async function createStorefrontSavedSearch(
  name: string,
  querystring: string,
  csrfToken: string,
) {
  return bridgeRequest<BridgeSavedSearchCreateResponse>(
    "/api/storefront/tools/saved-searches/",
    {
      method: "POST",
      body: { name, querystring },
      csrfToken,
    },
  );
}

export async function deleteStorefrontSavedSearch(
  searchId: number,
  csrfToken: string,
) {
  return bridgeRequest<BridgeSavedListMutateResponse>(
    `/api/storefront/tools/saved-searches/${searchId}/delete/`,
    {
      method: "POST",
      body: {},
      csrfToken,
    },
  );
}

export async function ingestStorefrontAnalytics(
  event: string,
  surface: string,
  payload: Record<string, unknown>,
  csrfToken: string,
) {
  return bridgeRequest<null>("/api/storefront/analytics/ingest/", {
    method: "POST",
    body: {
      event,
      surface,
      ...payload,
    },
    csrfToken,
  });
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Moscow",
  }).format(parsed);
}
