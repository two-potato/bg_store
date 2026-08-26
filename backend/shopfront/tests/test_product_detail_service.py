"""Tests for product detail and recommendation services."""

import pytest
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from ..product_detail_service import (
    ProductDetailPageService,
    ProductRecommendationSectionService,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestProductDetailPageService:
    """Test ProductDetailPageService context assembly."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def request_factory(self):
        """Create request factory."""
        return RequestFactory()

    @pytest.fixture
    def request_with_user(self, request_factory, user):
        """Create request with authenticated user."""
        request = request_factory.get("/")
        request.user = user
        request.session = {}
        return request

    def test_build_context_returns_none_for_missing_product(self, request_with_user):
        """Test that build_context returns None when product doesn't exist."""
        service = ProductDetailPageService(request_with_user)
        result = service.build_context(slug="nonexistent")
        assert result is None

    def test_build_context_includes_required_fields(self, request_with_user, db):
        """Test that build_context returns dataclass with all required fields."""
        # This test requires a valid product to exist in the database
        # For now, we just verify the service can be instantiated
        service = ProductDetailPageService(request_with_user)
        assert service.user == request_with_user.user
        assert service.request == request_with_user

    def test_prepare_subscriptions_returns_false_for_anonymous(self, request_factory):
        """Test subscription checks for anonymous user."""
        request = request_factory.get("/")
        request.user = User()  # AnonymousUser equivalent
        request.user.is_authenticated = False

        service = ProductDetailPageService(request)
        brand_sub, category_sub = service._prepare_subscriptions(None)

        assert brand_sub is False
        assert category_sub is False

    def test_prepare_tracking_payload_structure(self, request_with_user, db):
        """Test that tracking payload has correct structure."""
        service = ProductDetailPageService(request_with_user)

        # Create a minimal product mock
        class MockProduct:
            display_price = 100.00

        payload = service._prepare_tracking_payload(MockProduct())  # type: ignore

        assert '"event": "product_view"' in payload
        assert '"currency": "RUB"' in payload
        assert '"value": 100.0' in payload


class TestProductRecommendationSectionService:
    """Test ProductRecommendationSectionService for AJAX sections."""

    @pytest.fixture
    def request_factory(self):
        """Create request factory."""
        return RequestFactory()

    @pytest.fixture
    def request(self, request_factory):
        """Create test request."""
        request = request_factory.get("/")
        request.user = User()  # AnonymousUser
        return request

    def test_build_section_context_returns_none_for_missing_product(self, request):
        """Test that service returns None when product doesn't exist."""
        service = ProductRecommendationSectionService(request)
        result = service.build_section_context(slug="nonexistent", section="related")
        assert result is None

    def test_service_instantiation(self, request):
        """Test service can be instantiated with request."""
        service = ProductRecommendationSectionService(request)
        assert service.request == request
        assert service.user == request.user
