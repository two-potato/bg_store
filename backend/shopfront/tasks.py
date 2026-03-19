import asyncio
import logging
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from catalog.models import Product
from orders.models import OrderItem
from users.models import UserProfile
from core.notifications import apost_notify_json, is_telegram_recipient_quarantined, send_mail_message
from .models import (
    FavoriteProduct,
    RecommendationPopularitySnapshot,
    RecommendationProductAffinity,
    RecommendationReplenishmentProfile,
    RecommendationSet,
    RecommendationUserAffinity,
    RecentlyViewedProduct,
)
from .recommendation_ranker import rerank_product_ids
from .recommendation_selectors import (
    hybrid_affinity_candidates,
    personalized_candidate_ids,
    user_reorder_ids,
    watchlist_candidate_ids,
)

log = logging.getLogger("shopfront")


def _admin_emails() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def _admin_telegram_ids() -> list[int]:
    recipients: list[int] = []
    seen: set[int] = set()
    qs = UserProfile.objects.filter(
        role=UserProfile.Role.ADMIN,
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    for value in qs:
        if not value:
            continue
        tg_id = int(value)
        if is_telegram_recipient_quarantined(tg_id):
            continue
        if tg_id in seen:
            continue
        seen.add(tg_id)
        recipients.append(tg_id)
    explicit = list(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or [])
    for value in explicit:
        if not str(value).strip().lstrip("-").isdigit():
            continue
        tg_id = int(value)
        if is_telegram_recipient_quarantined(tg_id):
            continue
        if tg_id in seen:
            continue
        seen.add(tg_id)
        recipients.append(tg_id)
    return recipients

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_contact_feedback(self, *, name: str, phone: str, message: str, source: str):
    text = (
        "Новая заявка из формы обратной связи\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n\n"
        f"Сообщение:\n{message}\n"
    )

    recipients = _admin_emails()
    if recipients:
        send_mail_message(
            subject="[Servio] Новая заявка с формы контактов",
            message=text,
            recipient_list=recipients,
            logger=log,
            extra={"source": source},
        )
    else:
        log.warning("contact_feedback_email_no_recipients")

    tg_text = (
        "📩 Новая заявка с формы контактов\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n\n"
        f"{message}"
    )
    telegram_ids = _admin_telegram_ids()

    async def _send():
        from httpx import AsyncClient

        async with AsyncClient(timeout=10) as client:
            for tg in telegram_ids:
                await apost_notify_json(
                    client,
                    "/notify/send_text",
                    {"telegram_id": tg, "text": tg_text},
                    logger=log,
                    failure_event="contact_feedback_send_text_failed",
                    extra={"telegram_id": tg},
                )
            # Group delivery is a fallback channel. Keep task successful even if this path is not configured.
            await apost_notify_json(
                client,
                "/notify/send_group",
                {"text": tg_text},
                logger=log,
                failure_event="contact_feedback_group_send_failed",
            )

    try:
        asyncio.run(_send())
    except Exception:
        log.exception("contact_feedback_tg_send_failed", extra={"recipients": telegram_ids})
        raise
    log.info("contact_feedback_tg_sent", extra={"recipients": telegram_ids})


def _replace_snapshot_rows(*, scope_type: str, scope_id: int, window: str, rows: list[dict]) -> int:
    RecommendationPopularitySnapshot.objects.filter(scope_type=scope_type, scope_id=scope_id, window=window).delete()
    RecommendationPopularitySnapshot.objects.bulk_create(
        [
            RecommendationPopularitySnapshot(
                scope_type=scope_type,
                scope_id=scope_id,
                window=window,
                product_id=row["product_id"],
                score=row["score"],
                metadata=row.get("metadata", {}),
            )
            for row in rows
        ],
        batch_size=200,
    )
    return len(rows)


def _set_recommendation_set(*, kind: str, scope_type: str, scope_id: int, source: str, product_ids: list[int], expires_in_sec: int = 3600, metadata: dict | None = None) -> RecommendationSet:
    now = timezone.now()
    return RecommendationSet.objects.create(
        kind=kind,
        scope_type=scope_type,
        scope_id=scope_id,
        source=source,
        product_ids=list(product_ids or []),
        metadata=metadata or {},
        generated_at=now,
        expires_at=now + timedelta(seconds=max(60, expires_in_sec)),
    )


@shared_task
def refresh_recommendation_popularity(window: str = "7d", limit: int = 60):
    since = timezone.now() - timedelta(days=30 if window == "30d" else 7)
    recent_views = Counter(
        RecentlyViewedProduct.objects.filter(updated_at__gte=since).values_list("product_id", flat=True)
    )
    favorites = Counter(FavoriteProduct.objects.filter(created_at__gte=since).values_list("product_id", flat=True))
    purchases = Counter(OrderItem.objects.filter(created_at__gte=since).values_list("product_id", flat=True))
    products = list(
        Product.objects.filter(publication_status=Product.PublicationStatus.PUBLISHED)
        .only("id", "category_id", "brand_id", "seller_id", "is_new", "is_promo", "stock_qty")
    )
    global_rows = []
    by_category: dict[int, list[dict]] = defaultdict(list)
    for product in products:
        score = Decimal(purchases[product.id] * 8 + favorites[product.id] * 3 + recent_views[product.id])
        if product.is_promo:
            score += Decimal("2")
        if product.is_new:
            score += Decimal("1")
        if product.stock_qty > 0:
            score += Decimal("1")
        if score <= 0:
            continue
        row = {
            "product_id": product.id,
            "score": score,
            "metadata": {
                "purchase_count": purchases[product.id],
                "favorite_count": favorites[product.id],
                "recent_view_count": recent_views[product.id],
            },
        }
        global_rows.append(row)
        if product.category_id:
            by_category[product.category_id].append(row)
    global_rows.sort(key=lambda row: (-row["score"], row["product_id"]))
    _replace_snapshot_rows(
        scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
        scope_id=0,
        window=window,
        rows=global_rows[:limit],
    )
    for category_id, rows in by_category.items():
        rows.sort(key=lambda row: (-row["score"], row["product_id"]))
        _replace_snapshot_rows(
            scope_type=RecommendationPopularitySnapshot.ScopeType.CATEGORY,
            scope_id=category_id,
            window=window,
            rows=rows[:limit],
        )
    log.info("recommendation_popularity_refreshed", extra={"window": window, "global_count": len(global_rows[:limit])})
    return len(global_rows[:limit])


@shared_task
def refresh_recommendation_affinities(limit_per_product: int = 24):
    order_item_rows = list(
        OrderItem.objects.values_list("order_id", "product_id").order_by("order_id", "product_id")
    )
    by_order: dict[int, list[int]] = defaultdict(list)
    for order_id, product_id in order_item_rows:
        by_order[int(order_id)].append(int(product_id))
    edges: Counter[tuple[int, int]] = Counter()
    for product_ids in by_order.values():
        deduped = sorted(set(product_ids))
        for source_product_id in deduped:
            for target_product_id in deduped:
                if source_product_id == target_product_id:
                    continue
                edges[(source_product_id, target_product_id)] += 1
    RecommendationProductAffinity.objects.filter(
        affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE
    ).delete()
    rows = []
    grouped: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for (source_product_id, target_product_id), count in edges.items():
        grouped[source_product_id].append((target_product_id, count))
    for source_product_id, targets in grouped.items():
        for target_product_id, count in sorted(targets, key=lambda item: (-item[1], item[0]))[:limit_per_product]:
            rows.append(
                RecommendationProductAffinity(
                    source_product_id=source_product_id,
                    target_product_id=target_product_id,
                    affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE,
                    score=Decimal(count),
                    orders_count=count,
                )
            )
    RecommendationProductAffinity.objects.bulk_create(rows, batch_size=200)
    log.info("recommendation_affinities_refreshed", extra={"edges": len(rows)})
    return len(rows)


@shared_task
def refresh_recommendation_user_affinity(limit_per_dimension: int = 12):
    RecommendationUserAffinity.objects.all().delete()
    price_band_bounds = (
        ("entry", lambda price: Decimal(str(price or 0)) < Decimal("2000")),
        ("mid", lambda price: Decimal("2000") <= Decimal(str(price or 0)) < Decimal("10000")),
        ("premium", lambda price: Decimal(str(price or 0)) >= Decimal("10000")),
    )
    rows = []
    user_ids = set(FavoriteProduct.objects.values_list("user_id", flat=True)) | set(RecentlyViewedProduct.objects.values_list("user_id", flat=True)) | set(OrderItem.objects.values_list("order__placed_by_id", flat=True))
    for user_id in sorted(int(value) for value in user_ids if value):
        favorites = list(FavoriteProduct.objects.filter(user_id=user_id).select_related("product")[:128])
        recents = list(RecentlyViewedProduct.objects.filter(user_id=user_id).select_related("product")[:128])
        order_items = list(OrderItem.objects.filter(order__placed_by_id=user_id).select_related("product")[:256])
        dimension_scores: dict[tuple[str, int, str], Decimal] = defaultdict(lambda: Decimal("0"))
        dimension_counts: Counter[tuple[str, int, str]] = Counter()
        for collection, weight in ((favorites, Decimal("4")), (recents, Decimal("2")), (order_items, Decimal("6"))):
            for item in collection:
                product = getattr(item, "product", None)
                if not product:
                    continue
                for dimension, entity_id in (
                    ("brand", int(getattr(product, "brand_id", 0) or 0)),
                    ("category", int(getattr(product, "category_id", 0) or 0)),
                    ("seller", int(getattr(product, "seller_id", 0) or 0)),
                ):
                    if entity_id <= 0:
                        continue
                    key = (dimension, entity_id, "")
                    dimension_scores[key] += weight
                    dimension_counts[key] += 1
                for tag_id in product.tags.values_list("id", flat=True)[:10]:
                    key = ("tag", int(tag_id), "")
                    dimension_scores[key] += weight / Decimal("2")
                    dimension_counts[key] += 1
                price_value = getattr(product, "price", 0)
                for price_band, predicate in price_band_bounds:
                    if predicate(price_value):
                        key = ("price_band", 0, price_band)
                        dimension_scores[key] += weight
                        dimension_counts[key] += 1
                        break
        per_dimension_rank: dict[str, list[tuple[tuple[str, int, str], Decimal]]] = defaultdict(list)
        for key, score in dimension_scores.items():
            per_dimension_rank[key[0]].append((key, score))
        for dimension, ranked in per_dimension_rank.items():
            for (dim, entity_id, entity_key), score in sorted(ranked, key=lambda item: (-item[1], item[0][1], item[0][2]))[:limit_per_dimension]:
                rows.append(
                    RecommendationUserAffinity(
                        user_id=user_id,
                        dimension=dim,
                        entity_id=entity_id,
                        entity_key=entity_key,
                        score=score,
                        event_count=int(dimension_counts[(dim, entity_id, entity_key)]),
                    )
                )
    RecommendationUserAffinity.objects.bulk_create(rows, batch_size=200)
    log.info("recommendation_user_affinity_refreshed", extra={"rows": len(rows)})
    return len(rows)


@shared_task
def refresh_recommendation_replenishment(limit_per_user: int = 24):
    RecommendationReplenishmentProfile.objects.all().delete()
    rows = []
    grouped: dict[tuple[int, int], list] = defaultdict(list)
    for item in (
        OrderItem.objects.filter(order__placed_by_id__isnull=False)
        .select_related("order", "product")
        .order_by("order__placed_by_id", "product_id", "order__created_at", "id")
    ):
        grouped[(int(item.order.placed_by_id), int(item.product_id))].append(item)
    now = timezone.now()
    for (user_id, product_id), items in grouped.items():
        ordered_at = [getattr(item.order, "created_at", None) for item in items if getattr(item.order, "created_at", None) is not None]
        intervals = []
        for idx in range(1, len(ordered_at)):
            delta = ordered_at[idx] - ordered_at[idx - 1]
            if delta.days > 0:
                intervals.append(delta.days)
        expected_interval = Decimal(str(sum(intervals) / len(intervals))) if intervals else Decimal("0")
        last_ordered_at = ordered_at[-1] if ordered_at else None
        days_since_last = Decimal(str(max(0, (now - last_ordered_at).days))) if last_ordered_at else Decimal("0")
        orders_count = len({int(item.order_id) for item in items})
        quantity_total = sum(int(item.qty or 0) for item in items)
        score = Decimal(str(orders_count * 5 + quantity_total))
        if expected_interval > 0:
            score += min(Decimal("10"), days_since_last / expected_interval * Decimal("6"))
        rows.append(
            RecommendationReplenishmentProfile(
                user_id=user_id,
                product_id=product_id,
                first_ordered_at=ordered_at[0] if ordered_at else None,
                last_ordered_at=last_ordered_at,
                orders_count=orders_count,
                quantity_total=quantity_total,
                expected_interval_days=expected_interval,
                score=score,
                metadata={"days_since_last": float(days_since_last)},
            )
        )
    RecommendationReplenishmentProfile.objects.bulk_create(rows, batch_size=200)
    log.info("recommendation_replenishment_refreshed", extra={"rows": len(rows)})
    return len(rows)


@shared_task
def refresh_recommendation_sets(limit: int = 8):
    now = timezone.now()
    RecommendationSet.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
    global_ids = list(
        RecommendationPopularitySnapshot.objects.filter(
            scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
            scope_id=0,
            window="7d",
        )
        .order_by("-score", "product_id")
        .values_list("product_id", flat=True)[:limit]
    )
    _set_recommendation_set(
        kind="home_popular",
        scope_type=RecommendationSet.ScopeType.GLOBAL,
        scope_id=0,
        source="popularity_snapshot",
        product_ids=global_ids,
    )
    user_ids = list(
        RecommendationUserAffinity.objects.order_by().values_list("user_id", flat=True).distinct()[:500]
    )
    for user_id in user_ids:
        user_ref = type("UserRef", (), {"is_authenticated": True, "id": user_id})()
        candidate_ids = personalized_candidate_ids(user_ref, limit=limit * 3) + hybrid_affinity_candidates(user_ref, limit=limit * 2)
        if candidate_ids:
            ranked_ids = rerank_product_ids(candidate_ids, user=user_ref, source_name="personalized_home", experiment_variant="ranked_v2", limit=limit)
            _set_recommendation_set(
                kind="personalized_home",
                scope_type=RecommendationSet.ScopeType.USER,
                scope_id=user_id,
                source="personalized_candidates",
                product_ids=ranked_ids,
                metadata={"experiment_variant": "ranked_v2"},
            )
        watchlist_ids = watchlist_candidate_ids(user_ref, limit=limit * 2)
        if watchlist_ids:
            _set_recommendation_set(
                kind="watchlist_home",
                scope_type=RecommendationSet.ScopeType.USER,
                scope_id=user_id,
                source="watchlist_candidates",
                product_ids=watchlist_ids[:limit],
            )
        reorder_ids = list(
            RecommendationReplenishmentProfile.objects.filter(user_id=user_id)
            .order_by("-score", "product_id")
            .values_list("product_id", flat=True)[:limit]
        ) or user_reorder_ids(user_ref, limit=limit)
        if reorder_ids:
            _set_recommendation_set(
                kind="reorder",
                scope_type=RecommendationSet.ScopeType.USER,
                scope_id=user_id,
                source="order_history",
                product_ids=reorder_ids,
                expires_in_sec=6 * 3600,
            )
    for source_product_id in (
        RecommendationProductAffinity.objects.filter(affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE)
        .order_by()
        .values_list("source_product_id", flat=True)
        .distinct()[:500]
    ):
        product_ids = list(
            RecommendationProductAffinity.objects.filter(
                source_product_id=source_product_id,
                affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE,
            )
            .order_by("-score", "-orders_count", "target_product_id")
            .values_list("target_product_id", flat=True)[:limit]
        )
        _set_recommendation_set(
            kind="fbt",
            scope_type=RecommendationSet.ScopeType.PRODUCT,
            scope_id=source_product_id,
            source="product_affinity",
            product_ids=product_ids,
            expires_in_sec=6 * 3600,
        )
    log.info("recommendation_sets_refreshed", extra={"users": len(user_ids), "global_ids": len(global_ids)})
    return {"users": len(user_ids), "global_ids": len(global_ids)}
