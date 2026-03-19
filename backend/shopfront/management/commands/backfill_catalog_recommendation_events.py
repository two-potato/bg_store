from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from catalog.models import Product
from orders.models import OrderItem
from shopfront.models import FavoriteProduct, RecommendationEvent, RecentlyViewedProduct
from shopfront.recommendation_selectors import search_recovery_candidate_ids


class Command(BaseCommand):
    help = "Backfill catalog/search_recovery recommendation events so catalog ML can be trained on realistic synthetic exposure logs."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=24, help="Maximum number of users to synthesize sessions for.")
        parser.add_argument("--sessions-per-user", type=int, default=4, help="How many catalog sessions to create per user.")
        parser.add_argument("--limit", type=int, default=8, help="How many recommendation impressions per session to keep.")
        parser.add_argument("--reset", action="store_true", help="Delete previous backfilled catalog events before generating new ones.")

    def handle(self, *args, **options):
        user_limit = max(1, int(options["users"] or 24))
        sessions_per_user = max(1, int(options["sessions_per_user"] or 4))
        limit = max(2, int(options["limit"] or 8))
        if options.get("reset"):
            deleted, _ = RecommendationEvent.objects.filter(request_id__startswith="backfill-catalog-").delete()
            self.stdout.write(self.style.WARNING(f"Deleted previous synthetic catalog events: {deleted}"))

        rng = Random(20260319)
        users = self._target_users(limit=user_limit)
        session_count = 0
        event_count = 0
        now = timezone.now()

        for user in users:
            seed_products = self._seed_products_for_user(user)
            if not seed_products:
                continue
            for session_index, seed_product in enumerate(seed_products[:sessions_per_user], start=1):
                query = self._query_for_seed(seed_product)
                candidate_ids = search_recovery_candidate_ids(query, limit=limit * 2)
                if not candidate_ids:
                    candidate_ids = list(
                        Product.objects.filter(
                            publication_status=Product.PublicationStatus.PUBLISHED,
                            category_id=seed_product.category_id,
                        )
                        .exclude(pk=seed_product.pk)
                        .order_by("-is_promo", "-is_new", "id")
                        .values_list("id", flat=True)[: limit * 2]
                    )
                ranked_candidates = []
                for product in Product.objects.filter(id__in=candidate_ids).select_related("brand", "category", "seller"):
                    affinity = 0
                    if seed_product.brand_id and product.brand_id == seed_product.brand_id:
                        affinity += 3
                    if seed_product.category_id and product.category_id == seed_product.category_id:
                        affinity += 2
                    if seed_product.seller_id and product.seller_id == seed_product.seller_id:
                        affinity += 1
                    if getattr(seed_product, "material", "") and product.material == seed_product.material:
                        affinity += 1
                    ranked_candidates.append((product, affinity))
                ranked_candidates.sort(key=lambda row: (-row[1], -int(row[0].is_promo), -int(row[0].is_new), row[0].id))
                ranked_candidates = ranked_candidates[:limit]
                if not ranked_candidates:
                    continue

                request_id = f"backfill-catalog-{user.id}-{session_index}"
                session_key = f"backfill-catalog-sess-{user.id}-{session_index}"
                session_time = now - timedelta(days=(user.id + session_index) % 21, hours=session_index * 2)

                click_target = ranked_candidates[0][0]
                add_to_cart_target = ranked_candidates[0][0] if len(ranked_candidates) >= 1 and ranked_candidates[0][1] >= 2 else None
                purchase_target = ranked_candidates[1][0] if len(ranked_candidates) >= 2 and ranked_candidates[1][1] >= 3 else add_to_cart_target

                for position, (product, affinity) in enumerate(ranked_candidates, start=1):
                    created = RecommendationEvent.objects.create(
                        event="recommendation_impression",
                        user=user,
                        session_key=session_key,
                        surface="catalog",
                        recommendation_source="search_recovery",
                        product=product,
                        seller_id=product.seller_id,
                        brand_id=product.brand_id,
                        category_id=product.category_id,
                        position=position,
                        request_id=request_id,
                        payload={
                            "search_query": query,
                            "search_term": query,
                            "cart_size": 0,
                            "experiment_variant": "ml_v1",
                            "strategy": "catalog_backfill",
                            "model_version": "backfill-catalog-v1",
                            "recommendation_reason_codes": self._reason_codes(seed_product, product),
                            "recommendation_candidate_sources": ["semantic_search_recovery", "catalog_backfill"],
                            "recommendation_score_hint": float(affinity),
                        },
                    )
                    RecommendationEvent.objects.filter(pk=created.pk).update(created_at=session_time + timedelta(seconds=position))
                    event_count += 1

                click_event = RecommendationEvent.objects.create(
                    event="recommendation_click",
                    user=user,
                    session_key=session_key,
                    surface="catalog",
                    recommendation_source="search_recovery",
                    product=click_target,
                    seller_id=click_target.seller_id,
                    brand_id=click_target.brand_id,
                    category_id=click_target.category_id,
                    position=1,
                    request_id=request_id,
                    payload={"search_query": query, "source": "catalog_backfill"},
                )
                RecommendationEvent.objects.filter(pk=click_event.pk).update(created_at=session_time + timedelta(minutes=2))
                event_count += 1

                if add_to_cart_target is not None and rng.random() < 0.85:
                    add_event = RecommendationEvent.objects.create(
                        event="add_to_cart",
                        user=user,
                        session_key=session_key,
                        surface="catalog",
                        recommendation_source="search_recovery",
                        product=add_to_cart_target,
                        seller_id=add_to_cart_target.seller_id,
                        brand_id=add_to_cart_target.brand_id,
                        category_id=add_to_cart_target.category_id,
                        position=1,
                        request_id=request_id,
                        payload={"search_query": query, "source": "catalog_backfill"},
                    )
                    RecommendationEvent.objects.filter(pk=add_event.pk).update(created_at=session_time + timedelta(minutes=4))
                    event_count += 1

                if purchase_target is not None and rng.random() < 0.55:
                    purchase_event = RecommendationEvent.objects.create(
                        event="purchase",
                        user=user,
                        session_key=session_key,
                        surface="catalog",
                        recommendation_source="search_recovery",
                        product=purchase_target,
                        seller_id=purchase_target.seller_id,
                        brand_id=purchase_target.brand_id,
                        category_id=purchase_target.category_id,
                        position=2 if purchase_target != click_target else 1,
                        request_id=request_id,
                        payload={"search_query": query, "source": "catalog_backfill"},
                    )
                    RecommendationEvent.objects.filter(pk=purchase_event.pk).update(created_at=session_time + timedelta(minutes=9))
                    event_count += 1

                session_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog backfill complete: users={len(users)}, sessions={session_count}, events={event_count}"
            )
        )

    def _target_users(self, *, limit: int):
        user_model = get_user_model()
        user_ids = list(
            FavoriteProduct.objects.values("user_id")
            .annotate(score=Count("id"))
            .order_by("-score", "user_id")
            .values_list("user_id", flat=True)[: limit * 2]
        )
        if len(user_ids) < limit:
            recent_ids = list(
                RecentlyViewedProduct.objects.values("user_id")
                .annotate(score=Count("id"))
                .order_by("-score", "user_id")
                .values_list("user_id", flat=True)[: limit * 2]
            )
            user_ids.extend(recent_ids)
        if len(user_ids) < limit:
            order_user_ids = list(
                OrderItem.objects.values("order__placed_by_id")
                .annotate(score=Count("id"))
                .order_by("-score", "order__placed_by_id")
                .values_list("order__placed_by_id", flat=True)[: limit * 2]
            )
            user_ids.extend(order_user_ids)
        deduped = []
        seen = set()
        for value in user_ids:
            if not value or value in seen:
                continue
            seen.add(int(value))
            deduped.append(int(value))
        return list(user_model.objects.filter(id__in=deduped[:limit]).order_by("id"))

    def _seed_products_for_user(self, user) -> list[Product]:
        favorite_ids = list(FavoriteProduct.objects.filter(user=user).order_by("-created_at").values_list("product_id", flat=True)[:6])
        recent_ids = list(RecentlyViewedProduct.objects.filter(user=user).order_by("-updated_at").values_list("product_id", flat=True)[:6])
        ordered_ids = list(
            OrderItem.objects.filter(order__placed_by=user)
            .order_by("-created_at")
            .values_list("product_id", flat=True)[:6]
        )
        ids = []
        for group in (favorite_ids, recent_ids, ordered_ids):
            for value in group:
                if value and value not in ids:
                    ids.append(int(value))
        products = {
            product.id: product
            for product in Product.objects.filter(id__in=ids).select_related("brand", "category", "seller")
        }
        return [products[product_id] for product_id in ids if product_id in products]

    def _query_for_seed(self, product: Product) -> str:
        parts = [
            getattr(getattr(product, "brand", None), "name", "") or "",
            getattr(getattr(product, "category", None), "name", "") or "",
            getattr(product, "material", "") or "",
            getattr(product, "purpose", "") or "",
        ]
        query = " ".join(part.strip() for part in parts if str(part or "").strip()).strip()
        return query or getattr(product, "name", "")

    def _reason_codes(self, seed_product: Product, product: Product) -> list[str]:
        reasons = ["search_intent_match"]
        if seed_product.brand_id and seed_product.brand_id == product.brand_id:
            reasons.append("seed_brand_match")
        if seed_product.category_id and seed_product.category_id == product.category_id:
            reasons.append("seed_category_match")
        if seed_product.seller_id and seed_product.seller_id == product.seller_id:
            reasons.append("seed_seller_match")
        return reasons
