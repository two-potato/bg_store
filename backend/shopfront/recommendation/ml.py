from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from catalog.models import Product

from ..models import RecommendationEvent, RecommendationModelArtifact, RecommendationTrainingDataset
from .feature_store import FEATURE_NAMES_V1, product_feature_payload, user_feature_payload
from .ranker import RankedRecommendationResult, select_ranked_product_ids

try:
    from sklearn.ensemble import GradientBoostingClassifier
except Exception:  # pragma: no cover - optional dependency
    GradientBoostingClassifier = None


MODEL_FEATURES = list(FEATURE_NAMES_V1)
SURFACE_MODEL_MAP = {
    "home": "home_for_you",
    "catalog": "search_recovery",
    "pdp": "product_similar",
    "cart": "cart_cross_sell",
    "checkout": "checkout_cross_sell",
}


@dataclass
class TrainingRow:
    feature_map: dict[str, float]
    labels: dict[str, int]
    meta: dict[str, object]


def available_trainers() -> list[str]:
    """Handle available trainers."""
    trainers = ["logistic_regression"]
    if GradientBoostingClassifier is not None:
        trainers.append("gradient_boosting")
    return trainers


def _artifact_root(kind: str) -> Path:
    """Internal helper for artifact root."""
    root = Path(getattr(settings, "BASE_DIR", Path.cwd())) / ".artifacts" / kind
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sigmoid(value: float) -> float:
    """Internal helper for sigmoid."""
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _safe_float(value) -> float:
    """Internal helper for safe float."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _one_hot_surface(surface: str) -> dict[str, float]:
    """Internal helper for one hot surface."""
    return {
        "context_surface_home": 1.0 if surface == "home" else 0.0,
        "context_surface_catalog": 1.0 if surface == "catalog" else 0.0,
        "context_surface_pdp": 1.0 if surface == "pdp" else 0.0,
        "context_surface_cart": 1.0 if surface == "cart" else 0.0,
        "context_surface_checkout": 1.0 if surface == "checkout" else 0.0,
    }


def build_feature_map(
    *,
    surface: str,
    product: Product,
    user,
    position: int = 0,
    search_query: str = "",
    cart_size: int = 0,
    source_product: Product | None = None,
    candidate_sources: Iterable[str] | None = None,
    reason_codes: Iterable[str] | None = None,
) -> dict[str, float]:
    """Build feature map."""
    user_payload = user_feature_payload(user)
    product_payload = product_feature_payload(product)
    affinity_scores = user_payload.get("affinity_scores", {}) or {}
    candidate_sources = list(candidate_sources or [])
    reason_codes = list(reason_codes or [])
    query_text = str(search_query or "").strip()
    tag_scores = affinity_scores.get("tag", {}) or {}
    tag_affinity_score = 0.0
    for tag_id in product.tags.values_list("id", flat=True)[:12]:
        tag_affinity_score = max(tag_affinity_score, _safe_float(tag_scores.get(str(int(tag_id or 0)))))
    feature_map = {
        "user_is_authenticated": 1.0 if getattr(user, "is_authenticated", False) else 0.0,
        "user_recent_views_count": _safe_float(user_payload.get("user_recent_views_count")),
        "user_favorites_count": _safe_float(user_payload.get("user_favorites_count")),
        "user_orders_count": _safe_float(user_payload.get("user_orders_count")),
        "user_replenishment_count": _safe_float(user_payload.get("user_replenishment_count")),
        "user_brand_subscriptions_count": _safe_float(user_payload.get("user_brand_subscriptions_count")),
        "user_category_subscriptions_count": _safe_float(user_payload.get("user_category_subscriptions_count")),
        "user_saved_searches_count": _safe_float(user_payload.get("user_saved_searches_count")),
        "user_cart_items_count": _safe_float(user_payload.get("user_cart_items_count")),
        "user_affinity_brand_score": _safe_float((affinity_scores.get("brand", {}) or {}).get(str(int(product.brand_id or 0)))),
        "user_affinity_category_score": _safe_float((affinity_scores.get("category", {}) or {}).get(str(int(product.category_id or 0)))),
        "user_affinity_seller_score": _safe_float((affinity_scores.get("seller", {}) or {}).get(str(int(product.seller_id or 0)))),
        "user_affinity_tag_score": tag_affinity_score,
        "user_price_band_entry": 1.0 if user_payload.get("price_band") == "entry" else 0.0,
        "user_price_band_mid": 1.0 if user_payload.get("price_band") == "mid" else 0.0,
        "user_price_band_premium": 1.0 if user_payload.get("price_band") == "premium" else 0.0,
        "product_is_new": 1.0 if product_payload.get("is_new") else 0.0,
        "product_is_promo": 1.0 if product_payload.get("is_promo") else 0.0,
        "product_in_stock": 1.0 if product_payload.get("in_stock") else 0.0,
        "product_fast_delivery": 1.0 if product_payload.get("fast_delivery") else 0.0,
        "product_low_moq": 1.0 if product_payload.get("low_moq") else 0.0,
        "product_price_value": _safe_float(product_payload.get("price_value")),
        "product_rating_avg": _safe_float(product_payload.get("rating_avg")),
        "product_rating_count": _safe_float(product_payload.get("rating_count")),
        "product_review_photo_count": _safe_float(product_payload.get("review_photo_count")),
        "product_review_verified_ratio": _safe_float(product_payload.get("review_verified_ratio")),
        "product_global_popularity_7d": _safe_float(product_payload.get("global_popularity_7d")),
        "product_global_popularity_30d": _safe_float(product_payload.get("global_popularity_30d")),
        "product_category_popularity_7d": _safe_float(product_payload.get("category_popularity_7d")),
        "product_brand_popularity_7d": _safe_float(product_payload.get("brand_popularity_7d")),
        "product_seller_popularity_7d": _safe_float(product_payload.get("seller_popularity_7d")),
        "product_similar_edge_score": _safe_float(product_payload.get("similar_edge_score")),
        "product_copurchase_edge_score": _safe_float(product_payload.get("copurchase_edge_score")),
        "product_conversion_score": _safe_float(product_payload.get("conversion_score")),
        "product_purchase_count_30d": _safe_float(product_payload.get("purchase_count_30d")),
        "product_view_count_7d": _safe_float(product_payload.get("view_count_7d")),
        "product_add_to_cart_count_7d": _safe_float(product_payload.get("add_to_cart_count_7d")),
        "product_seller_rating_avg": _safe_float(product_payload.get("seller_rating_avg")),
        "product_seller_review_count": _safe_float(product_payload.get("seller_review_count")),
        "context_position": float(max(0, int(position or 0))),
        "context_position_inverse": 1.0 / float(max(1, int(position or 0))),
        "context_has_query": 1.0 if query_text else 0.0,
        "context_query_length": float(len(query_text)),
        "context_cart_size": float(max(0, int(cart_size or 0))),
        "context_source_same_brand": 1.0 if source_product is not None and product.brand_id and product.brand_id == source_product.brand_id else 0.0,
        "context_source_same_category": 1.0 if source_product is not None and product.category_id and product.category_id == source_product.category_id else 0.0,
        "context_source_same_seller": 1.0 if source_product is not None and product.seller_id and product.seller_id == source_product.seller_id else 0.0,
        "context_candidate_source_count": float(len(candidate_sources)),
        "context_reason_count": float(len(reason_codes)),
        "context_is_anonymous": 0.0 if getattr(user, "is_authenticated", False) else 1.0,
    }
    feature_map.update(_one_hot_surface(surface))
    for feature_name in MODEL_FEATURES:
        feature_map.setdefault(feature_name, 0.0)
    return feature_map


def _label_for_event(impression: RecommendationEvent, by_key: dict[tuple[str, str, int], set[str]]) -> dict[str, int]:
    """Internal helper for label for event."""
    key = (str(impression.request_id or impression.session_key or ""), str(impression.surface or ""), int(impression.product_id or 0))
    events = by_key.get(key, set())
    click = 1 if "recommendation_click" in events else 0
    add_to_cart = 1 if "add_to_cart" in events else 0
    purchase = 1 if "purchase" in events else 0
    reorder = 1 if purchase and str(impression.recommendation_source or "").startswith("home_replenishment") else 0
    strong_engagement = 1 if purchase or add_to_cart else 0
    qualified_click = 1 if click and not add_to_cart and not purchase else 0
    revenue_event = 1 if purchase or reorder else 0
    weighted_value = min(10, click + add_to_cart * 3 + purchase * 6 + reorder * 8)
    return {
        "click": click,
        "add_to_cart": add_to_cart,
        "purchase": purchase,
        "reorder": reorder,
        "strong_engagement": strong_engagement,
        "qualified_click": qualified_click,
        "revenue_event": revenue_event,
        "weighted_value": weighted_value,
        "blended": 1 if purchase or add_to_cart or click else 0,
    }


def build_training_rows(*, surface: str, since=None, until=None) -> list[TrainingRow]:
    """Build training rows."""
    until = until or timezone.now()
    since = since or (until - timedelta(days=30))
    impressions = list(
        RecommendationEvent.objects.filter(
            event="recommendation_impression",
            surface=surface,
            created_at__gte=since,
            created_at__lte=until,
            product_id__isnull=False,
        ).select_related("product", "user")
    )
    key_rows = defaultdict(set)
    followup_rows = RecommendationEvent.objects.filter(
        event__in=["recommendation_click", "add_to_cart", "purchase"],
        created_at__gte=since,
        created_at__lte=until + timedelta(days=1),
        product_id__isnull=False,
    ).values_list("request_id", "session_key", "surface", "product_id", "event")
    for request_id, session_key, row_surface, product_id, event_name in followup_rows:
        key = (str(request_id or session_key or ""), str(row_surface or ""), int(product_id or 0))
        key_rows[key].add(str(event_name or ""))
    rows: list[TrainingRow] = []
    for impression in impressions:
        product = getattr(impression, "product", None)
        if product is None:
            continue
        payload = dict(impression.payload or {})
        feature_map = build_feature_map(
            surface=surface,
            product=product,
            user=getattr(impression, "user", None),
            position=int(impression.position or 0),
            search_query=str(payload.get("search_query") or payload.get("search_term") or ""),
            cart_size=int(payload.get("cart_size") or 0),
            candidate_sources=payload.get("recommendation_candidate_sources") or [],
            reason_codes=payload.get("recommendation_reason_codes") or [],
        )
        labels = _label_for_event(impression, key_rows)
        rows.append(
            TrainingRow(
                feature_map=feature_map,
                labels=labels,
                meta={
                    "event_id": impression.id,
                    "request_id": impression.request_id or impression.session_key or "",
                    "surface": surface,
                    "product_id": product.id,
                    "position": int(impression.position or 0),
                    "recommendation_source": impression.recommendation_source or "",
                },
            )
        )
    return rows


def _write_dataset_artifact(*, rows: list[TrainingRow], surface: str, label_kind: str, version: str) -> tuple[str, int, int]:
    """Internal helper for write dataset artifact."""
    root = _artifact_root("recommendation_datasets")
    path = root / f"{surface}-{label_kind}-{version}.jsonl"
    positive_count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            label_value = float(row.labels.get(label_kind, 0))
            positive_count += int(label_value > 0)
            handle.write(
                json.dumps(
                    {
                        "surface": surface,
                        "label_kind": label_kind,
                        "label": label_value,
                        "labels": row.labels,
                        "features": row.feature_map,
                        "meta": row.meta,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return str(path), len(rows), positive_count


def build_training_dataset(*, surface: str, label_kind: str = "purchase", since=None, until=None) -> RecommendationTrainingDataset:
    """Build training dataset."""
    version = timezone.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
    rows = build_training_rows(surface=surface, since=since, until=until)
    artifact_path, row_count, positive_count = _write_dataset_artifact(rows=rows, surface=surface, label_kind=label_kind, version=version)
    return RecommendationTrainingDataset.objects.create(
        surface=surface,
        label_kind=label_kind,
        version=version,
        window_start=since,
        window_end=until or timezone.now(),
        row_count=row_count,
        positive_count=positive_count,
        artifact_path=artifact_path,
        metadata={
            "feature_names": MODEL_FEATURES,
            "available_labels": ["click", "qualified_click", "add_to_cart", "purchase", "reorder", "strong_engagement", "revenue_event", "weighted_value", "blended"],
        },
    )


def _read_dataset(dataset: RecommendationTrainingDataset) -> list[tuple[dict[str, float], float, dict, dict]]:
    """Internal helper for read dataset."""
    rows: list[tuple[dict[str, float], float, dict, dict]] = []
    path = Path(dataset.artifact_path)
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            rows.append(
                (
                    dict(payload.get("features") or {}),
                    float(payload.get("label") or 0),
                    dict(payload.get("meta") or {}),
                    dict(payload.get("labels") or {}),
                )
            )
    return rows


def _dot(weights: dict[str, float], features: dict[str, float], intercept: float) -> float:
    """Internal helper for dot."""
    total = intercept
    for feature_name, value in features.items():
        total += weights.get(feature_name, 0.0) * float(value or 0.0)
    return total


def train_logistic_model(dataset: RecommendationTrainingDataset, *, epochs: int = 20, learning_rate: float = 0.001, l2: float = 0.0001) -> RecommendationModelArtifact:
    """Train logistic model."""
    rows = _read_dataset(dataset)
    weights = {feature_name: 0.0 for feature_name in MODEL_FEATURES}
    intercept = 0.0
    if not rows:
        return RecommendationModelArtifact.objects.create(
            surface=dataset.surface,
            version=dataset.version,
            status=RecommendationModelArtifact.Status.FAILED,
            feature_names=MODEL_FEATURES,
            metrics={"error": "empty_dataset"},
            trained_on=dataset,
        )
    for _epoch in range(max(1, int(epochs))):
        for features, label, _meta, _labels in rows:
            binary_label = 1.0 if float(label) > 0 else 0.0
            prediction = _sigmoid(_dot(weights, features, intercept))
            error = binary_label - prediction
            intercept += learning_rate * error
            for feature_name in MODEL_FEATURES:
                value = float(features.get(feature_name, 0.0))
                weights[feature_name] += learning_rate * (error * value - l2 * weights[feature_name])
    metrics = evaluate_model_rows(rows, weights=weights, intercept=intercept)
    model = RecommendationModelArtifact.objects.create(
        surface=dataset.surface,
        version=dataset.version,
        status=RecommendationModelArtifact.Status.READY,
        algorithm="logistic_regression",
        feature_names=MODEL_FEATURES,
        intercept=intercept,
        weights=weights,
        metrics=metrics,
        trained_on=dataset,
        artifact_path=_write_model_artifact(surface=dataset.surface, version=dataset.version, weights=weights, intercept=intercept, metrics=metrics),
        metadata={"label_kind": dataset.label_kind, "trainer": "logistic_regression"},
    )
    return model


def train_gradient_boosting_model(
    dataset: RecommendationTrainingDataset,
    *,
    random_state: int = 42,
    n_estimators: int = 120,
    learning_rate: float = 0.05,
    max_depth: int = 3,
) -> RecommendationModelArtifact:
    """Train gradient boosting model."""
    if GradientBoostingClassifier is None:
        return RecommendationModelArtifact.objects.create(
            surface=dataset.surface,
            version=dataset.version,
            status=RecommendationModelArtifact.Status.FAILED,
            algorithm="gradient_boosting",
            feature_names=MODEL_FEATURES,
            metrics={"error": "trainer_unavailable", "trainer": "gradient_boosting"},
            trained_on=dataset,
        )
    rows = _read_dataset(dataset)
    if not rows:
        return RecommendationModelArtifact.objects.create(
            surface=dataset.surface,
            version=dataset.version,
            status=RecommendationModelArtifact.Status.FAILED,
            algorithm="gradient_boosting",
            feature_names=MODEL_FEATURES,
            metrics={"error": "empty_dataset"},
            trained_on=dataset,
        )
    feature_matrix = [[float(features.get(name, 0.0)) for name in MODEL_FEATURES] for features, _label, _meta, _labels in rows]
    labels = [1 if float(label) > 0 else 0 for _features, label, _meta, _labels in rows]
    if len(set(labels)) < 2:
        return RecommendationModelArtifact.objects.create(
            surface=dataset.surface,
            version=dataset.version,
            status=RecommendationModelArtifact.Status.FAILED,
            algorithm="gradient_boosting",
            feature_names=MODEL_FEATURES,
            metrics={"error": "single_class_dataset"},
            trained_on=dataset,
        )
    model_impl = GradientBoostingClassifier(
        random_state=random_state,
        n_estimators=max(20, int(n_estimators or 120)),
        learning_rate=max(0.001, float(learning_rate or 0.05)),
        max_depth=max(1, int(max_depth or 3)),
    )
    model_impl.fit(feature_matrix, labels)
    probabilities = [float(row[1]) for row in model_impl.predict_proba(feature_matrix)]
    metrics = evaluate_scored_rows(rows, scores=probabilities)
    tree_payload = {
        "params": {
            "random_state": random_state,
            "n_estimators": int(n_estimators or 120),
            "learning_rate": float(learning_rate or 0.05),
            "max_depth": int(max_depth or 3),
        },
        "estimators": _serialize_gradient_boosting(model_impl),
        "classes": [int(value) for value in getattr(model_impl, "classes_", [0, 1])],
    }
    model = RecommendationModelArtifact.objects.create(
        surface=dataset.surface,
        version=dataset.version,
        status=RecommendationModelArtifact.Status.READY,
        algorithm="gradient_boosting",
        feature_names=MODEL_FEATURES,
        intercept=0.0,
        weights={},
        metrics=metrics,
        trained_on=dataset,
        artifact_path=_write_tree_model_artifact(
            surface=dataset.surface,
            version=dataset.version,
            artifact_payload=tree_payload,
            metrics=metrics,
        ),
        metadata={"label_kind": dataset.label_kind, "trainer": "gradient_boosting", "tree_payload": tree_payload},
    )
    return model


def train_recommendation_model(dataset: RecommendationTrainingDataset, *, trainer: str = "auto", **kwargs) -> RecommendationModelArtifact:
    """Train recommendation model."""
    trainer_code = str(trainer or "auto").strip().lower()
    if trainer_code == "auto":
        trainer_code = "gradient_boosting" if GradientBoostingClassifier is not None else "logistic_regression"
    if trainer_code == "gradient_boosting":
        return train_gradient_boosting_model(
            dataset,
            random_state=int(kwargs.get("random_state", 42) or 42),
            n_estimators=int(kwargs.get("n_estimators", 120) or 120),
            learning_rate=float(kwargs.get("learning_rate", 0.05) or 0.05),
            max_depth=int(kwargs.get("max_depth", 3) or 3),
        )
    return train_logistic_model(
        dataset,
        epochs=int(kwargs.get("epochs", 20) or 20),
        learning_rate=float(kwargs.get("learning_rate", 0.001) or 0.001),
        l2=float(kwargs.get("l2", 0.0001) or 0.0001),
    )


def _write_model_artifact(*, surface: str, version: str, weights: dict[str, float], intercept: float, metrics: dict) -> str:
    """Internal helper for write model artifact."""
    root = _artifact_root("recommendation_models")
    path = root / f"{surface}-{version}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "surface": surface,
                "version": version,
                "feature_names": MODEL_FEATURES,
                "intercept": intercept,
                "weights": weights,
                "metrics": metrics,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    return str(path)


def _write_tree_model_artifact(*, surface: str, version: str, artifact_payload: dict, metrics: dict) -> str:
    """Internal helper for write tree model artifact."""
    root = _artifact_root("recommendation_models")
    path = root / f"{surface}-{version}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "surface": surface,
                "version": version,
                "feature_names": MODEL_FEATURES,
                "algorithm": "gradient_boosting",
                "tree_model": artifact_payload,
                "metrics": metrics,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    return str(path)


def _serialize_gradient_boosting(model_impl) -> list[dict]:
    """Internal helper for serialize gradient boosting."""
    rows: list[dict] = []
    estimators = getattr(model_impl, "estimators_", None)
    if estimators is None:
        return rows
    for stage, estimator_group in enumerate(estimators.tolist() if hasattr(estimators, "tolist") else estimators):
        estimator = estimator_group[0] if isinstance(estimator_group, (list, tuple)) else estimator_group
        tree = getattr(estimator, "tree_", None)
        if tree is None:
            continue
        rows.append(
            {
                "stage": int(stage),
                "children_left": [int(value) for value in tree.children_left.tolist()],
                "children_right": [int(value) for value in tree.children_right.tolist()],
                "feature": [int(value) for value in tree.feature.tolist()],
                "threshold": [float(value) for value in tree.threshold.tolist()],
                "value": [float(value[0][0]) for value in tree.value.tolist()],
            }
        )
    return rows


def _predict_gradient_boosting_score(model: RecommendationModelArtifact, features: dict[str, float]) -> float:
    """Internal helper for predict gradient boosting score."""
    tree_model = dict((model.metadata or {}).get("tree_payload") or {})
    params = dict(tree_model.get("params") or {})
    estimators = list(tree_model.get("estimators") or [])
    learning_rate = float(params.get("learning_rate") or 0.05)
    raw_score = 0.0
    for estimator in estimators:
        node = 0
        children_left = list(estimator.get("children_left") or [])
        children_right = list(estimator.get("children_right") or [])
        feature_indexes = list(estimator.get("feature") or [])
        thresholds = list(estimator.get("threshold") or [])
        values = list(estimator.get("value") or [])
        while node < len(children_left):
            left = int(children_left[node])
            right = int(children_right[node])
            if left == -1 and right == -1:
                raw_score += learning_rate * float(values[node] if node < len(values) else 0.0)
                break
            feature_index = int(feature_indexes[node]) if node < len(feature_indexes) else -2
            threshold = float(thresholds[node]) if node < len(thresholds) else 0.0
            feature_name = MODEL_FEATURES[feature_index] if 0 <= feature_index < len(MODEL_FEATURES) else ""
            feature_value = float(features.get(feature_name, 0.0))
            node = left if feature_value <= threshold else right
            if node < 0:
                break
    return _sigmoid(raw_score)


def evaluate_model_rows(rows: list[tuple[dict[str, float], float, dict, dict]], *, weights: dict[str, float], intercept: float) -> dict[str, float]:
    """Handle evaluate model rows."""
    scores = [_sigmoid(_dot(weights, features, intercept)) for features, _label, _meta, _labels in rows]
    return evaluate_scored_rows(rows, scores=scores)


def evaluate_scored_rows(rows: list[tuple[dict[str, float], float, dict, dict]], *, scores: list[float]) -> dict[str, float]:
    """Handle evaluate scored rows."""
    if not rows:
        return {"row_count": 0, "logloss": 0.0, "auc": 0.0, "precision_at_5": 0.0}
    scored = []
    logloss = 0.0
    grouped: dict[str, list[tuple[float, int]]] = defaultdict(list)
    positives = 0
    negatives = 0
    blended_gain = 0.0
    purchase_positives = 0
    reorder_positives = 0
    mrr_values = []
    ndcg_values = []
    recall_values = []
    for index, row in enumerate(rows):
        _features, label, meta, labels = row
        prediction = float(scores[index] if index < len(scores) else 0.0)
        binary_label = 1 if float(label) > 0 else 0
        label_float = float(binary_label)
        positives += int(binary_label > 0)
        negatives += int(binary_label <= 0)
        purchase_positives += int(float(labels.get("purchase") or 0) > 0)
        reorder_positives += int(float(labels.get("reorder") or 0) > 0)
        blended_gain += float(labels.get("weighted_value") or 0)
        logloss += -(label_float * math.log(max(prediction, 1e-9)) + (1.0 - label_float) * math.log(max(1e-9, 1.0 - prediction)))
        scored.append((prediction, binary_label))
        grouped[str(meta.get("request_id") or meta.get("event_id") or "")].append((prediction, binary_label))
    scored.sort(key=lambda item: item[0], reverse=True)
    rank_sum = 0.0
    pos_seen = 0
    for index, (_score, label) in enumerate(scored, start=1):
        if label > 0:
            pos_seen += 1
            rank_sum += index
    auc = 0.0
    if positives and negatives:
        auc = (rank_sum - (positives * (positives + 1) / 2.0)) / float(positives * negatives)
    precision_values = []
    for items in grouped.values():
        if not items:
            continue
        top_items = sorted(items, key=lambda item: item[0], reverse=True)[:5]
        precision_values.append(sum(label for _score, label in top_items) / float(len(top_items)))
        ranked_items = sorted(items, key=lambda item: item[0], reverse=True)[:10]
        reciprocal_rank = 0.0
        dcg = 0.0
        total_positives = sum(label for _score, label in items)
        for rank_index, (_score, label) in enumerate(ranked_items, start=1):
            if label > 0 and reciprocal_rank == 0.0:
                reciprocal_rank = 1.0 / float(rank_index)
            dcg += ((2 ** label) - 1) / math.log2(rank_index + 1)
        ideal_labels = sorted((label for _score, label in items), reverse=True)[:10]
        ideal_dcg = 0.0
        for rank_index, label in enumerate(ideal_labels, start=1):
            ideal_dcg += ((2 ** label) - 1) / math.log2(rank_index + 1)
        mrr_values.append(reciprocal_rank)
        ndcg_values.append(dcg / ideal_dcg if ideal_dcg > 0 else 0.0)
        recall_values.append(sum(label for _score, label in ranked_items) / float(max(1, total_positives)))
    return {
        "row_count": float(len(rows)),
        "positive_count": float(positives),
        "positive_rate": float(positives / max(1, len(rows))),
        "purchase_positive_count": float(purchase_positives),
        "reorder_positive_count": float(reorder_positives),
        "weighted_gain_total": float(blended_gain),
        "logloss": float(logloss / max(1, len(rows))),
        "auc": float(auc),
        "precision_at_5": float(sum(precision_values) / max(1, len(precision_values))),
        "mrr_at_10": float(sum(mrr_values) / max(1, len(mrr_values))),
        "ndcg_at_10": float(sum(ndcg_values) / max(1, len(ndcg_values))),
        "recall_at_10": float(sum(recall_values) / max(1, len(recall_values))),
    }


def activate_model(model: RecommendationModelArtifact) -> RecommendationModelArtifact:
    """Handle activate model."""
    RecommendationModelArtifact.objects.filter(surface=model.surface, variant=model.variant, status=RecommendationModelArtifact.Status.ACTIVE).exclude(pk=model.pk).update(
        status=RecommendationModelArtifact.Status.RETIRED
    )
    model.status = RecommendationModelArtifact.Status.ACTIVE
    model.activated_at = timezone.now()
    model.save(update_fields=["status", "activated_at", "updated_at"])
    return model


def active_model_for_surface(surface: str, *, variant: str = "ml_v1") -> RecommendationModelArtifact | None:
    """Handle active model for surface."""
    return (
        RecommendationModelArtifact.objects.filter(
            surface=surface,
            variant=variant,
            status=RecommendationModelArtifact.Status.ACTIVE,
        )
        .order_by("-activated_at", "-created_at", "-id")
        .first()
    )


def score_candidates_with_model(
    *,
    surface: str,
    model: RecommendationModelArtifact,
    candidate_ids: list[int],
    user,
    request,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    candidate_reason_codes: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    candidate_sources: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    blocked_product_ids: set[int] | None = None,
    limit: int = 8,
) -> RankedRecommendationResult:
    """Score candidates with model."""
    candidate_reason_codes = candidate_reason_codes or {}
    candidate_sources = candidate_sources or {}
    products = {
        product.id: product
        for product in Product.objects.filter(id__in=candidate_ids).select_related("brand", "category", "seller")
    }
    cart_size = len(cart_product_ids or set())
    search_query = ""
    if request is not None:
        try:
            search_query = str(request.GET.get("q") or "")
        except Exception:
            search_query = ""
    scores_by_product: dict[int, float] = {}
    multi_objective_breakdown: dict[int, dict[str, float]] = {}
    for position, product_id in enumerate(candidate_ids, start=1):
        product = products.get(product_id)
        if product is None:
            continue
        feature_map = build_feature_map(
            surface=surface,
            product=product,
            user=user,
            position=position,
            search_query=search_query,
            cart_size=cart_size,
            source_product=source_product,
            candidate_sources=candidate_sources.get(product_id) or [],
            reason_codes=candidate_reason_codes.get(product_id) or [],
        )
        primary_score = (
            _predict_gradient_boosting_score(model, feature_map)
            if str(model.algorithm or "") == "gradient_boosting"
            else _sigmoid(_dot({key: _safe_float(value) for key, value in dict(model.weights or {}).items()}, feature_map, _safe_float(model.intercept)))
        )
        product_payload = product_feature_payload(product)
        engagement_score = min(
            1.0,
            (
                _safe_float(product_payload.get("view_count_7d")) * 0.01
                + _safe_float(product_payload.get("add_to_cart_count_7d")) * 0.05
                + _safe_float(product_payload.get("rating_avg")) * 0.06
            ),
        )
        conversion_score = min(
            1.0,
            (
                _safe_float(product_payload.get("purchase_count_30d")) * 0.05
                + _safe_float(product_payload.get("conversion_score")) * 0.01
                + _safe_float(product_payload.get("review_verified_ratio")) * 0.35
            ),
        )
        quality_score = min(
            1.0,
            (
                _safe_float(product_payload.get("seller_rating_avg")) * 0.12
                + _safe_float(product_payload.get("rating_avg")) * 0.12
                + (0.1 if product_payload.get("in_stock") else 0.0)
                + (0.05 if product_payload.get("fast_delivery") else 0.0)
            ),
        )
        final_score = (primary_score * 0.65) + (conversion_score * 0.2) + (engagement_score * 0.1) + (quality_score * 0.05)
        scores_by_product[product_id] = final_score
        multi_objective_breakdown[product_id] = {
            "primary_score": round(primary_score, 6),
            "conversion_score": round(conversion_score, 6),
            "engagement_score": round(engagement_score, 6),
            "quality_score": round(quality_score, 6),
            "final_score": round(final_score, 6),
        }
    ordered = [product_id for product_id, _score in sorted(scores_by_product.items(), key=lambda item: (-item[1], candidate_ids.index(item[0])))]
    selected = select_ranked_product_ids(
        ordered,
        products_by_id=products,
        blocked_product_ids=blocked_product_ids,
        require_in_stock=True,
        max_per_seller=2 if surface in {"home", "catalog", "checkout"} else 3,
        max_per_brand=2 if surface in {"home", "catalog"} else None,
        max_per_category=3 if surface in {"home", "catalog"} else None,
        limit=limit,
    )
    return RankedRecommendationResult(
        product_ids=selected,
        scores_by_product={pid: scores_by_product.get(pid, 0.0) for pid in selected},
        reason_codes_by_product={
            pid: sorted({str(value) for value in (candidate_reason_codes.get(pid) or []) if str(value).strip()})
            for pid in selected
        },
        candidate_sources_by_product={
            pid: sorted({str(value) for value in (candidate_sources.get(pid) or []) if str(value).strip()})
            for pid in selected
        },
        metadata={"strategy": "ml_ranked", "model_version": model.version, "multi_objective_scores": multi_objective_breakdown},
    )
