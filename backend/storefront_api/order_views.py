from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.views import View

from catalog.models import Product
from commerce.cart_mutations import add_to_cart_session
from orders.models import Order
from users.views.helpers import _approval_approved_count, _approval_required_count, _visible_orders_queryset, approver_memberships_for_company, ensure_approval_policy, ensure_company_workspace

from .common import cart_payload, json_error, money, product_image_url


def _order_item(item):
    active_qty = int(getattr(item, "active_qty", item.qty or 0) or 0)
    return {"id": item.id, "product_id": item.product_id, "name": item.name, "qty": int(item.qty or 0), "canceled_qty": int(item.canceled_qty or 0), "active_qty": active_qty, "price": money(item.price), "row_total": money(Decimal(str(item.price))*Decimal(max(0,active_qty))), "seller_offer_id": item.seller_offer_id, "product": {"id": item.product.id, "slug": item.product.slug, "name": item.product.name, "sku": item.product.sku, "image_url": product_image_url(item.product)}}


def _detail(request, order):
    company = ensure_company_workspace(order.legal_entity) if order.legal_entity_id else None
    policy = ensure_approval_policy(company) if company else None
    can_approve = bool(company and approver_memberships_for_company(company).filter(user=request.user).exists())
    claims=list(order.claims.all()); tickets=list(order.support_tickets.all())
    shipments=[]
    for seller_order in order.seller_orders.all():
        for s in seller_order.shipments.all():
            shipments.append({"id":s.id,"seller_order_id":seller_order.id,"seller_id":seller_order.seller_id,"seller_name":seller_order.seller.username,"seller_store_name":seller_order.seller_store_name,"tracking_number":s.tracking_number,"delivery_method":s.delivery_method,"warehouse_name":s.warehouse_name,"status":s.status,"status_display":s.get_status_display(),"packed_at":s.packed_at.isoformat() if s.packed_at else None,"shipped_at":s.shipped_at.isoformat() if s.shipped_at else None,"delivered_at":s.delivered_at.isoformat() if s.delivered_at else None})
    fake=getattr(order,"fake_payment",None); demo=bool(getattr(settings,"ENABLE_DEMO_PAYMENTS",settings.DEBUG))
    retry=""
    if demo and order.placed_by_id==request.user.id and fake and order.payment_method in {Order.PaymentMethod.MIR_CARD,Order.PaymentMethod.ONLINE_CARD}: retry=f"/payments/{'online' if order.payment_method==Order.PaymentMethod.ONLINE_CARD else 'fake'}/{order.id}/"
    has_seller=bool(order.seller_orders.all()); paid=order.status in {Order.Status.PAID,Order.Status.DELIVERING,Order.Status.DELIVERED}; delivering=order.status in {Order.Status.DELIVERING,Order.Status.DELIVERED}; has_claims=bool(claims)
    timeline=[
      {"key":"created","title":"Created","state":"done","label":order.created_at.isoformat(),"timestamp":order.created_at.isoformat()},
      {"key":"sent_for_approval","title":"Sent for approval","state":"done" if order.approval_status in {Order.ApprovalStatus.PENDING,Order.ApprovalStatus.APPROVED,Order.ApprovalStatus.REJECTED} else "pending","label":order.get_approval_status_display(),"timestamp":None},
      {"key":"approved_or_rejected","title":"Approved / rejected","state":"done" if order.approval_status==Order.ApprovalStatus.APPROVED else "issue" if order.approval_status==Order.ApprovalStatus.REJECTED else "pending","label":order.approved_at.isoformat() if order.approved_at else "Ожидает решения","timestamp":order.approved_at.isoformat() if order.approved_at else None},
      {"key":"invoiced","title":"Invoiced","state":"done" if order.payment_method==Order.PaymentMethod.INVOICE else "pending","label":"По счёту" if order.payment_method==Order.PaymentMethod.INVOICE else "Без invoice flow","timestamp":None},
      {"key":"paid","title":"Paid","state":"done" if paid else "pending","label":order.get_status_display(),"timestamp":None},
      {"key":"packed","title":"Packed","state":"done" if has_seller else "pending","label":"Поставщики приняли заказ" if has_seller else "Ожидает распределения","timestamp":None},
      {"key":"shipped","title":"Shipped","state":"done" if delivering else "pending","label":"Выполняется" if delivering else "Ещё не отгружен","timestamp":None},
      {"key":"delivered","title":"Delivered","state":"done" if order.status==Order.Status.DELIVERED else "pending","label":"Заказ завершён" if order.status==Order.Status.DELIVERED else "В пути","timestamp":None},
      {"key":"claim_opened_or_resolved","title":"Claim opened / resolved","state":"issue" if has_claims else "pending","label":f"{len(claims)} обращений" if has_claims else "Без претензий","timestamp":None},
    ]
    return {"id":order.id,"status":order.status,"status_display":order.get_status_display(),"split_status":order.split_status,"split_status_display":order.get_split_status_display(),"approval_status":order.approval_status,"approval_status_display":order.get_approval_status_display(),"customer_type":order.customer_type,"customer_type_display":order.get_customer_type_display(),"payment_method":order.payment_method,"payment_method_display":order.get_payment_method_display(),"delivery_method":order.delivery_method,"delivery_method_display":order.get_delivery_method_display(),"subtotal":money(order.subtotal),"discount_amount":money(order.discount_amount),"total":money(order.total),"customer_comment":order.customer_comment,"coupon_code":order.coupon_code,"source_channel":order.source_channel,"created_at":order.created_at.isoformat(),"updated_at":order.updated_at.isoformat(),"items":[_order_item(i) for i in order.items.all()],"seller_splits":[{"id":s.id,"seller_id":s.seller_id,"seller_name":s.seller.username,"seller_store_name":s.seller_store_name,"items_count":int(s.items_count or 0),"subtotal":money(s.subtotal),"status":s.status,"status_display":s.get_status_display()} for s in order.seller_splits.all()],"approval":{"required_count":_approval_required_count(order),"approved_count":_approval_approved_count(order),"can_approve":can_approve,"policy":{"enabled":bool(policy and policy.is_enabled),"require_comment":bool(policy and policy.require_comment),"required_approvals_count":int(policy.required_approvals_count) if policy else 1,"max_pending_hours":int(policy.max_pending_hours) if policy else 24}},"tracking":{"available":bool(shipments),"shipments":shipments,"tracking_url":f"/account/orders/{order.id}/tracking/"},"payment":{"demo_enabled":demo,"can_retry":bool(retry),"retry_url":retry,"invoice_url":f"/account/orders/{order.id}/invoice/","fake_payment":{"provider_payment_id":fake.provider_payment_id if fake else "","status":fake.status if fake else "","status_display":fake.get_status_display() if fake else "","last_event":fake.last_event if fake else "","amount":money(fake.amount) if fake else "0.00"}},"support":{"claims_count":len(claims),"open_claims_count":sum(1 for c in claims if c.status in {c.Status.OPEN,c.Status.IN_REVIEW}),"support_tickets_count":len(tickets),"open_support_tickets_count":sum(1 for t in tickets if t.status in {t.Status.OPEN,t.Status.IN_PROGRESS})},"timeline":timeline,"actions":{"can_reorder":order.placed_by_id==request.user.id,"can_cancel":order.placed_by_id==request.user.id and order.status not in {Order.Status.CANCELED,Order.Status.DELIVERED},"reorder_url":f"/api/storefront/orders/{order.id}/reorder/","legacy_detail_url":f"/account/orders/{order.id}/"}}


