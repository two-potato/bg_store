import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, override_settings

from catalog.models import Brand, Category, Product
from orders.models import Order, OrderItem
from shopfront.models import FavoriteProduct, RecommendationEvent, RecommendationFeatureSnapshot, RecentlyViewedProduct
from shopfront.recommendation.feature_store import refresh_recommendation_feature_snapshots
from shopfront.recommendation.ml import activate_model, active_model_for_surface, build_training_dataset, train_logistic_model, train_recommendation_model
from shopfront.recommendation.scoring_service import score_candidates_contract


pytestmark = pytest.mark.django_db


def _make_request():
    request = RequestFactory().get("/search/?q=syrup")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    request.user = AnonymousUser()
    return request


def _make_product(*, seller, brand, category, sku, name, price="100.00", stock_qty=10, is_promo=False):
    return Product.objects.create(
        seller=seller,
        brand=brand,
        category=category,
        sku=sku,
        name=name,
        price=price,
        stock_qty=stock_qty,
        is_promo=is_promo,
    )


def test_refresh_recommendation_feature_snapshots_builds_rows(user):
    seller = get_user_model().objects.create_user(username="ml_seller_features", password="pass")
    brand = Brand.objects.create(name="ML Brand Features")
    category = Category.objects.create(name="ML Category Features")
    product = _make_product(seller=seller, brand=brand, category=category, sku="55550001", name="Feature Product")
    FavoriteProduct.objects.create(user=user, product=product)
    RecentlyViewedProduct.objects.create(user=user, product=product)
    OrderItem.objects.create(
        order=Order.objects.create(placed_by=user, customer_type=Order.CustomerType.COMPANY),
        product=product,
        name=product.name,
        price=product.price,
        qty=1,
    )

    result = refresh_recommendation_feature_snapshots(user_limit=10, product_limit=10)

    assert result["users"] >= 1
    assert RecommendationFeatureSnapshot.objects.filter(
        feature_set=RecommendationFeatureSnapshot.FeatureSet.USER_V1,
        scope_type=RecommendationFeatureSnapshot.ScopeType.USER,
        scope_id=user.id,
    ).exists()
    assert RecommendationFeatureSnapshot.objects.filter(
        feature_set=RecommendationFeatureSnapshot.FeatureSet.PRODUCT_V1,
        scope_type=RecommendationFeatureSnapshot.ScopeType.PRODUCT,
        scope_id=product.id,
    ).exists()
    payload = RecommendationFeatureSnapshot.objects.filter(
        feature_set=RecommendationFeatureSnapshot.FeatureSet.PRODUCT_V1,
        scope_type=RecommendationFeatureSnapshot.ScopeType.PRODUCT,
        scope_id=product.id,
    ).latest("id").payload
    assert "rating_avg" in payload
    assert "conversion_score" in payload


@override_settings(RECOMMENDATION_ML_ENABLED=True, RECOMMENDATION_ML_ROLLOUT_PERCENT=100, RECOMMENDATION_ML_SURFACES=["catalog"])
def test_recommendation_ml_training_and_scoring_contract(user):
    seller = get_user_model().objects.create_user(username="ml_seller_train", password="pass")
    brand = Brand.objects.create(name="ML Brand Train")
    category = Category.objects.create(name="ML Category Train")
    positive = _make_product(seller=seller, brand=brand, category=category, sku="55550011", name="Positive", is_promo=True)
    negative = _make_product(seller=seller, brand=brand, category=category, sku="55550012", name="Negative")
    FavoriteProduct.objects.create(user=user, product=positive)
    RecentlyViewedProduct.objects.create(user=user, product=positive)
    refresh_recommendation_feature_snapshots(user_limit=10, product_limit=10)
    RecommendationEvent.objects.create(
        event="recommendation_impression",
        user=user,
        session_key="sess-ml-1",
        request_id="req-ml-1",
        surface="catalog",
        recommendation_source="search_recovery",
        product=positive,
        position=1,
    )
    RecommendationEvent.objects.create(
        event="purchase",
        user=user,
        session_key="sess-ml-1",
        request_id="req-ml-1",
        surface="catalog",
        recommendation_source="search_recovery",
        product=positive,
    )
    RecommendationEvent.objects.create(
        event="recommendation_impression",
        user=user,
        session_key="sess-ml-2",
        request_id="req-ml-2",
        surface="catalog",
        recommendation_source="search_recovery",
        product=negative,
        position=2,
    )

    dataset = build_training_dataset(surface="catalog", label_kind="purchase")
    model = train_logistic_model(dataset, epochs=5, learning_rate=0.01)
    activate_model(model)

    assert dataset.row_count == 2
    assert model.status == model.Status.ACTIVE
    assert active_model_for_surface("catalog") is not None

    request = _make_request()
    request.user = user
    request.session[SessionMiddleware.__name__ if False else "noop"] = True
    result, contract = score_candidates_contract(
        surface="catalog",
        candidate_ids=[positive.id, negative.id],
        user=user,
        request=request,
        source_name="search_recovery",
        experiment_variant="ml_v1",
        candidate_reason_codes={positive.id: ["trending"], negative.id: ["trending"]},
        candidate_sources={positive.id: ["global_popular"], negative.id: ["global_popular"]},
        limit=2,
    )

    assert contract.strategy == "ml_ranked"
    assert contract.model_version == model.version
    assert result.product_ids


def test_recommendation_dataset_tracks_richer_labels_and_auto_trainer(user):
    seller = get_user_model().objects.create_user(username="ml_seller_labels", password="pass")
    brand = Brand.objects.create(name="ML Brand Labels")
    category = Category.objects.create(name="ML Category Labels")
    product = _make_product(seller=seller, brand=brand, category=category, sku="55550021", name="Label Product", is_promo=True)
    refresh_recommendation_feature_snapshots(user_limit=10, product_limit=10)
    RecommendationEvent.objects.create(
        event="recommendation_impression",
        user=user,
        session_key="sess-ml-3",
        request_id="req-ml-3",
        surface="home",
        recommendation_source="personalized_home",
        product=product,
        position=1,
    )
    RecommendationEvent.objects.create(
        event="recommendation_click",
        user=user,
        session_key="sess-ml-3",
        request_id="req-ml-3",
        surface="home",
        recommendation_source="personalized_home",
        product=product,
    )
    RecommendationEvent.objects.create(
        event="add_to_cart",
        user=user,
        session_key="sess-ml-3",
        request_id="req-ml-3",
        surface="home",
        recommendation_source="personalized_home",
        product=product,
    )
    dataset = build_training_dataset(surface="home", label_kind="weighted_value")
    model = train_recommendation_model(dataset, trainer="auto", epochs=2)

    assert dataset.row_count == 1
    assert dataset.positive_count == 1
    assert "weighted_value" in dataset.metadata["available_labels"]
    assert model.status in {model.Status.READY, model.Status.FAILED}
    assert model.algorithm in {"logistic_regression", "gradient_boosting"}
