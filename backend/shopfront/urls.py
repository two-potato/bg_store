from django.urls import path
from .views import (
    HomeView, CatalogView, ProductDetailView, TwaHomeView,
    CartBadgeView, CartPanelView, CartAddView, CartRemoveView, CartClearView, CartUpdateView, CartPageView,
    CheckoutPageView, CheckoutSubmitView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("catalog/", CatalogView.as_view(), name="catalog"),
    path("product/<int:pk>/", ProductDetailView.as_view(), name="product"),
    path("cart/badge/", CartBadgeView.as_view(), name="cart_badge"),
    path("cart/", CartPageView.as_view(), name="cart_page"),
    path("cart/panel/", CartPanelView.as_view(), name="cart_panel"),
    path("cart/add/", CartAddView.as_view(), name="cart_add"),
    path("cart/remove/", CartRemoveView.as_view(), name="cart_remove"),
    path("cart/clear/", CartClearView.as_view(), name="cart_clear"),
    path("cart/update/", CartUpdateView.as_view(), name="cart_update"),
    path("twa/", TwaHomeView.as_view(), name="twa_home"),
    path("checkout/", CheckoutPageView.as_view(), name="checkout"),
    path("checkout/submit/", CheckoutSubmitView.as_view(), name="checkout_submit"),
]
