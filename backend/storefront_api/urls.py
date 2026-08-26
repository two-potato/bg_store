from django.urls import path

from .account_views import StorefrontAccountAddressDeleteView, StorefrontAccountAddressesView, StorefrontAccountAddressSetDefaultView, StorefrontAccountBootstrapView, StorefrontAccountLegalEntitiesView, StorefrontAccountNotificationsView, StorefrontAccountPreferencesView, StorefrontAccountSettingsView
from .analytics_views import StorefrontWaveAnalyticsIngestView
from .cart_views import StorefrontCartAddView, StorefrontCartClearView, StorefrontCartRemoveView, StorefrontCartUpdateView, StorefrontCartView, StorefrontSessionBootstrapView
from .order_views import StorefrontOrderDetailView, StorefrontOrderReorderView
from .tools_views import StorefrontFavoriteToggleView, StorefrontFavoritesView, StorefrontSavedListAddItemView, StorefrontSavedListDeleteView, StorefrontSavedListDetailView, StorefrontSavedListMoveToCartView, StorefrontSavedListRemoveItemView, StorefrontSavedListsView, StorefrontSavedListTogglePublicView, StorefrontSavedSearchDeleteView, StorefrontSavedSearchesView

urlpatterns = [
    path("api/storefront/session/bootstrap/", StorefrontSessionBootstrapView.as_view(), name="storefront_session_bootstrap"),
    path("api/storefront/cart/", StorefrontCartView.as_view(), name="storefront_cart_json"),
    path("api/storefront/cart/add/", StorefrontCartAddView.as_view(), name="storefront_cart_add_json"),
    path("api/storefront/cart/update/", StorefrontCartUpdateView.as_view(), name="storefront_cart_update_json"),
    path("api/storefront/cart/remove/", StorefrontCartRemoveView.as_view(), name="storefront_cart_remove_json"),
    path("api/storefront/cart/clear/", StorefrontCartClearView.as_view(), name="storefront_cart_clear_json"),
    path("api/storefront/orders/<int:order_id>/", StorefrontOrderDetailView.as_view(), name="storefront_order_detail_json"),
    path("api/storefront/orders/<int:order_id>/reorder/", StorefrontOrderReorderView.as_view(), name="storefront_order_reorder_json"),
    path("api/storefront/account/settings/", StorefrontAccountSettingsView.as_view(), name="storefront_account_settings"),
    path("api/storefront/account/preferences/", StorefrontAccountPreferencesView.as_view(), name="storefront_account_preferences"),
    path("api/storefront/account/addresses/", StorefrontAccountAddressesView.as_view(), name="storefront_account_addresses"),
    path("api/storefront/account/addresses/<int:address_id>/default/", StorefrontAccountAddressSetDefaultView.as_view(), name="storefront_account_address_set_default"),
    path("api/storefront/account/addresses/<int:address_id>/delete/", StorefrontAccountAddressDeleteView.as_view(), name="storefront_account_address_delete"),
    path("api/storefront/account/legal-entities/", StorefrontAccountLegalEntitiesView.as_view(), name="storefront_account_legal_entities"),
    path("api/storefront/account/notifications/", StorefrontAccountNotificationsView.as_view(), name="storefront_account_notifications"),
    path("api/storefront/account/bootstrap/", StorefrontAccountBootstrapView.as_view(), name="storefront_account_bootstrap"),
    path("api/storefront/tools/favorites/", StorefrontFavoritesView.as_view(), name="storefront_tools_favorites"),
    path("api/storefront/tools/favorites/toggle/", StorefrontFavoriteToggleView.as_view(), name="storefront_tools_favorite_toggle"),
    path("api/storefront/tools/lists/", StorefrontSavedListsView.as_view(), name="storefront_tools_saved_lists"),
    path("api/storefront/tools/lists/<int:list_id>/", StorefrontSavedListDetailView.as_view(), name="storefront_tools_saved_list_detail"),
    path("api/storefront/tools/lists/<int:list_id>/add/", StorefrontSavedListAddItemView.as_view(), name="storefront_tools_saved_list_add_item"),
    path("api/storefront/tools/lists/<int:list_id>/remove-item/", StorefrontSavedListRemoveItemView.as_view(), name="storefront_tools_saved_list_remove_item"),
    path("api/storefront/tools/lists/<int:list_id>/move-to-cart/", StorefrontSavedListMoveToCartView.as_view(), name="storefront_tools_saved_list_move_to_cart"),
    path("api/storefront/tools/lists/<int:list_id>/toggle-public/", StorefrontSavedListTogglePublicView.as_view(), name="storefront_tools_saved_list_toggle_public"),
    path("api/storefront/tools/lists/<int:list_id>/delete/", StorefrontSavedListDeleteView.as_view(), name="storefront_tools_saved_list_delete"),
    path("api/storefront/tools/saved-searches/", StorefrontSavedSearchesView.as_view(), name="storefront_tools_saved_searches"),
    path("api/storefront/tools/saved-searches/<int:search_id>/delete/", StorefrontSavedSearchDeleteView.as_view(), name="storefront_tools_saved_search_delete"),
    path("api/storefront/analytics/ingest/", StorefrontWaveAnalyticsIngestView.as_view(), name="storefront_wave_analytics_ingest"),
]
