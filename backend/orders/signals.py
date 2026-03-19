import logging

from kombu.exceptions import OperationalError
from django.db import transaction
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver

from .models import Order, OrderItem
from .services import plan_seller_splits, recalc_order_totals_from_items
from .tasks import notify_admin_order_status_email, notify_order_status_telegram

log = logging.getLogger("orders")


def _schedule_email(order_id: int, event: str, previous_status: str | None = None) -> None:
    try:
        notify_admin_order_status_email.delay(order_id=order_id, event=event, previous_status=previous_status)
        log.info("order_email_scheduled", extra={"order_id": order_id, "event": event, "previous_status": previous_status})
    except Exception:
        # Email notification must never break order lifecycle.
        log.exception("order_email_schedule_failed", extra={"order_id": order_id, "event": event})


def _schedule_telegram_status(order_id: int, event: str, previous_status: str | None = None) -> None:
    try:
        notify_order_status_telegram.delay(order_id=order_id, event=event, previous_status=previous_status)
        log.info("order_status_tg_scheduled", extra={"order_id": order_id, "event": event, "previous_status": previous_status})
    except Exception:
        log.exception("order_status_tg_schedule_failed", extra={"order_id": order_id})


@receiver(pre_save, sender=Order)
def order_track_previous_status(sender, instance: Order, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        old = Order.objects.only("status").get(pk=instance.pk)
        instance._previous_status = old.status
    except Order.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def order_notify_admin_on_create_or_status_change(sender, instance: Order, created: bool, **kwargs):
    transaction.on_commit(lambda: plan_seller_splits(instance))

    if created:
        log.info("order_created_signal", extra={"order_id": instance.id, "status": instance.status})
        transaction.on_commit(lambda: _schedule_email(order_id=instance.id, event="created"))
        transaction.on_commit(lambda: _schedule_telegram_status(order_id=instance.id, event="created"))
        return

    prev = getattr(instance, "_previous_status", None)
    if prev != instance.status:
        log.info("order_status_changed_signal", extra={"order_id": instance.id, "previous_status": prev, "status": instance.status})
        transaction.on_commit(
            lambda: _schedule_email(
                order_id=instance.id,
                event="status_changed",
                previous_status=prev,
            )
        )
        transaction.on_commit(
            lambda: _schedule_telegram_status(
                order_id=instance.id,
                event="status_changed",
                previous_status=prev,
            )
        )


def _sync_order_after_item_change(order_id: int) -> None:
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return
    recalc_order_totals_from_items(order)
    plan_seller_splits(order)


@receiver(post_save, sender=OrderItem)
def order_item_sync_seller_splits_on_save(sender, instance: OrderItem, **kwargs):
    _sync_order_after_item_change(instance.order_id)


@receiver(post_delete, sender=OrderItem)
def order_item_sync_seller_splits_on_delete(sender, instance: OrderItem, **kwargs):
    _sync_order_after_item_change(instance.order_id)
