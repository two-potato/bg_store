from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from .models import FakeAcquiringPayment, Order


@dataclass
class PaymentInitResult:
    provider_code: str
    payment_id: str
    redirect_url: str
    payment: FakeAcquiringPayment


class PaymentProvider(Protocol):
    code: str

    def initialize(self, order: Order) -> PaymentInitResult: ...


class FakeMirProvider:
    code = "fake_mir"

    def initialize(self, order: Order) -> PaymentInitResult:
        payment, _created = FakeAcquiringPayment.objects.get_or_create(
            order=order,
            defaults={
                "amount": order.total,
                "provider_payment_id": f"fake_{order.id}_{uuid4().hex[:10]}",
            },
        )
        return PaymentInitResult(
            provider_code=self.code,
            payment_id=payment.provider_payment_id,
            redirect_url=f"/payments/fake/{order.id}/",
            payment=payment,
        )


def get_payment_provider(payment_method: str) -> PaymentProvider | None:
    mapping = {
        Order.PaymentMethod.MIR_CARD: FakeMirProvider(),
    }
    return mapping.get(payment_method)