class StorefrontOrderDetailView(View):
    def get(self, request, order_id):
        if not request.user.is_authenticated:return json_error(request,"authentication_required",401)
        order=_visible_orders_queryset(request.user).select_related("legal_entity","delivery_address","placed_by","approved_by","fake_payment").prefetch_related("items__product__images","seller_splits__seller","seller_orders__seller","seller_orders__shipments","approval_logs__actor","claims__created_by","claims__responded_by","support_tickets__created_by").filter(id=order_id).first()
        return JsonResponse({"ok":True,"order":_detail(request,order)}) if order else json_error(request,"order_not_found",404)


class StorefrontOrderReorderView(View):
    def post(self, request, order_id):
        if not request.user.is_authenticated:return json_error(request,"authentication_required",401)
        order=_visible_orders_queryset(request.user).prefetch_related("items").filter(id=order_id,placed_by=request.user).first()
        if not order:return json_error(request,"order_not_found",404)
        requested={}; names={}
        for i in order.items.all():
            qty=max(0,int(getattr(i,"active_qty",i.qty or 0) or 0)); requested[i.product_id]=requested.get(i.product_id,0)+qty; names[i.product_id]=i.name
        added=[]; adjusted=[]; unavailable=[]; total_req=sum(requested.values()); total_added=0
        session=request.session.get("cart",{})
        for pid,qty in requested.items():
            before=int((session.get(str(pid),{}) or {}).get("qty",0) or 0)
            try:r=add_to_cart_session(request=request,product_id=pid,qty=qty,logger=__import__("logging").getLogger("storefront_api"))
            except Product.DoesNotExist: unavailable.append({"product_id":pid,"product_name":names[pid],"requested_qty":qty,"reason":"product_not_found"});continue
            after=int(r["current_qty"]); inc=max(0,after-before); total_added+=inc; row={"product_id":pid,"product_name":r["product"].name,"requested_qty":qty,"added_qty":inc,"cart_qty":after}
            if inc<=0:unavailable.append({**row,"reason":"out_of_stock_or_limit_reached"})
            elif inc<qty:adjusted.append({**row,"reason":"stock_capped"})
            else:added.append(row)
        result="none" if total_req<=0 or total_added<=0 else "full" if total_added>=total_req else "partial"
        return JsonResponse({"ok":True,"reorder":{"order_id":order.id,"result_type":result,"summary":{"requested_lines":len(requested),"added_lines":len(added),"adjusted_lines":len(adjusted),"unavailable_lines":len(unavailable),"total_requested_qty":total_req,"total_added_qty":total_added},"added":added,"adjusted":adjusted,"unavailable":unavailable,"cart_url":"/cart/"},"cart":cart_payload(request)})
