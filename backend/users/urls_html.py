from django.urls import path, include
from .views_html import (
    account_home, account_addresses, account_legal_entities, account_orders, account_order_detail, account_comments,
    login_view, register_view, logout_view, telegram_webapp_login, cancel_legal_request, confirm_email_view,
    validate_login_form, validate_register_form,
    account_seller_home, account_seller_product_add,
)

urlpatterns = [
    path("", account_home, name="account_home"),
    path("addresses/", account_addresses, name="account_addresses"),
    path("legal/", account_legal_entities, name="account_legal"),
    path("legal/request/<int:pk>/cancel/", cancel_legal_request, name="account_legal_cancel"),
    path("orders/", account_orders, name="account_orders"),
    path("orders/<int:order_id>/", account_order_detail, name="account_order_detail"),
    path("comments/", account_comments, name="account_comments"),
    path("seller/", account_seller_home, name="account_seller_home"),
    path("seller/products/add/", account_seller_product_add, name="account_seller_products_add"),
    path("login/", login_view, name="login"),
    path("login/validate/", validate_login_form, name="login_validate"),
    path("register/", register_view, name="register"),
    path("register/validate/", validate_register_form, name="register_validate"),
    path("confirm-email/", confirm_email_view, name="confirm_email"),
    path("logout/", logout_view, name="logout"),
    path("twa/login/", telegram_webapp_login, name="twa_login"),
    # allauth URLs under /account/social/
    path("social/", include("allauth.urls")),
]
