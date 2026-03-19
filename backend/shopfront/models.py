from django.conf import settings
from django.db import models
from django.utils import timezone

from uuid import uuid4

from catalog.models import Product, Brand, Category
from core.models import TimeStampedModel


class FavoriteProduct(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_favorite_product_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="fav_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Favorite(user={self.user_id}, product={self.product_id})"


class SavedSearch(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=120)
    querystring = models.CharField(max_length=512)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="saved_search_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"SavedSearch(user={self.user_id}, name={self.name})"


class PersistentCart(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="persistent_cart",
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Persistent cart"
        verbose_name_plural = "Persistent carts"

    def __str__(self) -> str:
        return f"PersistentCart(user={self.user_id})"


class CategorySubscription(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="category_subscriptions",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subscribers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"],
                name="unique_category_subscription_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="cat_sub_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"CategorySubscription(user={self.user_id}, category={self.category_id})"


class BrandSubscription(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_subscriptions",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name="subscribers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "brand"],
                name="unique_brand_subscription_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="brand_sub_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"BrandSubscription(user={self.user_id}, brand={self.brand_id})"


class RecentlyViewedProduct(TimeStampedModel):
    updated_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recently_viewed_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="recently_viewed_by",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_recently_viewed_product_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="recent_view_user_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"RecentlyViewed(user={self.user_id}, product={self.product_id})"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields and set(update_fields) == {"updated_at"} and self.pk and self.updated_at:
            type(self).objects.filter(pk=self.pk).update(updated_at=self.updated_at)
            return
        if not update_fields or "updated_at" in update_fields:
            self.updated_at = timezone.now()
        return super().save(*args, **kwargs)


class SavedList(TimeStampedModel):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        FAVORITES = "favorites", "Favorites"
        ORDER = "order", "Order"
        CART = "cart", "Cart"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_lists",
    )
    name = models.CharField(max_length=140)
    description = models.CharField(max_length=255, blank=True)
    share_token = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    is_public = models.BooleanField(default=False)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="saved_list_user_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"SavedList(user={self.user_id}, name={self.name})"

    def ensure_share_token(self) -> str:
        if self.share_token:
            return self.share_token
        self.share_token = uuid4().hex
        return self.share_token

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.ensure_share_token()
        return super().save(*args, **kwargs)


class SavedListItem(TimeStampedModel):
    saved_list = models.ForeignKey(
        SavedList,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="saved_list_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=180, blank=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "-updated_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["saved_list", "product"],
                name="unique_saved_list_product",
            ),
        ]

    def __str__(self) -> str:
        return f"SavedListItem(list={self.saved_list_id}, product={self.product_id})"


class RecommendationEvent(TimeStampedModel):
    event = models.CharField(max_length=48, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_events",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    surface = models.CharField(max_length=32, blank=True, db_index=True)
    recommendation_source = models.CharField(max_length=64, blank=True, db_index=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_events",
    )
    seller_id = models.IntegerField(null=True, blank=True)
    brand_id = models.IntegerField(null=True, blank=True)
    category_id = models.IntegerField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["event", "-created_at"], name="recoevent_event_created_idx"),
            models.Index(fields=["surface", "-created_at"], name="recoevent_surface_created_idx"),
            models.Index(fields=["recommendation_source", "-created_at"], name="recoevent_src_created_idx"),
            models.Index(fields=["user", "-created_at"], name="recoevent_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationEvent(event={self.event}, product={self.product_id})"


class RecommendationProductAffinity(TimeStampedModel):
    class AffinityType(models.TextChoices):
        CO_PURCHASE = "co_purchase", "Co-purchase"
        SUBSTITUTE = "substitute", "Substitute"
        SIMILAR = "similar", "Similar"
        ACCESSORY = "accessory", "Accessory"

    source_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="outgoing_recommendation_affinities",
    )
    target_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="incoming_recommendation_affinities",
    )
    affinity_type = models.CharField(max_length=24, choices=AffinityType.choices, default=AffinityType.CO_PURCHASE)
    score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    orders_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-score", "-orders_count", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_product", "target_product", "affinity_type"],
                name="unique_reco_affinity_edge",
            ),
        ]
        indexes = [
            models.Index(fields=["source_product", "affinity_type", "-score"], name="recoaff_src_type_score_idx"),
            models.Index(fields=["target_product", "affinity_type", "-score"], name="recoaff_tgt_type_score_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationAffinity({self.source_product_id}->{self.target_product_id}, {self.affinity_type})"


class RecommendationPopularitySnapshot(TimeStampedModel):
    class ScopeType(models.TextChoices):
        GLOBAL = "global", "Global"
        CATEGORY = "category", "Category"
        BRAND = "brand", "Brand"
        SELLER = "seller", "Seller"

    scope_type = models.CharField(max_length=24, choices=ScopeType.choices, default=ScopeType.GLOBAL)
    scope_id = models.PositiveIntegerField(default=0)
    window = models.CharField(max_length=16, default="7d")
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="recommendation_popularity_snapshots",
    )
    score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["scope_type", "scope_id", "window", "-score", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scope_type", "scope_id", "window", "product"],
                name="unique_reco_pop_snapshot",
            ),
        ]
        indexes = [
            models.Index(fields=["scope_type", "scope_id", "window", "-score"], name="recopop_scope_score_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationPopularity(scope={self.scope_type}:{self.scope_id}, product={self.product_id})"


class RecommendationSet(TimeStampedModel):
    class ScopeType(models.TextChoices):
        GLOBAL = "global", "Global"
        USER = "user", "User"
        PRODUCT = "product", "Product"
        CATEGORY = "category", "Category"
        BRAND = "brand", "Brand"
        SELLER = "seller", "Seller"
        CART = "cart", "Cart"
        CHECKOUT = "checkout", "Checkout"
        SEARCH = "search", "Search"

    kind = models.CharField(max_length=48, db_index=True)
    scope_type = models.CharField(max_length=24, choices=ScopeType.choices, default=ScopeType.GLOBAL)
    scope_id = models.PositiveIntegerField(default=0, db_index=True)
    source = models.CharField(max_length=64, blank=True, db_index=True)
    product_ids = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-generated_at", "-id"]
        indexes = [
            models.Index(fields=["kind", "scope_type", "scope_id", "-generated_at"], name="recoset_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationSet(kind={self.kind}, scope={self.scope_type}:{self.scope_id})"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class RecommendationUserAffinity(TimeStampedModel):
    class Dimension(models.TextChoices):
        BRAND = "brand", "Brand"
        CATEGORY = "category", "Category"
        SELLER = "seller", "Seller"
        TAG = "tag", "Tag"
        PRICE_BAND = "price_band", "Price band"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_affinities",
    )
    dimension = models.CharField(max_length=24, choices=Dimension.choices, db_index=True)
    entity_id = models.PositiveIntegerField(default=0, db_index=True)
    entity_key = models.CharField(max_length=64, blank=True, db_index=True)
    score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    event_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["user_id", "dimension", "-score", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dimension", "entity_id", "entity_key"],
                name="unique_reco_user_affinity",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "dimension", "-score"], name="recouseraff_user_dim_idx"),
            models.Index(fields=["dimension", "entity_id", "-score"], name="recouseraff_dim_entity_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationUserAffinity(user={self.user_id}, {self.dimension}={self.entity_id or self.entity_key})"


class RecommendationReplenishmentProfile(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_replenishment_profiles",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="recommendation_replenishment_profiles",
    )
    first_ordered_at = models.DateTimeField(null=True, blank=True)
    last_ordered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    orders_count = models.PositiveIntegerField(default=0)
    quantity_total = models.PositiveIntegerField(default=0)
    expected_interval_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["user_id", "-score", "-last_ordered_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_reco_replenishment_profile",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-score", "-last_ordered_at"], name="recoreplen_user_score_idx"),
            models.Index(fields=["product", "-score"], name="recoreplen_product_score_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationReplenishmentProfile(user={self.user_id}, product={self.product_id})"


class RecommendationFeatureSnapshot(TimeStampedModel):
    class FeatureSet(models.TextChoices):
        USER_V1 = "user_v1", "User v1"
        PRODUCT_V1 = "product_v1", "Product v1"
        GLOBAL_V1 = "global_v1", "Global v1"

    class ScopeType(models.TextChoices):
        USER = "user", "User"
        PRODUCT = "product", "Product"
        GLOBAL = "global", "Global"

    feature_set = models.CharField(max_length=24, choices=FeatureSet.choices, db_index=True)
    scope_type = models.CharField(max_length=24, choices=ScopeType.choices, db_index=True)
    scope_id = models.PositiveIntegerField(default=0, db_index=True)
    surface = models.CharField(max_length=32, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["feature_set", "scope_type", "surface", "-generated_at", "-id"]
        indexes = [
            models.Index(fields=["feature_set", "scope_type", "scope_id", "surface", "-generated_at"], name="recofeat_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationFeatureSnapshot({self.feature_set}, {self.scope_type}:{self.scope_id}, {self.surface or 'all'})"


class RecommendationTrainingDataset(TimeStampedModel):
    surface = models.CharField(max_length=32, db_index=True)
    label_kind = models.CharField(max_length=24, default="purchase", db_index=True)
    version = models.CharField(max_length=40, db_index=True)
    window_start = models.DateTimeField(null=True, blank=True)
    window_end = models.DateTimeField(null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    positive_count = models.PositiveIntegerField(default=0)
    artifact_path = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["surface", "label_kind", "-created_at"], name="recods_surface_created_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationTrainingDataset(surface={self.surface}, label={self.label_kind}, version={self.version})"


class RecommendationModelArtifact(TimeStampedModel):
    class Status(models.TextChoices):
        TRAINING = "training", "Training"
        READY = "ready", "Ready"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=64, db_index=True, default="servio_ranker")
    surface = models.CharField(max_length=32, db_index=True)
    variant = models.CharField(max_length=24, db_index=True, default="ml_v1")
    algorithm = models.CharField(max_length=32, default="logistic_regression")
    version = models.CharField(max_length=40, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRAINING, db_index=True)
    feature_names = models.JSONField(default=list, blank=True)
    intercept = models.FloatField(default=0.0)
    weights = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    artifact_path = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    trained_on = models.ForeignKey(
        RecommendationTrainingDataset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="models",
    )
    activated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["surface", "variant", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["surface", "variant", "status", "-created_at"], name="recomodel_surface_idx"),
        ]

    def __str__(self) -> str:
        return f"RecommendationModelArtifact(surface={self.surface}, variant={self.variant}, version={self.version}, status={self.status})"
