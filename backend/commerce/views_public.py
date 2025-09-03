from rest_framework import views, permissions, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings
from .models import LegalEntity, MembershipRequest, DeliveryAddress, LegalEntityMembership
from .serializers import (
    CheckInnResponseSerializer, MembershipRequestCreateSerializer, DeliveryAddressSerializer
)
import asyncio
import logging
import os
import httpx
from django.template import loader
from django.http import HttpResponse
from .utils import reverse_geocode
from core.logging_utils import LoggedAPIViewMixin, LoggedViewSetMixin, log_calls

log = logging.getLogger("commerce")

class CheckInnView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        inn = (request.data.get("inn") or "").strip()
        try:
            le = LegalEntity.objects.get(inn=inn)
            data = {"exists": True, "legal_entity_id": le.id, "name": le.name}
        except LegalEntity.DoesNotExist:
            data = {"exists": False}
        return Response(CheckInnResponseSerializer(data).data)

class MembershipRequestViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = MembershipRequest.objects.all()
    serializer_class = MembershipRequestCreateSerializer
    def perform_create(self, serializer):
        req = serializer.save()
        log.info("membership_request_created", extra={"legal_entity_id": req.legal_entity_id, "applicant_id": req.applicant_id})
        admins_qs = LegalEntityMembership.objects.filter(
            legal_entity=req.legal_entity,
            role__in=[LegalEntityMembership.Role.OWNER, LegalEntityMembership.Role.ADMIN]
        ).select_related("user__profile")
        admins = list(admins_qs)
        async def send(admins_list):
            async with httpx.AsyncClient(timeout=10) as c:
                for m in admins_list:
                    tg = getattr(m.user.profile, "telegram_id", None)
                    if tg:
                        await c.post(f"{settings.BOT_BASE_URL}/notify/send_kb", json={
                            "telegram_id": tg,
                            "text": f"🔔 Заявка на вступление в {req.legal_entity.name} от {req.applicant.username}",
                            "keyboard": [[{"text":"Открыть админку","callback_data":"noop"}]]
                        })
        try:
            if admins:
                asyncio.run(send(admins))
        except Exception:
            # Don't block API on notify errors in dev/tests
            log.exception("membership_notify_error")
        log.info("membership_notify_done", extra={"admins": len(admins)})

class DeliveryAddressViewSet(LoggedViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeliveryAddressSerializer
    def get_queryset(self):
        le_id = self.request.query_params.get("legal_entity")
        qs = DeliveryAddress.objects.filter(legal_entity__members=self.request.user)
        return qs.filter(legal_entity_id=le_id) if le_id else qs
    def perform_create(self, serializer):
        le_id = int(self.request.data.get("legal_entity"))
        # ensure user is a member of the legal entity
        if not LegalEntityMembership.objects.filter(user=self.request.user, legal_entity_id=le_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к выбранному юрлицу")
        serializer.save(legal_entity_id=le_id)


# -------- External lookups (DaData) --------

DADATA_TOKEN = getattr(settings, "DADATA_TOKEN", os.getenv("DADATA_TOKEN", ""))

async def _dadata_post(url: str, payload: dict):
    headers = {"Authorization": f"Token {DADATA_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_party_by_inn(request):
    if not DADATA_TOKEN:
        return Response({"detail": "DADATA_TOKEN is not configured"}, status=400)
    inn = (request.query_params.get("inn") or "").strip()
    if not inn:
        return Response({"detail": "inn is required"}, status=400)
    data = asyncio.run(_dadata_post(
        "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party",
        {"query": inn}
    ))
    sug = (data.get("suggestions") or [])
    if not sug:
        return Response({}, status=404)
    item = sug[0].get("data", {})
    addr = (item.get("address") or {}).get("data") or {}
    out = {
        "inn": item.get("inn"),
        "kpp": item.get("kpp"),
        "ogrn": item.get("ogrn"),
        "name": (item.get("name") or {}).get("short_with_opf") or (item.get("name") or {}).get("full_with_opf"),
        "address": (item.get("address") or {}).get("unrestricted_value"),
        "street": addr.get("street_with_type") or "",
        "house": addr.get("house") or "",
        "block": addr.get("block") or "",
        "building": addr.get("building") or "",
        "management": (item.get("management") or {}).get("name"),
        "okved": (item.get("okveds") or [{}])[0].get("code") if item.get("okveds") else item.get("okved"),
        "status": item.get("state", {}).get("status"),
    }
    return Response(out)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_bank_by_bik(request):
    if not DADATA_TOKEN:
        return Response({"detail": "DADATA_TOKEN is not configured"}, status=400)
    bik = (request.query_params.get("bik") or "").strip()
    if not bik:
        return Response({"detail": "bik is required"}, status=400)
    data = asyncio.run(_dadata_post(
        "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/bank",
        {"query": bik}
    ))
    sug = (data.get("suggestions") or [])
    if not sug:
        return Response({}, status=404)
    item = sug[0].get("data", {})
    out = {
        "bik": item.get("bic"),
        "name": (item.get("name") or {}).get("payment"),
        "correspondent_account": item.get("corr_account"),
        "address": (item.get("address") or {}).get("value"),
    }
    return Response(out)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_party_preview(request):
    """Return small HTML preview by INN to show on the form (HTMX-friendly)."""
    inn = (request.query_params.get("inn") or "").strip()
    ctx = {"name": "", "inn": inn, "kpp": "", "address": "", "found": False}
    status_code = 200
    if not inn:
        status_code = 400
    elif not DADATA_TOKEN:
        status_code = 400
    else:
        try:
            data = asyncio.run(_dadata_post(
                "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party",
                {"query": inn}
            ))
            sug = (data.get("suggestions") or [])
            if sug:
                item = sug[0].get("data", {})
                addr = (item.get("address") or {}).get("data") or {}
                ctx.update({
                    "name": (item.get("name") or {}).get("short_with_opf") or (item.get("name") or {}).get("full_with_opf") or "",
                    "inn": item.get("inn") or inn,
                    "kpp": item.get("kpp") or "",
                    "address": (item.get("address") or {}).get("unrestricted_value") or "",
                    "street": addr.get("street_with_type") or "",
                    "house": addr.get("house") or "",
                    "block": addr.get("block") or "",
                    "building": addr.get("building") or "",
                    "found": True,
                })
            else:
                status_code = 404
        except Exception:
            status_code = 500
    html = loader.render_to_string("account/partials/inn_preview.html", ctx)
    return HttpResponse(html, content_type="text/html", status=status_code)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_reverse_geocode(request):
    """Return country, city, street, postcode by lat/lon via DaData.

    Query params: lat, lon
    """
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if lat is None or lon is None:
        return Response({"detail": "lat and lon are required"}, status=400)
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return Response({"detail": "invalid coordinates"}, status=400)
    data = reverse_geocode(lat_f, lon_f)
    if not data:
        return Response({}, status=404)
    return Response(data)
