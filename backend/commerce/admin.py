from django.contrib import admin, messages
from django.db import transaction

from .models import (
    LegalEntity,
    LegalEntityMembership,
    DeliveryAddress,
    MembershipRequest,
    LegalEntityCreationRequest,
)


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
            if mr.status != mr.Status.PENDING:
                skipped += 1
                continue
            with transaction.atomic():
                LegalEntityMembership.objects.get_or_create(
                    user=mr.applicant,
                    legal_entity=mr.legal_entity,
                    defaults={"role": LegalEntityMembership.Role.MANAGER},
                )
                mr.status = mr.Status.APPROVED
                mr.save(update_fields=["status"])
                approved += 1
        if approved:
            messages.success(request, f"Одобрено: {approved}")
        if skipped:
            messages.info(request, f"Пропущено (не pending): {skipped}")

    @admin.action(description="Отклонить выбранные заявки")
    def reject_requests(self, request, queryset):
        updated = queryset.filter(status=MembershipRequest.Status.PENDING).update(
            status=MembershipRequest.Status.REJECTED
        )
        messages.success(request, f"Отклонено: {updated}")


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
            if cr.status != cr.Status.PENDING:
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
                LegalEntityMembership.objects.create(
                    user=cr.applicant,
                    legal_entity=le,
                    role=LegalEntityMembership.Role.OWNER,
                )
                cr.status = cr.Status.APPROVED
                cr.save(update_fields=["status"])
                created += 1
        if created:
            messages.success(request, f"Создано юрлиц: {created}")
        if skipped:
            messages.info(request, f"Пропущено (не pending): {skipped}")

    @admin.action(description="Отклонить создание юрлица")
    def reject_creations(self, request, queryset):
        updated = queryset.filter(status=LegalEntityCreationRequest.Status.PENDING).update(
            status=LegalEntityCreationRequest.Status.REJECTED
        )
        messages.success(request, f"Отклонено заявок: {updated}")
