from rest_framework import views, permissions
from rest_framework.response import Response
from .models import LegalEntity, MembershipRequest, LegalEntityCreationRequest, LegalEntityMembership
from core.logging_utils import LoggedAPIViewMixin

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class ApproveMembershipView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        mr = MembershipRequest.objects.select_related("legal_entity","applicant").get(pk=pk)
        if mr.status != mr.Status.PENDING:
            return Response({"detail":"Уже обработано"}, status=400)
        LegalEntityMembership.objects.get_or_create(
            user=mr.applicant, legal_entity=mr.legal_entity,
            defaults={"role": LegalEntityMembership.Role.MANAGER}
        )
        mr.status = mr.Status.APPROVED
        mr.save(update_fields=["status"])
        return Response({"ok": True})

class RejectMembershipView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        mr = MembershipRequest.objects.get(pk=pk)
        if mr.status != mr.Status.PENDING:
            return Response({"detail":"Уже обработано"}, status=400)
        mr.status = mr.Status.REJECTED
        mr.save(update_fields=["status"])
        return Response({"ok": True})

class ApproveEntityCreationView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if cr.status != cr.Status.PENDING:
            return Response({"detail":"Уже обработано"}, status=400)
        le = LegalEntity.objects.create(
            name=cr.name, inn=cr.inn, bik=cr.bik, checking_account=cr.checking_account, bank_name=cr.bank_name
        )
        LegalEntityMembership.objects.create(user=cr.applicant, legal_entity=le, role=LegalEntityMembership.Role.OWNER)
        cr.status = cr.Status.APPROVED
        cr.save(update_fields=["status"])
        return Response({"ok": True, "legal_entity_id": le.id})

class RejectEntityCreationView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if cr.status != cr.Status.PENDING:
            return Response({"detail":"Уже обработано"}, status=400)
        cr.status = cr.Status.REJECTED
        cr.save(update_fields=["status"])
        return Response({"ok": True})
