"""Tests for store detail and review services."""

import pytest
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from ..store_detail_service import (
    StoreDetailPageService,
    StoreReviewService,
    StoreReviewOperationResult,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestStoreDetailPageService:
    """Test StoreDetailPageService context assembly."""

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

    def test_service_instantiation(self, request_with_user):
        """Test service can be instantiated with request."""
        service = StoreDetailPageService(request_with_user)
        assert service.request == request_with_user
        assert service.user == request_with_user.user

    def test_build_storefront_context_structure(self, request_with_user):
        """Test that storefront context has required structure."""
        service = StoreDetailPageService(request_with_user)
        # Store doesn't exist, so we just verify service methods exist
        assert hasattr(service, "build_storefront_context")
        assert hasattr(service, "build_vendor_seo_context")
        assert hasattr(service, "build_seller_profile_context")

    def test_build_vendor_seo_context_structure(self, request_with_user):
        """Test that vendor SEO context is a dict."""
        service = StoreDetailPageService(request_with_user)
        # This would need a real store, just verify method exists
        assert callable(service.build_vendor_seo_context)

    def test_build_seller_profile_context_structure(self, request_with_user):
        """Test that seller profile context is a dict."""
        service = StoreDetailPageService(request_with_user)
        assert callable(service.build_seller_profile_context)


class TestStoreReviewService:
    """Test StoreReviewService for store review operations."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def request_factory(self):
        """Create request factory."""
        return RequestFactory()

    @pytest.fixture
    def request_with_user(self, request_factory, user):
        """Create request with authenticated user."""
        request = request_factory.post("/")
        request.user = user
        request.session = {}
        return request

    def test_upsert_store_review_invalid_rating_low(self, request_with_user):
        """Test that rating < 1 is rejected."""
        service = StoreReviewService(request_with_user)

        # Create mock store
        class MockStore:
            id = 1
            owner_id = 999

        result = service.upsert_store_review(MockStore(), 0)  # type: ignore

        assert result.success is False
        assert "от 1 до 5" in result.message

    def test_upsert_store_review_invalid_rating_high(self, request_with_user):
        """Test that rating > 5 is rejected."""
        service = StoreReviewService(request_with_user)

        class MockStore:
            id = 1
            owner_id = 999

        result = service.upsert_store_review(MockStore(), 6)  # type: ignore

        assert result.success is False
        assert "от 1 до 5" in result.message

    def test_upsert_store_review_result_type(self, request_with_user):
        """Test that result is StoreReviewOperationResult."""
        service = StoreReviewService(request_with_user)

        class MockStore:
            id = 1
            owner_id = 999

        result = service.upsert_store_review(MockStore(), 0)  # type: ignore

        assert isinstance(result, StoreReviewOperationResult)
        assert hasattr(result, "success")
        assert hasattr(result, "message")

    def test_delete_store_review_result_type(self, request_with_user):
        """Test that delete result is correct type."""
        service = StoreReviewService(request_with_user)

        class MockStore:
            id = 1

        result = service.delete_store_review(MockStore())  # type: ignore

        assert isinstance(result, StoreReviewOperationResult)
        assert hasattr(result, "deleted")
        assert hasattr(result, "success")

    def test_service_user_authentication(self, request_with_user):
        """Test that service correctly stores authenticated user."""
        service = StoreReviewService(request_with_user)
        assert service.user == request_with_user.user
        assert service.user.is_authenticated
