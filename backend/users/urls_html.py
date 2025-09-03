from django.urls import path, include
from .views_html import (
    account_home, account_addresses, account_legal_entities, account_orders,
    login_view, register_view, logout_view, telegram_webapp_login, cancel_legal_request
)

urlpatterns = [
    path("", account_home, name="account_home"),
    path("addresses/", account_addresses, name="account_addresses"),
    path("legal/", account_legal_entities, name="account_legal"),
    path("legal/request/<int:pk>/cancel/", cancel_legal_request, name="account_legal_cancel"),
    path("orders/", account_orders, name="account_orders"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("twa/login/", telegram_webapp_login, name="twa_login"),
    # allauth URLs under /account/social/
    path("social/", include("allauth.urls")),
]
