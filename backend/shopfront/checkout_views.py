"""Compatibility exports for cart, checkout, guest order, and payment views."""

from .views.checkout_cart import (
    BuyNowView,
    CartAddView,
    CartBadgeView,
    CartClearView,
    CartPageView,
    CartPanelView,
    CartRemoveView,
    CartUpdateView,
)
from .views.checkout_flow import CheckoutPageView, CheckoutSubmitView
from .views.checkout_payment import (
    FakePaymentEventView,
    FakePaymentPageView,
    GuestFakePaymentEventView,
    GuestFakePaymentPageView,
    GuestOnlinePaymentEventView,
    GuestOnlinePaymentPageView,
    GuestOrderDetailView,
    OnlinePaymentEventView,
    OnlinePaymentPageView,
)

__all__ = [
    "CartBadgeView",
    "CartPanelView",
    "CartAddView",
    "BuyNowView",
    "CartPageView",
    "CartRemoveView",
    "CartClearView",
    "CartUpdateView",
    "CheckoutPageView",
    "CheckoutSubmitView",
    "FakePaymentPageView",
    "FakePaymentEventView",
    "OnlinePaymentPageView",
    "OnlinePaymentEventView",
    "GuestOrderDetailView",
    "GuestFakePaymentPageView",
    "GuestFakePaymentEventView",
    "GuestOnlinePaymentPageView",
    "GuestOnlinePaymentEventView",
]
