from django.http import JsonResponse
from django.views import View

from catalog.models import Product
from catalog.selectors import ordered_products_with_related
from commerce.cart_mutations import add_to_cart_session
from commerce.customer_state import FavoriteOperationService, SavedListOperationService, SavedSearchService
from legacy_shopfront_state.models import FavoriteProduct, SavedList, SavedListItem, SavedSearch

from .common import cart_payload, json_error, product_card, read_int, request_payload, string


class StorefrontFavoritesView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        products = FavoriteOperationService(request.user).get_favorite_products()
        return JsonResponse({"ok": True, "favorites": [product_card(p) for p in products], "counts": {"favorites": len(products), "saved_lists": SavedList.objects.filter(user=request.user).count()}})


class StorefrontFavoriteToggleView(View):
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        product_id = read_int(payload, "product_id")
        product = Product.objects.filter(pk=product_id).first() if product_id else None
        if product is None: return json_error(request, "product_not_found", 404)
        _, created = FavoriteOperationService(request.user).toggle_favorite(product, request=request)
        return JsonResponse({"ok": True, "favorited": created, "product_id": product.id})


class StorefrontSavedListsView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        rows = SavedList.objects.filter(user=request.user).prefetch_related("items").order_by("-updated_at", "-id")[:100]
        return JsonResponse({"ok": True, "saved_lists": [{"id": r.id, "name": r.name, "description": r.description or "", "source": r.source, "is_public": bool(r.is_public), "share_token": r.share_token, "items_count": r.items.count(), "updated_at": r.updated_at.isoformat()} for r in rows]})
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        result = SavedListOperationService(request.user).create_list(string(payload.get("name")), string(payload.get("description")), SavedList.Source.MANUAL)
        row = SavedList.objects.get(id=result.list_id)
        return JsonResponse({"ok": True, "saved_list": {"id": row.id, "name": row.name, "description": row.description or "", "source": row.source, "is_public": bool(row.is_public), "share_token": row.share_token}})


class StorefrontSavedListDetailView(View):
    def get(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        row = SavedList.objects.filter(user=request.user, id=list_id).prefetch_related("items").first()
        if not row: return json_error(request, "list_not_found", 404)
        items = list(row.items.all()); products = {p.id:p for p in ordered_products_with_related([i.product_id for i in items], include_rating=True)}
        return JsonResponse({"ok": True, "saved_list": {"id": row.id, "name": row.name, "description": row.description or "", "source": row.source, "is_public": bool(row.is_public), "share_token": row.share_token, "share_url": f"/lists/shared/{row.share_token}/", "items": [{"id": i.id, "quantity": int(i.quantity or 1), "note": i.note or "", "ordering": int(i.ordering or 0), "product": product_card(products[i.product_id])} for i in items if i.product_id in products]}})


class StorefrontSavedListAddItemView(View):
    def post(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        product_id, qty = read_int(payload, "product_id"), max(1, read_int(payload, "qty", 1) or 1)
        if not SavedList.objects.filter(user=request.user, id=list_id).exists(): return json_error(request, "list_not_found", 404)
        product = Product.objects.filter(pk=product_id).first() if product_id else None
        if not product: return json_error(request, "product_not_found", 404)
        SavedListOperationService(request.user).add_products_to_list(list_id, [product.id], {product.id: qty})
        item = SavedListItem.objects.get(saved_list_id=list_id, product=product)
        if item.quantity != qty: item.quantity=qty; item.save(update_fields=["quantity", "updated_at"])
        return JsonResponse({"ok": True, "item": {"id": item.id, "quantity": item.quantity, "product": product_card(product)}})


class StorefrontSavedListRemoveItemView(View):
    def post(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        result = SavedListOperationService(request.user).remove_item_from_list(list_id, read_int(payload, "item_id") or 0)
        return JsonResponse({"ok": True}) if result.success else json_error(request, "item_not_found", 404)


class StorefrontSavedListMoveToCartView(View):
    def post(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        row = SavedList.objects.filter(user=request.user, id=list_id).prefetch_related("items").first()
        if not row: return json_error(request, "list_not_found", 404)
        moved=0
        for item in row.items.all():
            try: add_to_cart_session(request=request, product_id=item.product_id, qty=max(1,int(item.quantity or 1)), logger=__import__("logging").getLogger("storefront_api")); moved+=1
            except Product.DoesNotExist: pass
        return JsonResponse({"ok": True, "moved_items": moved, "cart": cart_payload(request)})


class StorefrontSavedListTogglePublicView(View):
    def post(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        result=SavedListOperationService(request.user).toggle_list_public(list_id)
        if not result.success: return json_error(request,"list_not_found",404)
        row=SavedList.objects.get(user=request.user,id=list_id)
        return JsonResponse({"ok":True,"is_public":bool(row.is_public),"share_token":row.share_token})


class StorefrontSavedListDeleteView(View):
    def post(self, request, list_id):
        if not request.user.is_authenticated: return json_error(request,"authentication_required",401)
        return JsonResponse({"ok":True}) if SavedListOperationService(request.user).delete_list(list_id).success else json_error(request,"list_not_found",404)


class StorefrontSavedSearchesView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request,"authentication_required",401)
        rows=SavedSearchService(request.user).get_saved_searches()
        return JsonResponse({"ok":True,"saved_searches":[{"id":r.id,"name":r.name,"querystring":r.querystring,"created_at":r.created_at.isoformat()} for r in rows]})
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request,"authentication_required",401)
        payload,error=request_payload(request)
        if error:return json_error(request,error,400)
        result=SavedSearchService(request.user).save_search(string(payload.get("querystring")),string(payload.get("name"),"Мой фильтр"))
        if not result.success:return json_error(request,"invalid_querystring",400)
        r=SavedSearch.objects.get(id=result.list_id)
        return JsonResponse({"ok":True,"saved_search":{"id":r.id,"name":r.name,"querystring":r.querystring,"created_at":r.created_at.isoformat()}})


class StorefrontSavedSearchDeleteView(View):
    def post(self, request, search_id):
        if not request.user.is_authenticated:return json_error(request,"authentication_required",401)
        return JsonResponse({"ok":True}) if SavedSearchService(request.user).delete_search(search_id).success else json_error(request,"saved_search_not_found",404)
