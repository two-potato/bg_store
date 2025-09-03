from django.urls import path
from .views import home, catalog_page, product_page, cart_badge, cart_panel, cart_add, cart_remove, cart_clear, cart_update, checkout_page, checkout_submit

urlpatterns = [
    path("", home, name="home"),
    path("catalog/", catalog_page, name="catalog"),
    path("product/<int:pk>/", product_page, name="product"),
    path("cart/badge/", cart_badge, name="cart_badge"),
    path("cart/panel/", cart_panel, name="cart_panel"),
    path("cart/add/", cart_add, name="cart_add"),
    path("cart/remove/", cart_remove, name="cart_remove"),
    path("cart/clear/", cart_clear, name="cart_clear"),
    path("cart/update/", cart_update, name="cart_update"),
    path("checkout/", checkout_page, name="checkout"),
    path("checkout/submit/", checkout_submit, name="checkout_submit"),
]
