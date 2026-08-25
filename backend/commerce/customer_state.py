"""Customer shopping-state operations owned by the commerce domain.

The persisted models still use the historical ``shopfront`` app label until the
migration-state handoff is completed. Runtime callers should use this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from catalog.models import Brand, Category, Product
from catalog.selectors import ordered_products_with_related
from django.contrib.auth.models import User
from django.core.cache import cache

from shopfront.models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    SavedList,
    SavedListItem,
    SavedSearch,
)
from shopfront.recommendation.attribution_service import record_recommendation_event

if TYPE_CHECKING:
    from django.http import HttpRequest


@dataclass(slots=True)
class SavedListOperationResult:
    success: bool
    message: str
    list_id: int | None = None
    affected_count: int = 0
    meta: dict[str, object] | None = None


def _invalidate_favorites(user_id: int) -> None:
    cache.delete(f"shopfront:favorite_product_ids:v1:{int(user_id)}")


class SavedListOperationService:
    def __init__(self, user: User) -> None:
        self.user = user

    def create_list(self, name: str = "", description: str = "", source: str | None = None) -> SavedListOperationResult:
        saved_list = SavedList.objects.create(
            user=self.user,
            name=((name or "").strip() or "Новый список")[:140],
            description=(description or "").strip()[:255],
            source=source,
        )
        return SavedListOperationResult(True, "Список создан", list_id=saved_list.id)

    def delete_list(self, list_id: int) -> SavedListOperationResult:
        affected = SavedList.objects.filter(user=self.user, id=list_id).delete()[0]
        if affected:
            return SavedListOperationResult(True, "Список удалён", affected_count=affected)
        return SavedListOperationResult(False, "Список не найден")

    def add_products_to_list(self, list_id: int, product_ids: list[int], quantities: dict[int, int] | None = None) -> SavedListOperationResult:
        try:
            saved_list = SavedList.objects.get(user=self.user, id=list_id)
        except SavedList.DoesNotExist:
            return SavedListOperationResult(False, "Список не найден")
        quantities = quantities or {}
        created_count = 0
        for product_id in product_ids:
            _, created = SavedListItem.objects.get_or_create(
                saved_list=saved_list,
                product_id=product_id,
                defaults={"quantity": max(1, quantities.get(product_id, 1))},
            )
            created_count += int(created)
        return SavedListOperationResult(True, "Товары добавлены в список", list_id=list_id, affected_count=created_count)

    def remove_item_from_list(self, list_id: int, item_id: int) -> SavedListOperationResult:
        affected = SavedListItem.objects.filter(saved_list_id=list_id, saved_list__user=self.user, id=item_id).delete()[0]
        if affected:
            return SavedListOperationResult(True, "Товар удалён из списка", affected_count=affected)
        return SavedListOperationResult(False, "Товар не найден")

    def toggle_list_public(self, list_id: int) -> SavedListOperationResult:
        try:
            saved_list = SavedList.objects.get(user=self.user, id=list_id)
        except SavedList.DoesNotExist:
            return SavedListOperationResult(False, "Список не найден")
        saved_list.is_public = not saved_list.is_public
        saved_list.save(update_fields=["is_public", "updated_at"])
        return SavedListOperationResult(True, "Настройки доступа обновлены", list_id=list_id)


class FavoriteOperationService:
    def __init__(self, user: User) -> None:
        self.user = user

    def toggle_favorite(self, product: Product, request: HttpRequest | None = None) -> tuple[bool, bool]:
        obj, created = FavoriteProduct.objects.get_or_create(user=self.user, product=product)
        if created and request:
            try:
                record_recommendation_event(
                    request=request,
                    event_name="favorite_add",
                    product=product,
                    payload={"surface": "favorites_toggle"},
                    logger=__import__("logging").getLogger("commerce"),
                )
            except Exception:
                pass
        elif not created:
            obj.delete()
        _invalidate_favorites(self.user.id)
        return True, created

    def get_favorite_products(self, limit: int = 300) -> list[Product]:
        product_ids = list(
            FavoriteProduct.objects.filter(user=self.user)
            .order_by("-created_at")
            .values_list("product_id", flat=True)[:limit]
        )
        return ordered_products_with_related(product_ids, include_rating=True)


class SubscriptionOperationService:
    def __init__(self, user: User) -> None:
        self.user = user

    def toggle_subscription(self, entity: str, entity_id: int) -> SavedListOperationResult:
        model_map = {
            "brand": (BrandSubscription, Brand, "brand"),
            "category": (CategorySubscription, Category, "category"),
        }
        if entity not in model_map:
            return SavedListOperationResult(False, "invalid entity")
        subscription_model, source_model, fk_name = model_map[entity]
        try:
            source = source_model.objects.get(pk=entity_id)
        except source_model.DoesNotExist:
            return SavedListOperationResult(False, "entity_not_found")
        obj, created = subscription_model.objects.get_or_create(**{"user": self.user, fk_name: source})
        if not created:
            obj.delete()
        return SavedListOperationResult(
            True,
            "Подписка обновлена",
            affected_count=1,
            meta={"entity": entity, "entity_id": entity_id, "subscribed": created},
        )


class SavedSearchService:
    def __init__(self, user: User) -> None:
        self.user = user

    def save_search(self, querystring: str, name: str = "") -> SavedListOperationResult:
        querystring = (querystring or "").strip()
        if not querystring:
            return SavedListOperationResult(False, "Пустой фильтр")
        saved_search = SavedSearch.objects.create(
            user=self.user,
            name=((name or "").strip() or "Мой фильтр")[:120],
            querystring=querystring[:512],
        )
        return SavedListOperationResult(True, "Поиск сохранён", list_id=saved_search.id)

    def delete_search(self, search_id: int) -> SavedListOperationResult:
        affected = SavedSearch.objects.filter(user=self.user, id=search_id).delete()[0]
        if affected:
            return SavedListOperationResult(True, "Сохранённый поиск удалён")
        return SavedListOperationResult(False, "Поиск не найден")

    def get_saved_searches(self, limit: int = 200) -> list[SavedSearch]:
        return list(SavedSearch.objects.filter(user=self.user).order_by("-created_at")[:limit])
