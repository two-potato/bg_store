from django.contrib import admin, messages
from django.db import transaction
import logging

from .models import (
    LegalEntity,
    LegalEntityMembership,
    DeliveryAddress,
    MembershipRequest,
    LegalEntityCreationRequest,
    SellerStore,
)

log = logging.getLogger("commerce")


@admin.register(LegalEntity)
class LegalEntityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "bik", "bank_name", "created_at")
    search_fields = ("name", "inn")
    list_filter = ("created_at",)


@admin.register(LegalEntityMembership)
class LegalEntityMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "legal_entity", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("user__username", "user__email", "legal_entity__name", "legal_entity__inn")


@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "legal_entity", "city", "street", "postcode", "is_default")
    list_filter = ("is_default", "city")
    search_fields = ("label", "city", "street", "postcode", "legal_entity__name", "legal_entity__inn")


@admin.register(MembershipRequest)
class MembershipRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "applicant", "legal_entity", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("applicant__username", "applicant__email", "legal_entity__name", "legal_entity__inn")
    actions = ("approve_requests", "reject_requests")

    @admin.action(description="Одобрить выбранные заявки")
    def approve_requests(self, request, queryset):
        approved = 0
        skipped = 0
        for mr in queryset.select_related("legal_entity", "applicant"):
            if getattr(mr.status, 'code', None) != 'pending':
                skipped += 1
                continue
            with transaction.atomic():
                LegalEntityMembership.objects.get_or_create(
                    user=mr.applicant,
                    legal_entity=mr.legal_entity,
                    defaults={"role": None},
                )
                from .models import RequestStatus
                mr.status = RequestStatus.objects.get(code='approved')
                mr.save(update_fields=["status"])
                approved += 1
                log.info(
                    "membership_request_approved_admin_action",
                    extra={
                        "request_id": mr.id,
                        "legal_entity_id": mr.legal_entity_id,
                        "applicant_id": mr.applicant_id,
                        "admin_user_id": request.user.id,
                    },
                )
        if approved:
            messages.success(request, f"Одобрено: {approved}")
        if skipped:
            messages.info(request, f"Пропущено (не pending): {skipped}")
        log.info("membership_requests_admin_action_done", extra={"approved": approved, "skipped": skipped, "admin_user_id": request.user.id})

    @admin.action(description="Отклонить выбранные заявки")
    def reject_requests(self, request, queryset):
        from .models import RequestStatus
        updated = queryset.filter(status__code='pending').update(status=RequestStatus.objects.get(code='rejected'))
        messages.success(request, f"Отклонено: {updated}")
        log.info("membership_requests_rejected_admin_action", extra={"updated": updated, "admin_user_id": request.user.id})


@admin.register(LegalEntityCreationRequest)
class LegalEntityCreationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "inn", "applicant", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "inn", "applicant__username", "applicant__email")
    actions = ("approve_creations", "reject_creations")

    @admin.action(description="Одобрить создание юрлица")
    def approve_creations(self, request, queryset):
        created = 0
        skipped = 0
        for cr in queryset.select_related("applicant"):
            if getattr(cr.status, 'code', None) != 'pending':
                skipped += 1
                continue
            with transaction.atomic():
                # Avoid duplicate by INN
                if LegalEntity.objects.filter(inn=cr.inn).exists():
                    skipped += 1
                    messages.warning(
                        request,
                        f"ИНН {cr.inn} уже существует — заявка #{cr.id} пропущена",
                    )
                    continue
                le = LegalEntity.objects.create(
                    name=cr.name,
                    inn=cr.inn,
                    bik=cr.bik,
                    checking_account=cr.checking_account,
                    bank_name=cr.bank_name,
                )
                from .models import MembershipRole, RequestStatus
                owner = MembershipRole.objects.get(code='owner')
                LegalEntityMembership.objects.create(user=cr.applicant, legal_entity=le, role=owner)
                cr.status = RequestStatus.objects.get(code='approved')
                cr.save(update_fields=["status"])
                created += 1
                log.info(
                    "entity_creation_approved_admin_action",
                    extra={
                        "request_id": cr.id,
                        "legal_entity_id": le.id,
                        "applicant_id": cr.applicant_id,
                        "admin_user_id": request.user.id,
                    },
                )
        if created:
            messages.success(request, f"Создано юрлиц: {created}")
        if skipped:
            messages.info(request, f"Пропущено (не pending): {skipped}")
        log.info("entity_creations_admin_action_done", extra={"created": created, "skipped": skipped, "admin_user_id": request.user.id})

    @admin.action(description="Отклонить создание юрлица")
    def reject_creations(self, request, queryset):
        from .models import RequestStatus
        updated = queryset.filter(status__code='pending').update(status=RequestStatus.objects.get(code='rejected'))
        messages.success(request, f"Отклонено заявок: {updated}")
        log.info("entity_creations_rejected_admin_action", extra={"updated": updated, "admin_user_id": request.user.id})


@admin.register(SellerStore)
class SellerStoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "legal_entity", "created_at")
    search_fields = ("name", "owner__username", "legal_entity__name", "legal_entity__inn")
