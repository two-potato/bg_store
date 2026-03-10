from rest_framework import views, permissions, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from django.conf import settings
from django.core.cache import cache
from .models import LegalEntity, MembershipRequest, DeliveryAddress, LegalEntityMembership
from .serializers import (
    CheckInnResponseSerializer,
    CheckInnRequestSerializer,
    MembershipRequestCreateSerializer,
    DeliveryAddressSerializer,
    DetailSerializer,
    LookupPartyResponseSerializer,
    LookupBankResponseSerializer,
    ReverseGeocodeResponseSerializer,
)
import asyncio
import logging
import os
import httpx
from django.template import loader
from django.http import HttpResponse
from .utils import reverse_geocode
from core.logging_utils import LoggedAPIViewMixin, LoggedViewSetMixin, log_calls
from core.notifications import apost_notify_json

log = logging.getLogger("commerce")


@extend_schema(request=CheckInnRequestSerializer, responses=CheckInnResponseSerializer)
class CheckInnView(LoggedAPIViewMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CheckInnRequestSerializer

    def post(self, request):
        inn = (request.data.get("inn") or "").strip()
        cache_key = f"commerce:inn_exists:{inn}"
        data = cache.get(cache_key)
        if data is None:
            try:
                le = LegalEntity.objects.get(inn=inn)
                data = {"exists": True, "legal_entity_id": le.id, "name": le.name}
            except LegalEntity.DoesNotExist:
                data = {"exists": False}
            cache.set(cache_key, data, timeout=LOOKUP_TTL)
        return Response(CheckInnResponseSerializer(data).data)

@extend_schema_view(create=extend_schema(request=MembershipRequestCreateSerializer, responses=MembershipRequestCreateSerializer))
class MembershipRequestViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = MembershipRequest.objects.all()
    serializer_class = MembershipRequestCreateSerializer
    def perform_create(self, serializer):
        req = serializer.save()
        log.info("membership_request_created", extra={"legal_entity_id": req.legal_entity_id, "applicant_id": req.applicant_id})
        admins_qs = LegalEntityMembership.objects.filter(
            legal_entity=req.legal_entity,
            role__code__in=["owner","admin"]
        ).select_related("user__profile")
        admins = list(admins_qs)
        async def send(admins_list):
            from httpx import AsyncClient

            async with AsyncClient(timeout=10) as c:
                for m in admins_list:
                    tg = getattr(m.user.profile, "telegram_id", None)
                    if tg:
                        await apost_notify_json(
                            c,
                            "/notify/send_kb",
                            {
                                "telegram_id": tg,
                                "text": f"🔔 Заявка на вступление в {req.legal_entity.name} от {req.applicant.username}",
                                "keyboard": [[{"text":"Открыть админку","callback_data":"noop"}]],
                            },
                            logger=log,
                            failure_event="membership_notify_failed",
                            extra={"legal_entity_id": req.legal_entity_id, "telegram_id": int(tg)},
                        )
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
    queryset = DeliveryAddress.objects.none()
    lookup_field = "pk"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not getattr(getattr(self.request, "user", None), "is_authenticated", False):
            return DeliveryAddress.objects.none()
        le_id = self.request.query_params.get("legal_entity")
        qs = DeliveryAddress.objects.filter(legal_entity__members=self.request.user)
        return qs.filter(legal_entity_id=le_id) if le_id else qs
    def perform_create(self, serializer):
        le_id = int(self.request.data.get("legal_entity"))
        # ensure user is a member of the legal entity
        if not LegalEntityMembership.objects.filter(user=self.request.user, legal_entity_id=le_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к выбранному юрлицу")
        obj = serializer.save(legal_entity_id=le_id)
        try:
            log.info(
                "address_created",
                extra={
                    "user_id": self.request.user.id,
                    "legal_entity_id": le_id,
                    "address_id": obj.id,
                    "city": obj.city,
                    "street": obj.street,
                    "lat": float(obj.latitude) if obj.latitude is not None else None,
                    "lon": float(obj.longitude) if obj.longitude is not None else None,
                    "is_default": obj.is_default,
                },
            )
        except Exception:
            pass


# -------- External lookups (DaData) --------

DADATA_TOKEN = getattr(settings, "DADATA_TOKEN", os.getenv("DADATA_TOKEN", ""))
LOOKUP_TTL = int(getattr(settings, "CACHE_TTL_COMMERCE_LOOKUPS", 600))

async def _dadata_post(url: str, payload: dict):
    headers = {"Authorization": f"Token {DADATA_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()


@extend_schema(
    parameters=[OpenApiParameter(name="inn", type=str, location=OpenApiParameter.QUERY, required=True)],
    responses={200: LookupPartyResponseSerializer, 400: DetailSerializer, 404: LookupPartyResponseSerializer},
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_party_by_inn(request):
    if not DADATA_TOKEN:
        return Response({"detail": "DADATA_TOKEN is not configured"}, status=400)
    inn = (request.query_params.get("inn") or "").strip()
    if not inn:
        return Response({"detail": "inn is required"}, status=400)
    cache_key = f"commerce:lookup:party:{inn}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
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
    cache.set(cache_key, out, timeout=LOOKUP_TTL)
    return Response(out)


@extend_schema(
    parameters=[OpenApiParameter(name="bik", type=str, location=OpenApiParameter.QUERY, required=True)],
    responses={200: LookupBankResponseSerializer, 400: DetailSerializer, 404: LookupBankResponseSerializer},
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_bank_by_bik(request):
    if not DADATA_TOKEN:
        return Response({"detail": "DADATA_TOKEN is not configured"}, status=400)
    bik = (request.query_params.get("bik") or "").strip()
    if not bik:
        return Response({"detail": "bik is required"}, status=400)
    cache_key = f"commerce:lookup:bank:{bik}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
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
    cache.set(cache_key, out, timeout=LOOKUP_TTL)
    return Response(out)


@extend_schema(exclude=True)
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


@extend_schema(
    parameters=[
        OpenApiParameter(name="lat", type=float, location=OpenApiParameter.QUERY, required=True),
        OpenApiParameter(name="lon", type=float, location=OpenApiParameter.QUERY, required=True),
    ],
    responses={200: ReverseGeocodeResponseSerializer, 400: DetailSerializer, 404: ReverseGeocodeResponseSerializer},
)
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
    lat_lon = f"{lat_f:.5f}:{lon_f:.5f}"
    cache_key = f"commerce:lookup:revgeo:{lat_lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
    data = reverse_geocode(lat_f, lon_f)
    if not data:
        return Response({}, status=404)
    cache.set(cache_key, data, timeout=LOOKUP_TTL)
    return Response(data)
