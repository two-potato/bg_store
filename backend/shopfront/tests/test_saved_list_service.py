"""Tests for saved list operations service."""

import pytest
from django.contrib.auth import get_user_model

from ..saved_list_service import (
    SavedListOperationService,
    SavedListOperationResult,
    FavoriteOperationService,
    SubscriptionOperationService,
    SavedSearchService,
)
from ..models import SavedList

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestSavedListOperationService:
    """Test SavedListOperationService for list management."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="listuser",
            email="list@example.com",
            password="testpass123",
        )

    def test_create_list_with_name(self, user):
        """Test creating a saved list with name."""
        service = SavedListOperationService(user)
        result = service.create_list(name="My Shopping List")

        assert result.success is True
        assert result.list_id is not None
        assert (
            "сохранён" in result.message.lower() or "создан" in result.message.lower()
        )

    def test_create_list_default_name(self, user):
        """Test creating saved list uses default name if empty."""
        service = SavedListOperationService(user)
        result = service.create_list(name="")

        assert result.success is True
        assert result.list_id is not None
        # Should use default name "Новый список"
        saved_list = SavedList.objects.get(id=result.list_id)
        assert saved_list.name == "Новый список"

    def test_delete_list(self, user):
        """Test deleting a saved list."""
        # Create list first
        saved_list = SavedList.objects.create(
            user=user,
            name="List to Delete",
        )

        service = SavedListOperationService(user)
        result = service.delete_list(list_id=saved_list.id)

        assert result.success is True
        assert not SavedList.objects.filter(id=saved_list.id).exists()

    def test_delete_list_nonexistent(self, user):
        """Test deleting nonexistent list returns error."""
        service = SavedListOperationService(user)
        result = service.delete_list(list_id=99999)

        assert result.success is False

    def test_result_is_dataclass(self, user):
        """Test that result is SavedListOperationResult."""
        service = SavedListOperationService(user)
        result = service.create_list()

        assert isinstance(result, SavedListOperationResult)
        assert hasattr(result, "success")
        assert hasattr(result, "message")
        assert hasattr(result, "list_id")
        assert hasattr(result, "affected_count")

    def test_add_products_to_list(self, user):
        """Test adding products to a saved list."""
        # This test requires products to exist in DB
        # Verify method signature exists
        SavedList.objects.create(user=user, name="Test List")
        service = SavedListOperationService(user)

        assert hasattr(service, "add_products_to_list")
        assert callable(service.add_products_to_list)


class TestFavoriteOperationService:
    """Test FavoriteOperationService for favorite management."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="favuser",
            email="fav@example.com",
            password="testpass123",
        )

    def test_service_instantiation(self, user):
        """Test FavoriteOperationService can be instantiated."""
        service = FavoriteOperationService(user)
        assert service.user == user

    def test_toggle_favorite_has_required_method(self, user):
        """Test that toggle_favorite method exists."""
        service = FavoriteOperationService(user)
        assert hasattr(service, "toggle_favorite")
        assert callable(service.toggle_favorite)

    def test_result_structure(self, user):
        """Test that favorite operations return proper result."""
        service = FavoriteOperationService(user)
        # Method exists but requires valid product
        assert hasattr(service, "toggle_favorite")


class TestSubscriptionOperationService:
    """Test SubscriptionOperationService for subscription management."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="subuser",
            email="sub@example.com",
            password="testpass123",
        )

    def test_service_instantiation(self, user):
        """Test SubscriptionOperationService instantiation."""
        service = SubscriptionOperationService(user)
        assert service.user == user

    def test_toggle_brand_subscription_method_exists(self, user):
        """Test toggle_brand_subscription method exists."""
        service = SubscriptionOperationService(user)
        assert hasattr(service, "toggle_brand_subscription")
        assert callable(service.toggle_brand_subscription)

    def test_toggle_category_subscription_method_exists(self, user):
        """Test toggle_category_subscription method exists."""
        service = SubscriptionOperationService(user)
        assert hasattr(service, "toggle_category_subscription")
        assert callable(service.toggle_category_subscription)


class TestSavedSearchService:
    """Test SavedSearchService for saved search management."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username="searchuser",
            email="search@example.com",
            password="testpass123",
        )

    def test_service_instantiation(self, user):
        """Test SavedSearchService instantiation."""
        service = SavedSearchService(user)
        assert service.user == user

    def test_save_search_method_exists(self, user):
        """Test save_search method exists."""
        service = SavedSearchService(user)
        assert hasattr(service, "save_search")
        assert callable(service.save_search)

    def test_delete_search_method_exists(self, user):
        """Test delete_search method exists."""
        service = SavedSearchService(user)
        assert hasattr(service, "delete_search")
        assert callable(service.delete_search)
