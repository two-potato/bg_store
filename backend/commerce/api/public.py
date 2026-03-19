"""Public and authenticated commerce endpoints plus DaData lookup helpers."""

from rest_framework import views, permissions, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from django.conf import settings
from django.core.cache import cache
from ..models import LegalEntity, MembershipRequest, DeliveryAddress, LegalEntityMembership
from ..serializers import (
    CheckInnResponseSerializer,
    CheckInnRequestSerializer,
    MembershipRequestCreateSerializer,
    DeliveryAddressSerializer,
    DetailSerializer,
    ValidationErrorSerializer,
    LookupPartyResponseSerializer,
    LookupBankResponseSerializer,
    ReverseGeocodeResponseSerializer,
)

import asyncio
import logging
import os
from typing import Any
from json import JSONDecodeError

import httpx
from django.template import loader
from django.http import HttpResponse
from ..utils import reverse_geocode
from core.logging_utils import LoggedAPIViewMixin, LoggedViewSetMixin, log_calls
from core.notifications import apost_notify_json

log = logging.getLogger("commerce")


@extend_schema(
    tags=["Commerce"],
    summary="Check company INN in local database",
    description="Проверяет, есть ли юрлицо с указанным ИНН в локальной базе платформы.",
    request=CheckInnRequestSerializer,
    responses={
        200: CheckInnResponseSerializer,
        401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
    },
)
class CheckInnView(LoggedAPIViewMixin, views.APIView):
    """Check whether a legal entity with the given INN already exists locally."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CheckInnRequestSerializer

    def post(self, request: Any) -> Response:
        """Return local legal-entity presence information for the provided INN."""
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

@extend_schema_view(
    create=extend_schema(
        tags=["Commerce"],
        summary="Create membership request",
        description="Создаёт заявку на вступление текущего пользователя в существующее юрлицо.",
        request=MembershipRequestCreateSerializer,
        responses={
            201: MembershipRequestCreateSerializer,
            400: OpenApiResponse(response=ValidationErrorSerializer, description="Ошибка валидации заявки"),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        },
        examples=[
            OpenApiExample(
                "Membership request",
                value={"legal_entity": 12, "comment": "Нужен доступ для оформления заказов и управления адресами."},
                request_only=True,
            )
        ],
    )
)
class MembershipRequestViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Create membership requests for existing legal entities."""

    permission_classes = [permissions.IsAuthenticated]
    queryset = MembershipRequest.objects.all()
    serializer_class = MembershipRequestCreateSerializer

    def perform_create(self, serializer: MembershipRequestCreateSerializer) -> None:
        """Persist a membership request and notify entity admins when possible."""
        req = serializer.save()
        log.info("membership_request_created", extra={"legal_entity_id": req.legal_entity_id, "applicant_id": req.applicant_id})
        admins_qs = LegalEntityMembership.objects.filter(
            legal_entity=req.legal_entity,
            role__code__in=["owner","admin"]
        ).select_related("user__profile")
        admins = list(admins_qs)
        async def send(admins_list: list[LegalEntityMembership]) -> None:
            """Dispatch Telegram notifications to admins of the target entity."""
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
        except RuntimeError:
            # Don't block API on notify errors in dev/tests
            log.exception("membership_notify_error")
        log.info("membership_notify_done", extra={"admins": len(admins)})

