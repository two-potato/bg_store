from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel

from .product import Product


class ProductReview(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True, default="")
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="unique_product_review_per_user"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Review(product={self.product_id}, user={self.user_id}, rating={self.rating})"


class ProductReviewComment(TimeStampedModel):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_review_comments")
    text = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"ReviewComment(review={self.review_id}, user={self.user_id})"


class ProductReviewPhoto(TimeStampedModel):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="photos")
    image_url = models.URLField()
    caption = models.CharField(max_length=160, blank=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return f"ReviewPhoto(review={self.review_id})"


class ProductReviewVote(TimeStampedModel):
    class Value(models.TextChoices):
        HELPFUL = "helpful", "Helpful"
        UNHELPFUL = "unhelpful", "Unhelpful"

    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_review_votes")
    value = models.CharField(max_length=16, choices=Value.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="unique_review_vote_per_user"),
        ]

    def __str__(self):
        return f"ReviewVote(review={self.review_id}, user={self.user_id}, value={self.value})"


class ProductQuestion(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="questions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_questions")
    question_text = models.TextField()
    answer_text = models.TextField(blank=True, default="")
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answered_product_questions",
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"ProductQuestion(product={self.product_id}, user={self.user_id})"
