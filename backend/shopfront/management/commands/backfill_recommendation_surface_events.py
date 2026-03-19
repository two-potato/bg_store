from __future__ import annotations

from datetime import timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from catalog.models import Product
from orders.models import OrderItem
from shopfront.models import FavoriteProduct, PersistentCart, RecommendationEvent, RecentlyViewedProduct
from shopfront.recommendation_service import cart_recommendations, checkout_recommendations, product_detail_recommendations, product_section_context


class Command(BaseCommand):
    help = "Backfill realistic recommendation exposure and feedback events for pdp, cart, and checkout surfaces."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=16)
        parser.add_argument("--pdp-sessions", type=int, default=3)
        parser.add_argument("--cart-sessions", type=int, default=2)
        parser.add_argument("--checkout-sessions", type=int, default=2)
        parser.add_argument("--limit", type=int, default=8)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if options.get("reset"):
            deleted, _ = RecommendationEvent.objects.filter(request_id__startswith="backfill-surface-").delete()
            self.stdout.write(self.style.WARNING(f"Deleted previous synthetic surface events: {deleted}"))
        self.rng = Random(20260319)
        self.limit = max(2, int(options["limit"] or 8))
        self.user_model = get_user_model()
        users = self._target_users(limit=max(1, int(options["users"] or 16)))
        pdp_sessions = max(1, int(options["pdp_sessions"] or 3))
        cart_sessions = max(1, int(options["cart_sessions"] or 2))
        checkout_sessions = max(1, int(options["checkout_sessions"] or 2))
        session_count = 0
        event_count = 0
        now = timezone.now()

        for user in users:
            seeds = self._seed_products_for_user(user)
            if not seeds:
                continue
            for idx, seed in enumerate(seeds[:pdp_sessions], start=1):
                session_time = now - timedelta(days=(user.id + idx) % 14, hours=idx)
                event_count += self._backfill_pdp(user, seed, session_index=idx, session_time=session_time)
                session_count += 1
            cart_sets = self._cart_sets_for_user(user, seeds)
            for idx, cart_products in enumerate(cart_sets[:cart_sessions], start=1):
                session_time = now - timedelta(days=(user.id + idx) % 10, minutes=15 * idx)
                event_count += self._backfill_cart(user, cart_products, session_index=idx, session_time=session_time)
                session_count += 1
            for idx, cart_products in enumerate(cart_sets[:checkout_sessions], start=1):
                session_time = now - timedelta(days=(user.id + idx) % 7, minutes=25 * idx)
                event_count += self._backfill_checkout(user, cart_products, session_index=idx, session_time=session_time)
                session_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Surface backfill complete: users={len(users)}, sessions={session_count}, events={event_count}"
            )
        )

    def _target_users(self, *, limit: int):
        user_ids = list(
            FavoriteProduct.objects.values("user_id")
            .annotate(score=Count("id"))
            .order_by("-score", "user_id")
            .values_list("user_id", flat=True)[: limit * 2]
        )
        if len(user_ids) < limit:
            user_ids.extend(
                list(
                    RecentlyViewedProduct.objects.values("user_id")
                    .annotate(score=Count("id"))
                    .order_by("-score", "user_id")
                    .values_list("user_id", flat=True)[: limit * 2]
                )
            )
        deduped = []
        seen = set()
        for value in user_ids:
            if not value:
                continue
            int_value = int(value)
            if int_value in seen:
                continue
            seen.add(int_value)
            deduped.append(int_value)
        return list(self.user_model.objects.filter(id__in=deduped[:limit]).order_by("id"))

    def _seed_products_for_user(self, user) -> list[Product]:
        ids: list[int] = []
        for values in (
            FavoriteProduct.objects.filter(user=user).order_by("-created_at").values_list("product_id", flat=True)[:8],
            RecentlyViewedProduct.objects.filter(user=user).order_by("-updated_at").values_list("product_id", flat=True)[:8],
            OrderItem.objects.filter(order__placed_by=user).order_by("-created_at").values_list("product_id", flat=True)[:8],
        ):
            for value in values:
                if value and int(value) not in ids:
                    ids.append(int(value))
        products = {
            product.id: product
            for product in Product.objects.filter(id__in=ids).select_related("brand", "category", "seller")
        }
        return [products[product_id] for product_id in ids if product_id in products]

    def _cart_sets_for_user(self, user, seeds: list[Product]) -> list[list[Product]]:
        payload = dict(
            PersistentCart.objects.filter(user=user).values_list("payload", flat=True).first() or {}
        )
        cart_product_ids = [int(value) for value in payload.keys() if str(value).isdigit()]
        products = {
            product.id: product
            for product in Product.objects.filter(id__in=cart_product_ids).select_related("brand", "category", "seller")
        }
        cart_products = [products[product_id] for product_id in cart_product_ids if product_id in products]
        if cart_products:
            return [cart_products[i : i + 3] for i in range(0, len(cart_products), 3) if cart_products[i : i + 3]]
        if len(seeds) >= 3:
            return [seeds[:3], seeds[1:4] if len(seeds) >= 4 else seeds[:3]]
        return [seeds]

    def _backfill_pdp(self, user, seed: Product, *, session_index: int, session_time) -> int:
        ctx = product_detail_recommendations(seed, user=user, request=None, limit=self.limit)
        similar = list(ctx.get("similar_products") or [])[: self.limit]
        accessories_ctx = product_section_context(seed, "seller-cross", user=user, request=None)
        accessories = list(accessories_ctx.get("products") or [])[: self.limit]
        substitute_products = list(ctx.get("substitute_products") or [])[: self.limit]
        sources = [
            ("product_similar", similar, "semantic_similarity"),
            ("product_seller_cross_sell", accessories, "same_seller_cross_sell"),
            ("product_substitutes", substitute_products, "substitute_option"),
        ]
        event_count = 0
        for source_name, products, reason_code in sources:
            if not products:
                continue
            request_id = f"backfill-surface-pdp-{user.id}-{seed.id}-{session_index}-{source_name}"
            session_key = f"backfill-surface-pdp-sess-{user.id}-{session_index}"
            for position, product in enumerate(products, start=1):
                impression = RecommendationEvent.objects.create(
                    event="recommendation_impression",
                    user=user,
                    session_key=session_key,
                    surface="pdp",
                    recommendation_source=source_name,
                    product=product,
                    seller_id=product.seller_id,
                    brand_id=product.brand_id,
                    category_id=product.category_id,
                    position=position,
                    request_id=request_id,
                    payload={
                        "source_product_id": seed.id,
                        "recommendation_reason_codes": [reason_code],
                        "recommendation_candidate_sources": [source_name],
                        "recommendation_score_hint": float(max(0.5, 3.0 - position * 0.1)),
                    },
                )
                RecommendationEvent.objects.filter(pk=impression.pk).update(created_at=session_time + timedelta(seconds=position))
                event_count += 1
            target = products[0]
            click = RecommendationEvent.objects.create(
                event="recommendation_click",
                user=user,
                session_key=session_key,
                surface="pdp",
                recommendation_source=source_name,
                product=target,
                seller_id=target.seller_id,
                brand_id=target.brand_id,
                category_id=target.category_id,
                position=1,
                request_id=request_id,
                payload={"source_product_id": seed.id},
            )
            RecommendationEvent.objects.filter(pk=click.pk).update(created_at=session_time + timedelta(minutes=2))
            event_count += 1
            if self.rng.random() < 0.7:
                add = RecommendationEvent.objects.create(
                    event="add_to_cart",
                    user=user,
                    session_key=session_key,
                    surface="pdp",
                    recommendation_source=source_name,
                    product=target,
                    seller_id=target.seller_id,
                    brand_id=target.brand_id,
                    category_id=target.category_id,
                    position=1,
                    request_id=request_id,
                    payload={"source_product_id": seed.id},
                )
                RecommendationEvent.objects.filter(pk=add.pk).update(created_at=session_time + timedelta(minutes=4))
                event_count += 1
        return event_count

    def _backfill_cart(self, user, cart_products: list[Product], *, session_index: int, session_time) -> int:
        cart_products = [product for product in cart_products if product is not None][:3]
        if not cart_products:
            return 0
        ctx = cart_recommendations(cart_products, user=user, request=None, limit=self.limit)
        products = list(ctx.get("products") or [])[: self.limit]
        if not products:
            return 0
        request_id = f"backfill-surface-cart-{user.id}-{session_index}"
        session_key = f"backfill-surface-cart-sess-{user.id}-{session_index}"
        event_count = 0
        for position, product in enumerate(products, start=1):
            impression = RecommendationEvent.objects.create(
                event="recommendation_impression",
                user=user,
                session_key=session_key,
                surface="cart",
                recommendation_source="cart_cross_sell",
                product=product,
                seller_id=product.seller_id,
                brand_id=product.brand_id,
                category_id=product.category_id,
                position=position,
                request_id=request_id,
                payload={
                    "cart_size": len(cart_products),
                    "recommendation_reason_codes": ["same_seller_cross_sell" if position == 1 else "trending"],
                    "recommendation_candidate_sources": ["same_seller", "cart_popular"],
                    "recommendation_score_hint": float(max(0.5, 2.5 - position * 0.1)),
                },
            )
            RecommendationEvent.objects.filter(pk=impression.pk).update(created_at=session_time + timedelta(seconds=position))
            event_count += 1
        target = products[0]
        for event_name, offset in (("recommendation_click", 2), ("add_to_cart", 4)):
            event = RecommendationEvent.objects.create(
                event=event_name,
                user=user,
                session_key=session_key,
                surface="cart",
                recommendation_source="cart_cross_sell",
                product=target,
                seller_id=target.seller_id,
                brand_id=target.brand_id,
                category_id=target.category_id,
                position=1,
                request_id=request_id,
                payload={"cart_size": len(cart_products)},
            )
            RecommendationEvent.objects.filter(pk=event.pk).update(created_at=session_time + timedelta(minutes=offset))
            event_count += 1
        return event_count

    def _backfill_checkout(self, user, cart_products: list[Product], *, session_index: int, session_time) -> int:
        cart_products = [product for product in cart_products if product is not None][:3]
        if not cart_products:
            return 0
        ctx = checkout_recommendations(cart_products, user=user, request=None, limit=max(4, self.limit - 2))
        products = list(ctx.get("products") or [])[: self.limit]
        if not products:
            return 0
        request_id = f"backfill-surface-checkout-{user.id}-{session_index}"
        session_key = f"backfill-surface-checkout-sess-{user.id}-{session_index}"
        event_count = 0
        for position, product in enumerate(products, start=1):
            impression = RecommendationEvent.objects.create(
                event="recommendation_impression",
                user=user,
                session_key=session_key,
                surface="checkout",
                recommendation_source="checkout_cross_sell",
                product=product,
                seller_id=product.seller_id,
                brand_id=product.brand_id,
                category_id=product.category_id,
                position=position,
                request_id=request_id,
                payload={
                    "cart_size": len(cart_products),
                    "recommendation_reason_codes": ["same_seller_cross_sell" if position == 1 else "replenishment_due"],
                    "recommendation_candidate_sources": ["same_seller_fast_stock", "replenishment_profile"],
                    "recommendation_score_hint": float(max(0.5, 2.8 - position * 0.12)),
                },
            )
            RecommendationEvent.objects.filter(pk=impression.pk).update(created_at=session_time + timedelta(seconds=position))
            event_count += 1
        target = products[0]
        click = RecommendationEvent.objects.create(
            event="recommendation_click",
            user=user,
            session_key=session_key,
            surface="checkout",
            recommendation_source="checkout_cross_sell",
            product=target,
            seller_id=target.seller_id,
            brand_id=target.brand_id,
            category_id=target.category_id,
            position=1,
            request_id=request_id,
            payload={"cart_size": len(cart_products)},
        )
        RecommendationEvent.objects.filter(pk=click.pk).update(created_at=session_time + timedelta(minutes=2))
        event_count += 1
        if self.rng.random() < 0.65:
            purchase = RecommendationEvent.objects.create(
                event="purchase",
                user=user,
                session_key=session_key,
                surface="checkout",
                recommendation_source="checkout_cross_sell",
                product=target,
                seller_id=target.seller_id,
                brand_id=target.brand_id,
                category_id=target.category_id,
                position=1,
                request_id=request_id,
                payload={"cart_size": len(cart_products)},
            )
            RecommendationEvent.objects.filter(pk=purchase.pk).update(created_at=session_time + timedelta(minutes=7))
            event_count += 1
        return event_count