@extend_schema_view(
    list=extend_schema(
        tags=["Commerce"],
        summary="List delivery addresses",
        description="Возвращает адреса доставки текущего пользователя. Можно отфильтровать по `legal_entity`.",
        parameters=[
            OpenApiParameter(
                name="legal_entity",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID юрлица для фильтрации адресов",
            )
        ],
        responses={
            200: DeliveryAddressSerializer(many=True),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        },
    ),
    retrieve=extend_schema(
        tags=["Commerce"],
        summary="Retrieve delivery address",
        description="Возвращает один адрес доставки по id.",
        responses={
            200: DeliveryAddressSerializer,
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            404: OpenApiResponse(response=DetailSerializer, description="Адрес не найден"),
        },
    ),
    create=extend_schema(
        tags=["Commerce"],
        summary="Create delivery address",
        description="Создаёт адрес доставки для юрлица, в котором состоит текущий пользователь.",
        request=DeliveryAddressSerializer,
        responses={
            201: DeliveryAddressSerializer,
            400: OpenApiResponse(response=ValidationErrorSerializer, description="Ошибка валидации адреса"),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            403: OpenApiResponse(response=DetailSerializer, description="Нет доступа к выбранному юрлицу"),
        },
    ),
    update=extend_schema(
        tags=["Commerce"],
        summary="Update delivery address",
        description="Полностью обновляет адрес доставки.",
        request=DeliveryAddressSerializer,
        responses={
            200: DeliveryAddressSerializer,
            400: OpenApiResponse(response=ValidationErrorSerializer, description="Ошибка валидации адреса"),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            404: OpenApiResponse(response=DetailSerializer, description="Адрес не найден"),
        },
    ),
    partial_update=extend_schema(
        tags=["Commerce"],
        summary="Partially update delivery address",
        description="Частично обновляет адрес доставки.",
        request=DeliveryAddressSerializer,
        responses={
            200: DeliveryAddressSerializer,
            400: OpenApiResponse(response=ValidationErrorSerializer, description="Ошибка валидации адреса"),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            404: OpenApiResponse(response=DetailSerializer, description="Адрес не найден"),
        },
    ),
    destroy=extend_schema(
        tags=["Commerce"],
        summary="Delete delivery address",
        description="Удаляет адрес доставки.",
        request=None,
        responses={
            204: None,
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            404: OpenApiResponse(response=DetailSerializer, description="Адрес не найден"),
        },
    ),
)
class DeliveryAddressViewSet(LoggedViewSetMixin, viewsets.ModelViewSet):
    """CRUD for delivery addresses available to the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeliveryAddressSerializer
    queryset = DeliveryAddress.objects.none()
    lookup_field = "pk"

    def get_queryset(self):
        """Limit delivery addresses to legal entities visible to the caller."""
        if getattr(self, "swagger_fake_view", False) or not getattr(getattr(self.request, "user", None), "is_authenticated", False):
            return DeliveryAddress.objects.none()
        le_id = self.request.query_params.get("legal_entity")
        qs = DeliveryAddress.objects.filter(legal_entity__members=self.request.user)
        return qs.filter(legal_entity_id=le_id) if le_id else qs

    def perform_create(self, serializer: DeliveryAddressSerializer) -> None:
        """Create an address only if the caller belongs to the selected entity."""
        le_id = int(self.request.data.get("legal_entity"))
        # ensure user is a member of the legal entity
        if not LegalEntityMembership.objects.filter(user=self.request.user, legal_entity_id=le_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к выбранному юрлицу")
        obj = serializer.save(legal_entity_id=le_id)
        lat = None
        lon = None
        try:
            lat = float(obj.latitude) if obj.latitude is not None else None
            lon = float(obj.longitude) if obj.longitude is not None else None
        except (TypeError, ValueError):
            log.warning("address_created_invalid_coordinates", extra={"address_id": obj.id})
        log.info(
            "address_created",
            extra={
                "user_id": self.request.user.id,
                "legal_entity_id": le_id,
                "address_id": obj.id,
                "city": obj.city,
                "street": obj.street,
                "lat": lat,
                "lon": lon,
                "is_default": obj.is_default,
            },
        )


# -------- External lookups (DaData) --------

DADATA_TOKEN = getattr(settings, "DADATA_TOKEN", os.getenv("DADATA_TOKEN", ""))
LOOKUP_TTL = int(getattr(settings, "CACHE_TTL_COMMERCE_LOOKUPS", 600))

async def _dadata_post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a DaData POST request and return the decoded JSON payload."""
    headers = {"Authorization": f"Token {DADATA_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()


@extend_schema(
    tags=["Commerce"],
    summary="Lookup company by INN via DaData",
    description="Возвращает карточку компании по ИНН через DaData. Используется для автозаполнения юрлица.",
    parameters=[OpenApiParameter(name="inn", type=str, location=OpenApiParameter.QUERY, required=True)],
    responses={
        200: LookupPartyResponseSerializer,
        400: OpenApiResponse(response=DetailSerializer, description="Отсутствует DADATA_TOKEN или не передан inn"),
        401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        404: OpenApiResponse(response=LookupPartyResponseSerializer, description="Организация по ИНН не найдена"),
    },
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_party_by_inn(request):
    """Look up a company by INN via DaData and normalize the response."""
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
    tags=["Commerce"],
    summary="Lookup bank by BIK via DaData",
    description="Возвращает реквизиты банка по БИК через DaData.",
    parameters=[OpenApiParameter(name="bik", type=str, location=OpenApiParameter.QUERY, required=True)],
    responses={
        200: LookupBankResponseSerializer,
        400: OpenApiResponse(response=DetailSerializer, description="Отсутствует DADATA_TOKEN или не передан bik"),
        401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        404: OpenApiResponse(response=LookupBankResponseSerializer, description="Банк по БИК не найден"),
    },
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_bank_by_bik(request):
    """Look up bank requisites by BIK via DaData."""
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
    """Return a small HTMX-friendly HTML preview for a company INN."""
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
        except (httpx.HTTPError, RuntimeError, ValueError, JSONDecodeError):
            status_code = 500
    html = loader.render_to_string("account/partials/inn_preview.html", ctx)
    return HttpResponse(html, content_type="text/html", status=status_code)


@extend_schema(
    tags=["Commerce"],
    summary="Reverse geocode coordinates",
    description="Возвращает нормализованные адресные поля по координатам через reverse geocode helper.",
    parameters=[
        OpenApiParameter(name="lat", type=float, location=OpenApiParameter.QUERY, required=True),
        OpenApiParameter(name="lon", type=float, location=OpenApiParameter.QUERY, required=True),
    ],
    responses={
        200: ReverseGeocodeResponseSerializer,
        400: OpenApiResponse(response=DetailSerializer, description="Не переданы или некорректны lat/lon"),
        401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        404: OpenApiResponse(response=ReverseGeocodeResponseSerializer, description="Адрес по координатам не найден"),
    },
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@log_calls(log)
def lookup_reverse_geocode(request):
    """Reverse-geocode coordinates into normalized address fragments."""
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if lat is None or lon is None:
        log.warning(
            "revgeo_invalid_request",
            extra={"ui_surface": "address_lookup", "reason": "missing_coordinates", "lat": lat or "", "lon": lon or ""},
        )
        return Response({"detail": "lat and lon are required"}, status=400)
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        log.warning(
            "revgeo_invalid_request",
            extra={"ui_surface": "address_lookup", "reason": "invalid_coordinates", "lat": lat or "", "lon": lon or ""},
        )
        return Response({"detail": "invalid coordinates"}, status=400)
    lat_lon = f"{lat_f:.5f}:{lon_f:.5f}"
    cache_key = f"commerce:lookup:revgeo:{lat_lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        log.info(
            "revgeo_cache_hit",
            extra={"ui_surface": "address_lookup", "lat_lon": lat_lon},
        )
        return Response(cached)
    data = reverse_geocode(lat_f, lon_f)
    if not data:
        log.warning(
            "revgeo_not_found",
            extra={"ui_surface": "address_lookup", "lat_lon": lat_lon},
        )
        return Response({}, status=404)
    cache.set(cache_key, data, timeout=LOOKUP_TTL)
    log.info(
        "revgeo_response_ok",
        extra={"ui_surface": "address_lookup", "lat_lon": lat_lon, "has_postcode": bool(data.get("postcode"))},
    )
    return Response(data)
