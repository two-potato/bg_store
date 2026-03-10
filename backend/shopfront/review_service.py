from django.db.models import Avg, Count, Prefetch
from django.core.cache import cache
from django.conf import settings
from django.shortcuts import render

from catalog.models import (
    Product,
    ProductQuestion,
    ProductReview,
    ProductReviewComment,
    ProductReviewPhoto,
    ProductReviewVote,
)
from orders.models import Order, OrderItem


PAID_OR_CONFIRMED_ORDER_STATUSES = [
    Order.Status.CONFIRMED,
    Order.Status.PAID,
    Order.Status.DELIVERING,
    Order.Status.DELIVERED,
    Order.Status.CHANGED,
]


def _product_rating_summary(product_id: int) -> dict:
    cache_key = f"shopfront:product_rating:v1:{product_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    agg = ProductReview.objects.filter(product_id=product_id).aggregate(avg=Avg("rating"), count=Count("id"))
    payload = {
        "rating_avg": agg["avg"] or 0,
        "rating_count": agg["count"] or 0,
    }
    cache.set(cache_key, payload, timeout=getattr(settings, "CACHE_TTL_PDP_SUMMARY", 300))
    return payload


def build_reviews_context(product: Product, user, *, seller_rating_summary) -> dict:
    reviews_qs = (
        product.reviews.select_related("user", "user__profile")
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=ProductReviewComment.objects.select_related("user", "user__profile").order_by("created_at", "id"),
            ),
            Prefetch(
                "photos",
                queryset=ProductReviewPhoto.objects.order_by("ordering", "id"),
            ),
        )
    )
    product_rating = _product_rating_summary(product.id)
    user_review = None
    if getattr(user, "is_authenticated", False):
        user_review = reviews_qs.filter(user=user).first()
    questions_qs = ProductQuestion.objects.filter(product=product, is_public=True).select_related("user", "answered_by")[:20]
    seller_summary = seller_rating_summary(getattr(product, "seller_id", None))
    return {
        "p": product,
        "reviews": reviews_qs[:30],
        "rating_avg": product_rating["rating_avg"],
        "rating_count": product_rating["rating_count"],
        "user_review": user_review,
        "questions": questions_qs,
        "seller_rating_avg": seller_summary["rating_avg"],
        "seller_rating_count": seller_summary["rating_count"],
    }


def render_reviews_partial(request, product: Product, *, seller_rating_summary, status: int = 200):
    return render(
        request,
        "shopfront/partials/product_reviews.html",
        build_reviews_context(product, request.user, seller_rating_summary=seller_rating_summary),
        status=status,
    )


def has_verified_product_purchase(*, user, product: Product) -> bool:
    return OrderItem.objects.filter(
        order__placed_by=user,
        order__status__in=PAID_OR_CONFIRMED_ORDER_STATUSES,
        product=product,
    ).exists()


def upsert_product_review(*, product: Product, user, rating: int, text: str):
    verified = has_verified_product_purchase(user=user, product=product)
    return ProductReview.objects.update_or_create(
        product=product,
        user=user,
        defaults={"rating": rating, "text": text, "is_verified_purchase": verified},
    )


def delete_product_review(*, product: Product, user) -> int:
    deleted, _ = ProductReview.objects.filter(product=product, user=user).delete()
    return deleted


def create_review_comment(*, review: ProductReview, user, text: str):
    return ProductReviewComment.objects.create(review=review, user=user, text=text)


def update_review_comment(*, comment: ProductReviewComment, text: str):
    comment.text = text
    comment.save(update_fields=["text", "updated_at"])
    return comment


def delete_review_comment(*, comment: ProductReviewComment):
    comment.delete()


def apply_review_vote(*, review: ProductReview, user, value: str):
    ProductReviewVote.objects.update_or_create(
        review=review,
        user=user,
        defaults={"value": value},
    )
    review.helpful_count = ProductReviewVote.objects.filter(
        review=review, value=ProductReviewVote.Value.HELPFUL
    ).count()
    review.unhelpful_count = ProductReviewVote.objects.filter(
        review=review, value=ProductReviewVote.Value.UNHELPFUL
    ).count()
    review.save(update_fields=["helpful_count", "unhelpful_count", "updated_at"])
    return review


def create_product_question(*, product: Product, user, question_text: str):
    return ProductQuestion.objects.create(product=product, user=user, question_text=question_text)
