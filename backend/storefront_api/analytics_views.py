import logging

from django.http import HttpResponse
from django.views import View

from .common import json_error, request_payload, string

log = logging.getLogger("storefront_api.analytics")


class StorefrontWaveAnalyticsIngestView(View):
    allowed_events = {"cart_viewed","cart_qty_incremented","cart_qty_decremented","cart_item_removed","cart_cleared","cart_checkout_clicked","account_dashboard_viewed","orders_list_viewed","order_detail_viewed","order_tracking_viewed","order_reorder_clicked","order_cancel_submitted","invoice_download_clicked","claim_created","support_ticket_created","address_created","legal_request_created","favorites_viewed","favorite_toggled","saved_list_created","saved_list_deleted","saved_list_item_added","saved_list_item_removed","saved_list_moved_to_cart","saved_search_saved","saved_search_deleted"}
    def post(self, request):
        payload,error=request_payload(request)
        if error:return json_error(request,error,400)
        event=string(payload.get("event"))
        if event not in self.allowed_events:return json_error(request,"unsupported_event",400)
        log.info("storefront_api_analytics_event",extra={"event":event,"user_id":request.user.id if getattr(request.user,"is_authenticated",False) else None,"surface":string(payload.get("surface"),"unknown")})
        return HttpResponse(status=204)
