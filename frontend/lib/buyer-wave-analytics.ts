"use client";

export type BuyerWaveEvent =
  | "cart_viewed"
  | "cart_qty_incremented"
  | "cart_qty_decremented"
  | "cart_item_removed"
  | "cart_cleared"
  | "cart_checkout_clicked"
  | "account_dashboard_viewed"
  | "orders_list_viewed"
  | "order_detail_viewed"
  | "order_tracking_viewed"
  | "order_reorder_clicked"
  | "order_cancel_submitted"
  | "invoice_download_clicked"
  | "claim_created"
  | "support_ticket_created"
  | "address_created"
  | "legal_request_created"
  | "favorites_viewed"
  | "favorite_toggled"
  | "saved_list_created"
  | "saved_list_deleted"
  | "saved_list_item_added"
  | "saved_list_item_removed"
  | "saved_list_moved_to_cart"
  | "saved_search_saved"
  | "saved_search_deleted";

function readCookie(name: string) {
  if (typeof document === "undefined") {
    return "";
  }

  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[$()*+.?[\\\]^{|}]/g, "\\$&")}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : "";
}

export async function trackBuyerWaveEvent(
  event: BuyerWaveEvent,
  surface: string,
  payload: Record<string, unknown> = {},
) {
  const csrfToken = readCookie("csrftoken");
  const headers: Record<string, string> = {
    accept: "application/json",
    "content-type": "application/json",
    "x-requested-with": "XMLHttpRequest",
  };

  if (csrfToken) {
    headers["x-csrftoken"] = csrfToken;
  }

  try {
    await fetch("/api/storefront/analytics/ingest/", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      keepalive: true,
      headers,
      body: JSON.stringify({
        event,
        surface,
        ...payload,
      }),
    });
  } catch {
    // analytics endpoint should never block user action flow
  }
}
