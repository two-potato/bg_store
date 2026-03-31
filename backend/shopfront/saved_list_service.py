"""Service layer for saved list operations (favorites, lists, subscriptions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from catalog.models import Brand, Category, Product
from django.contrib.auth.models import User

from .models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    SavedList,
    SavedListItem,
    SavedSearch,
)
from .recommendation.attribution_service import record_recommendation_event

if TYPE_CHECKING:
    from django.http import HttpRequest


@dataclass(slots=True)
class SavedListOperationResult:
    """Result of a saved list operation."""

    success: bool
    message: str
    list_id: int | None = None
    affected_count: int = 0
    meta: dict[str, object] | None = None


class SavedListOperationService:
    """Manage saved list creation, deletion, and item management."""

    def __init__(self, user: User) -> None:
        self.user = user

    def create_list(
        self, name: str = "", description: str = "", source: str | None = None
    ) -> SavedListOperationResult:
        """Create a new saved list."""
        final_name = (name or "").strip() or "Новый список"
        final_desc = (description or "").strip()

        saved_list = SavedList.objects.create(
            user=self.user,
            name=final_name[:140],
            description=final_desc[:255],
            source=source,
        )
        return SavedListOperationResult(
            success=True, message="Список создан", list_id=saved_list.id
        )

    def delete_list(self, list_id: int) -> SavedListOperationResult:
        """Delete a saved list by ID."""
        affected = SavedList.objects.filter(user=self.user, id=list_id).delete()[0]
        if affected:
            return SavedListOperationResult(
                success=True, message="Список удалён", affected_count=affected
            )
        return SavedListOperationResult(success=False, message="Список не найден")

    def add_products_to_list(
        self,
        list_id: int,
        product_ids: list[int],
        quantities: dict[int, int] | None = None,
    ) -> SavedListOperationResult:
        """Add products to a saved list."""
        try:
            saved_list = SavedList.objects.get(user=self.user, id=list_id)
        except SavedList.DoesNotExist:
            return SavedListOperationResult(success=False, message="Список не найден")

        quantities = quantities or {}
        created_count = 0

        for product_id in product_ids:
            qty = quantities.get(product_id, 1)
            _, created = SavedListItem.objects.get_or_create(
                saved_list=saved_list,
                product_id=product_id,
                defaults={"quantity": max(1, qty)},
            )
            if created:
                created_count += 1

        return SavedListOperationResult(
            success=True,
            message="Товары добавлены в список",
            list_id=list_id,
            affected_count=created_count,
        )

    def remove_item_from_list(
        self, list_id: int, item_id: int
    ) -> SavedListOperationResult:
        """Remove an item from a saved list."""
        affected = SavedListItem.objects.filter(
            saved_list_id=list_id, saved_list__user=self.user, id=item_id
        ).delete()[0]

        if affected:
            return SavedListOperationResult(
                success=True, message="Товар удалён из списка", affected_count=affected
            )
        return SavedListOperationResult(success=False, message="Товар не найден")

    def toggle_list_public(self, list_id: int) -> SavedListOperationResult:
        """Toggle public/private status of a list."""
        try:
            saved_list = SavedList.objects.get(user=self.user, id=list_id)
        except SavedList.DoesNotExist:
            return SavedListOperationResult(success=False, message="Список не найден")

        saved_list.is_public = not saved_list.is_public
        saved_list.save(update_fields=["is_public", "updated_at"])

        return SavedListOperationResult(
            success=True,
            message="Настройки доступа обновлены",
            list_id=list_id,
        )


class FavoriteOperationService:
    """Manage favorite products."""

    def __init__(self, user: User) -> None:
        self.user = user

    def toggle_favorite(
        self, product: Product, request: HttpRequest | None = None
    ) -> tuple[bool, bool]:
        """
        Toggle favorite for a product.

        Returns: (success: bool, is_now_favorited: bool)
        """
        obj, created = FavoriteProduct.objects.get_or_create(
            user=self.user, product=product
        )
        from .context_processors import invalidate_favorites_state

        if created and request:
            from .views.constants import log

            try:
                record_recommendation_event(
                    request=request,
                    event_name="favorite_add",
                    product=product,
                    payload={"surface": "favorites_toggle"},
                    logger=log,
                )
            except Exception:
                pass
        elif not created:
            obj.delete()

        invalidate_favorites_state(self.user.id)

        return (True, created)

    def get_favorite_products(self, limit: int = 300) -> list[Product]:
        """Get user's favorite products."""
        product_ids = list(
            FavoriteProduct.objects.filter(user=self.user)
            .order_by("-created_at")
            .values_list("product_id", flat=True)[:limit]
        )

        from .catalog_selectors import ordered_products_with_related

        return ordered_products_with_related(product_ids, include_rating=True)


class SubscriptionOperationService:
    """Manage brand and category subscriptions."""

    def __init__(self, user: User) -> None:
        self.user = user

    def toggle_subscription(
        self, entity: str, entity_id: int
    ) -> SavedListOperationResult:
        """Toggle subscription to a brand or category."""
        model_map = {
            "brand": (BrandSubscription, Brand, "brand"),
            "category": (CategorySubscription, Category, "category"),
        }

        if entity not in model_map:
            return SavedListOperationResult(success=False, message="invalid entity")

        subscription_model, source_model, fk_name = model_map[entity]

        try:
            source = source_model.objects.get(pk=entity_id)
        except source_model.DoesNotExist:
            return SavedListOperationResult(success=False, message="entity_not_found")

        lookup = {"user": self.user, fk_name: source}
        obj, created = subscription_model.objects.get_or_create(**lookup)

        if not created:
            obj.delete()

        return SavedListOperationResult(
            success=True,
            message="Подписка обновлена",
            affected_count=1,
            meta={
                "entity": entity,
                "entity_id": entity_id,
                "subscribed": created,
            },
        )


class SavedSearchService:
    """Manage saved search filters."""

    def __init__(self, user: User) -> None:
        self.user = user

    def save_search(self, querystring: str, name: str = "") -> SavedListOperationResult:
        """Save a search filter."""
        querystring = (querystring or "").strip()
        name = (name or "").strip() or "Мой фильтр"

        if not querystring:
            return SavedListOperationResult(success=False, message="Пустой фильтр")

        saved_search = SavedSearch.objects.create(
            user=self.user,
            name=name[:120],
            querystring=querystring[:512],
        )

        return SavedListOperationResult(
            success=True,
            message="Поиск сохранён",
            list_id=saved_search.id,
        )

    def delete_search(self, search_id: int) -> SavedListOperationResult:
        """Delete a saved search."""
        affected = SavedSearch.objects.filter(user=self.user, id=search_id).delete()[0]

        if affected:
            return SavedListOperationResult(
                success=True, message="Сохранённый поиск удалён"
            )
        return SavedListOperationResult(success=False, message="Поиск не найден")

    def get_saved_searches(self, limit: int = 200) -> list[SavedSearch]:
        """Get user's saved searches."""
        return list(
            SavedSearch.objects.filter(user=self.user).order_by("-created_at")[:limit]
        )
