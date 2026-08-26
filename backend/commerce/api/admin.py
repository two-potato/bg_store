"""Admin-only moderation endpoints for commerce workflows."""

from typing import Any

from rest_framework import views, permissions
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiResponse, extend_schema
from ..models import LegalEntity, MembershipRequest, LegalEntityCreationRequest, LegalEntityMembership
from ..serializers import SimpleOkSerializer, SimpleOkWithLegalEntitySerializer, DetailSerializer
from core.logging_utils import LoggedAPIViewMixin
import logging

log = logging.getLogger("commerce")


class IsAdmin(permissions.BasePermission):
    """Allow access only to Django staff users."""

    def has_permission(self, request: Any, view: Any) -> bool:
        """Return whether the current request is performed by a staff user."""
        return bool(request.user and request.user.is_staff)


@extend_schema(
    tags=["Commerce Admin"],
    summary="Approve membership request",
    description="Подтверждает заявку на вступление пользователя в юрлицо. Доступно только staff-пользователям.",
    request=None,
    responses={
        200: SimpleOkSerializer,
        400: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
    },
)
class ApproveMembershipView(LoggedAPIViewMixin, views.APIView):
    """Approve a pending membership request and create the membership link."""

    permission_classes = [IsAdmin]
    serializer_class = SimpleOkSerializer

    def post(self, request: Any, pk: int) -> Response:
        """Approve a membership request if it is still pending."""
        mr = MembershipRequest.objects.select_related("legal_entity","applicant").get(pk=pk)
        if getattr(mr.status, 'code', None) != 'pending':
            log.info("membership_request_approve_skipped_not_pending", extra={"request_id": mr.id, "status": getattr(mr.status, "code", None)})
            return Response({"detail":"Уже обработано"}, status=400)
        from ..models import MembershipRole, RequestStatus
        LegalEntityMembership.objects.get_or_create(
            user=mr.applicant, legal_entity=mr.legal_entity,
            defaults={"role": MembershipRole.objects.get_or_create(code='manager', defaults={'name':'Менеджер'})[0]}
        )
        mr.status = RequestStatus.objects.get(code='approved')
        mr.save(update_fields=["status"])
        log.info("membership_request_approved", extra={"request_id": mr.id, "legal_entity_id": mr.legal_entity_id, "applicant_id": mr.applicant_id, "admin_user_id": request.user.id})
        return Response({"ok": True})


@extend_schema(
    tags=["Commerce Admin"],
    summary="Reject membership request",
    description="Отклоняет заявку на вступление пользователя в юрлицо.",
    request=None,
    responses={
        200: SimpleOkSerializer,
        400: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
    },
)
class RejectMembershipView(LoggedAPIViewMixin, views.APIView):
    """Reject a pending membership request."""

    permission_classes = [IsAdmin]
    serializer_class = SimpleOkSerializer

    def post(self, request: Any, pk: int) -> Response:
        """Reject a membership request if it is still pending."""
        mr = MembershipRequest.objects.get(pk=pk)
        if getattr(mr.status, 'code', None) != 'pending':
            log.info("membership_request_reject_skipped_not_pending", extra={"request_id": mr.id, "status": getattr(mr.status, "code", None)})
            return Response({"detail":"Уже обработано"}, status=400)
        from ..models import RequestStatus
        mr.status = RequestStatus.objects.get(code='rejected')
        mr.save(update_fields=["status"])
        log.info("membership_request_rejected", extra={"request_id": mr.id, "admin_user_id": request.user.id})
        return Response({"ok": True})


@extend_schema(
    tags=["Commerce Admin"],
    summary="Approve legal entity creation request",
    description="Создаёт юрлицо на основе заявки и назначает заявителя owner-участником.",
    request=None,
    responses={
        200: OpenApiResponse(response=SimpleOkWithLegalEntitySerializer),
        400: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
    },
)
class ApproveEntityCreationView(LoggedAPIViewMixin, views.APIView):
    """Approve a legal-entity creation request and create the entity."""

    permission_classes = [IsAdmin]
    serializer_class = SimpleOkSerializer

    def post(self, request: Any, pk: int) -> Response:
        """Create the legal entity and mark the request as approved."""
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if getattr(cr.status, 'code', None) != 'pending':
            log.info("entity_creation_request_approve_skipped_not_pending", extra={"request_id": cr.id, "status": getattr(cr.status, "code", None)})
            return Response({"detail":"Уже обработано"}, status=400)
        le = LegalEntity.objects.create(
            name=cr.name, inn=cr.inn, bik=cr.bik, checking_account=cr.checking_account, bank_name=cr.bank_name
        )
        from ..models import MembershipRole, RequestStatus
        LegalEntityMembership.objects.create(user=cr.applicant, legal_entity=le, role=MembershipRole.objects.get_or_create(code='owner', defaults={'name': 'Владелец'})[0])
        cr.status = RequestStatus.objects.get(code='approved')
        cr.save(update_fields=["status"])
        log.info("entity_creation_request_approved", extra={"request_id": cr.id, "legal_entity_id": le.id, "applicant_id": cr.applicant_id, "admin_user_id": request.user.id})
        return Response({"ok": True, "legal_entity_id": le.id})


@extend_schema(
    tags=["Commerce Admin"],
    summary="Reject legal entity creation request",
    description="Отклоняет заявку на создание юрлица.",
    request=None,
    responses={
        200: SimpleOkSerializer,
        400: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
    },
)
class RejectEntityCreationView(LoggedAPIViewMixin, views.APIView):
    """Reject a pending legal-entity creation request."""

    permission_classes = [IsAdmin]
    serializer_class = SimpleOkSerializer

    def post(self, request: Any, pk: int) -> Response:
        """Reject a legal-entity creation request if it is still pending."""
        cr = LegalEntityCreationRequest.objects.get(pk=pk)
        if getattr(cr.status, 'code', None) != 'pending':
            log.info("entity_creation_request_reject_skipped_not_pending", extra={"request_id": cr.id, "status": getattr(cr.status, "code", None)})
            return Response({"detail":"Уже обработано"}, status=400)
        from ..models import RequestStatus
        cr.status = RequestStatus.objects.get(code='rejected')
        cr.save(update_fields=["status"])
        log.info("entity_creation_request_rejected", extra={"request_id": cr.id, "admin_user_id": request.user.id})
        return Response({"ok": True})
