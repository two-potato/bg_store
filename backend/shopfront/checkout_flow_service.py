import json


def ensure_checkout_idempotency_key(request, key_factory) -> str:
    checkout_idem_key = (request.session.get("checkout_idem_key") or "").strip()
    if not checkout_idem_key:
        checkout_idem_key = key_factory()
        request.session["checkout_idem_key"] = checkout_idem_key
        request.session.modified = True
    return checkout_idem_key


def build_checkout_context(
    *,
    request,
    cart_ctx: dict,
    memberships,
    addresses,
    form_data,
    checkout_error: str,
    checkout_idem_key: str,
    individual_default_name: str,
    individual_default_email: str,
    company_snapshots,
    checkout_step_tracking_payload,
    checkout_error_tracking_payload,
    checkout_cart_tracking_payload: str,
) -> dict:
    return {
        **cart_ctx,
        "memberships": memberships,
        "addresses": addresses,
        "form_data": form_data or {},
        "checkout_error": checkout_error or "",
        "checkout_idem_key": checkout_idem_key,
        "is_authenticated_checkout": bool(request.user.is_authenticated),
        "individual_default_name": individual_default_name,
        "individual_default_email": individual_default_email,
        "company_snapshots": company_snapshots,
        "checkout_step_tracking_payload": json.dumps(checkout_step_tracking_payload, ensure_ascii=False)
        if cart_ctx["items"]
        else "",
        "checkout_error_tracking_payload": json.dumps(checkout_error_tracking_payload, ensure_ascii=False)
        if checkout_error
        else "",
        "checkout_cart_tracking_payload": checkout_cart_tracking_payload,
    }


def fake_payment_template_context(
    *,
    order,
    payment,
    order_detail_url: str,
    payment_event_url: str,
    payment_page_url: str | None = None,
    payment_started_tracking_payload: str | None = None,
) -> dict:
    context = {
        "order": order,
        "payment": payment,
        "order_detail_url": order_detail_url,
        "payment_event_url": payment_event_url,
    }
    if payment_page_url is not None:
        context["payment_page_url"] = payment_page_url
    if payment_started_tracking_payload is not None:
        context["payment_started_tracking_payload"] = payment_started_tracking_payload
    return context
