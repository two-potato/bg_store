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
        if getattr(mr.status, 'code', None) != 'pending':
            return Response({"detail":"Уже обработано"}, status=400)
        from .models import MembershipRole, RequestStatus
        LegalEntityMembership.objects.get_or_create(
            user=mr.applicant, legal_entity=mr.legal_entity,
            defaults={"role": MembershipRole.objects.get_or_create(code='manager', defaults={'name':'Менеджер'})[0]}
        )
        mr.status = RequestStatus.objects.get(code='approved')
        mr.save(update_fields=["status"])
        return Response({"ok": True})

class RejectMembershipView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        mr = MembershipRequest.objects.get(pk=pk)
        if getattr(mr.status, 'code', None) != 'pending':
            return Response({"detail":"Уже обработано"}, status=400)
        from .models import RequestStatus
        mr.status = RequestStatus.objects.get(code='rejected')
        mr.save(update_fields=["status"])
        return Response({"ok": True})

class ApproveEntityCreationView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if getattr(cr.status, 'code', None) != 'pending':
            return Response({"detail":"Уже обработано"}, status=400)
        le = LegalEntity.objects.create(
            name=cr.name, inn=cr.inn, bik=cr.bik, checking_account=cr.checking_account, bank_name=cr.bank_name
        )
        from .models import MembershipRole, RequestStatus
        LegalEntityMembership.objects.create(user=cr.applicant, legal_entity=le, role=MembershipRole.objects.get_or_create(code='owner', defaults={'name': 'Владелец'})[0])
        cr.status = RequestStatus.objects.get(code='approved')
        cr.save(update_fields=["status"])
        return Response({"ok": True, "legal_entity_id": le.id})

class RejectEntityCreationView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [IsAdmin]
    def post(self, request, pk):
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if getattr(cr.status, 'code', None) != 'pending':
            return Response({"detail":"Уже обработано"}, status=400)
        from .models import RequestStatus
        cr.status = RequestStatus.objects.get(code='rejected')
        cr.save(update_fields=["status"])
        return Response({"ok": True})
