from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.cache import cache
from django.http import Http404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from datetime import timedelta
import requests
from .forms import (
    LoginForm,
    RegisterForm,
    ProfileForm,
    LegalEntityRequestForm,
    AddressForm,
    SellerStoreForm,
    SellerProductCreateForm,
)
from .views import verify_init_data
from core.logging_utils import log_calls
import logging
from .models import UserProfile

log = logging.getLogger("users")


User = get_user_model()


def _build_email_confirm_token(user) -> str:
    token = AccessToken.for_user(user)
    token["typ"] = "email_confirm"
    token["uid"] = user.id
    token["eml"] = (user.email or "").strip().lower()
    token.set_exp(lifetime=timedelta(hours=24))
    return str(token)


def _send_email_confirmation(request, user) -> None:
    token = _build_email_confirm_token(user)
    confirm_url = request.build_absolute_uri(f"{reverse('confirm_email')}?token={token}")
    text = (
        "Подтвердите ваш email для входа в аккаунт BG Shop.\n\n"
        f"Ссылка подтверждения: {confirm_url}\n\n"
        "Ссылка действует 24 часа."
    )
    send_mail(
        subject="[BG Shop] Подтверждение email",
        message=text,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )


def _safe_next(request, default: str = "account_home") -> str:
    target = (request.GET.get("next") or "").strip()
    if target and url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return default


def _is_seller(request) -> bool:
    profile = getattr(request.user, "profile", None)
    if not profile:
        return False
    seller_value = getattr(getattr(UserProfile, "Role", object), "SELLER", "seller")
    return str(profile.role) == str(seller_value)


def _client_ip(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return xff or request.META.get("REMOTE_ADDR", "unknown")


def _login_fail_key(request) -> str:
    return f"auth:login:fail:{_client_ip(request)}"


def _mark_login_failure(request) -> None:
    key = _login_fail_key(request)
    current = int(cache.get(key, 0) or 0)
    cache.set(key, current + 1, timeout=int(getattr(settings, "LOGIN_CAPTCHA_WINDOW_SECONDS", 900)))


def _clear_login_failures(request) -> None:
    cache.delete(_login_fail_key(request))


def _captcha_required(request) -> bool:
    threshold = int(getattr(settings, "LOGIN_CAPTCHA_THRESHOLD", 5))
    if threshold <= 0:
        return False
    current = int(cache.get(_login_fail_key(request), 0) or 0)
    return current >= threshold


def _verify_turnstile(token: str, remoteip: str) -> tuple[bool, str]:
    secret = (getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    if not secret:
        return False, "Капча не настроена"
    if not token:
        return False, "Подтвердите, что вы не робот"
    try:
        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": remoteip},
            timeout=8,
        )
        payload = resp.json()
    except Exception:
        return False, "Не удалось проверить капчу. Повторите попытку."
    if bool(payload.get("success")):
        return True, ""
    return False, "Проверка капчи не пройдена"


@log_calls()
def account_home(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль обновлён")
        return redirect("account_home")
    from orders.models import Order
    from commerce.models import LegalEntityMembership, DeliveryAddress

    memberships_qs = LegalEntityMembership.objects.filter(user=request.user)
    entity_ids = memberships_qs.values_list("legal_entity_id", flat=True)
    metrics = {
        "orders_count": Order.objects.filter(placed_by=request.user).count(),
        "entities_count": memberships_qs.count(),
        "addresses_count": DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).count(),
    }
    if _is_seller(request):
        return redirect("account_seller_home")
    return render(
        request,
        "account/home.html",
        {"form": form, "profile": profile, "metrics": metrics, "account_section": "home"},
    )


@log_calls()
def account_addresses(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/addresses/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from commerce.models import DeliveryAddress, LegalEntityMembership
    # Все адреса по юрлицам, в которых состоит пользователь
    entity_ids = list(
        LegalEntityMembership.objects.filter(user=request.user).values_list("legal_entity_id", flat=True)
    )
    addresses = DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).order_by("-is_default","label")
    form = AddressForm(request.POST or None, user=request.user)
    # Создание адреса
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Адрес добавлен")
            # Для HTMX вернём только список адресов
            if request.headers.get("HX-Request"):
                updated = DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).order_by("-is_default","label")
                resp = render(request, "account/partials/addresses_list.html", {"addresses": updated})
                # Показать toast об успешном добавлении
                resp["HX-Trigger"] = '{"showToast": {"message": "Адрес добавлен", "variant": "success"}}'
                return resp
            return redirect("account_addresses")
        else:
            # Ошибки валидации: для HTMX отдаём только список ошибок (200 OK, чтобы HTMX произвёл swap)
            if request.headers.get("HX-Request"):
                resp = render(request, "account/partials/form_errors.html", {"form": form})
                resp["HX-Retarget"] = "#address-form-errors"
                resp["HX-Reswap"] = "innerHTML"
                resp["HX-Trigger"] = '{"showToast": {"message": "Исправьте ошибки формы", "variant": "danger"}}'
                return resp
    # Поддержка HTMX для подстановки списка
    if request.headers.get("HX-Request") and request.GET.get("fragment") == "list":
        return render(request, "account/partials/addresses_list.html", {"addresses": addresses})
    return render(
        request,
        "account/addresses.html",
        {
            "addresses": addresses,
            "form": form,
            "gmaps_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
            "profile": profile,
            "account_section": "addresses",
        },
    )


@log_calls()
def account_legal_entities(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/legal/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from commerce.models import LegalEntityMembership, LegalEntityCreationRequest
    my_memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=request.user)
    form = LegalEntityRequestForm(request.POST or None)
    requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            LegalEntityCreationRequest.objects.create(
                applicant=request.user,
                name=data["name"],
                inn=data["inn"],
                bik=data.get("bik") or "",
                checking_account=data.get("checking_account") or "",
                bank_name=data.get("bank_name") or "",
            )
            messages.success(request, "Заявка отправлена на рассмотрение")
            if request.headers.get("HX-Request"):
                # Вернём только список заявок
                requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
                return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})
            return redirect("account_legal")
        else:
            messages.error(request, "Исправьте ошибки в форме")
    # Поддержка HTMX для обновления списков
    if request.headers.get("HX-Request"):
        frag = request.GET.get("fragment")
        if frag == "requests":
            return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})
        if frag == "memberships":
            my_memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=request.user)
            return render(request, "account/partials/memberships_list.html", {"memberships": my_memberships})
    return render(
        request,
        "account/legal_entities.html",
        {
            "memberships": my_memberships,
            "form": form,
            "requests": requests_qs,
            "profile": profile,
            "account_section": "legal",
        },
    )


@require_http_methods(["POST"])
@log_calls()
def cancel_legal_request(request, pk: int):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/legal/")
    from commerce.models import LegalEntityCreationRequest
    obj = LegalEntityCreationRequest.objects.select_related("status").filter(id=pk, applicant=request.user).first()
    if obj and getattr(obj.status, 'code', None) == 'pending':
        from commerce.models import RequestStatus
        obj.status = RequestStatus.objects.get(code='rejected')
        obj.save(update_fields=["status"])
        messages.success(request, "Заявка отменена")
    # Вернём обновлённый список заявок (для HTMX)
    requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
    return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})


@log_calls()
def account_orders(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/orders/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from orders.models import Order
    orders = Order.objects.filter(placed_by=request.user).order_by("-id")[:100]
    return render(request, "account/orders.html", {"orders": orders, "profile": profile, "account_section": "orders"})


@log_calls()
def account_order_detail(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from orders.models import Order

    order = (
        Order.objects.select_related("legal_entity", "delivery_address")
        .prefetch_related("items__product__images")
        .filter(id=order_id, placed_by=request.user)
        .first()
    )
    if not order:
        raise Http404("Order not found")
    fake_payment = getattr(order, "fake_payment", None)
    return render(
        request,
        "account/order_detail.html",
        {"order": order, "fake_payment": fake_payment, "profile": profile, "account_section": "orders"},
    )


@log_calls()
def account_comments(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/comments/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from catalog.models import ProductReviewComment

    comments = (
        ProductReviewComment.objects.select_related("review__product")
        .filter(user=request.user)
        .order_by("-created_at", "-id")[:200]
    )
    return render(
        request,
        "account/comments.html",
        {"comments": comments, "profile": profile, "account_section": "comments"},
    )


@log_calls()
def account_seller_home(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")

    from commerce.models import LegalEntityMembership
    from catalog.models import Product

    store = getattr(request.user, "seller_store", None)
    form = SellerStoreForm(request.POST or None, request.FILES or None, instance=store, user=request.user)
    if request.method == "POST" and form.is_valid():
        store_obj = form.save(commit=False)
        store_obj.owner = request.user
        store_obj.save()
        messages.success(request, "Магазин продавца сохранён")
        return redirect("account_seller_home")

    memberships_qs = LegalEntityMembership.objects.filter(user=request.user)
    seller_metrics = {
        "products_count": Product.objects.filter(seller=request.user).count(),
        "in_stock_count": Product.objects.filter(seller=request.user, stock_qty__gt=0).count(),
        "entities_count": memberships_qs.count(),
    }
    return render(
        request,
        "account/seller_home.html",
        {
            "profile": profile,
            "store": store,
            "store_form": form,
            "seller_metrics": seller_metrics,
            "account_section": "seller_home",
        },
    )


@log_calls()
def account_seller_product_add(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/products/add/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")

    store = getattr(request.user, "seller_store", None)
    if store is None:
        messages.error(request, "Сначала настройте магазин продавца")
        return redirect("account_seller_home")

    form = SellerProductCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Товар '{product.name}' добавлен")
        return redirect("account_seller_products_add")

    from catalog.models import Product
    my_products = Product.objects.filter(seller=request.user).select_related("brand", "category").order_by("-id")[:20]
    return render(
        request,
        "account/seller_product_add.html",
        {
            "profile": profile,
            "store": store,
            "form": form,
            "my_products": my_products,
            "account_section": "seller_products",
        },
    )


@require_http_methods(["GET", "POST"])
@log_calls()
def login_view(request):
    if request.user.is_authenticated:
        return redirect("account_home")
    form = LoginForm(request.POST or None)
    captcha_required = _captcha_required(request)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip()
        password = form.cleaned_data["password"]
        if captcha_required:
            token = (request.POST.get("cf-turnstile-response") or "").strip()
            ok, captcha_error = _verify_turnstile(token, _client_ip(request))
            if not ok:
                _mark_login_failure(request)
                messages.error(request, captcha_error)
                return render(
                    request,
                    "account/login.html",
                    {
                        "form": form,
                        "seo_title": "Вход в аккаунт - PotatoFarm",
                        "seo_description": "Авторизация в личном кабинете PotatoFarm.",
                        "seo_robots": "noindex,nofollow",
                        "captcha_required": True,
                        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
                        "google_oauth_enabled": bool(
                            getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
                            .get("google", {})
                            .get("APP", {})
                            .get("client_id")
                        ),
                    },
                )
        # allow login by username/email/phone
        user = None
        candidate = None
        for field in ("username", "email"):
            try:
                candidate = User.objects.get(**{field: ident})
                user = authenticate(request, username=candidate.username, password=password)
                if user:
                    break
            except User.DoesNotExist:
                continue
        if not user:
            # phone via profile
            try:
                candidate = User.objects.get(profile__phone=ident)
                user = authenticate(request, username=candidate.username, password=password)
            except User.DoesNotExist:
                user = None
        if user:
            _clear_login_failures(request)
            login(request, user)
            return redirect(_safe_next(request))
        _mark_login_failure(request)
        captcha_required = _captcha_required(request)
        if candidate and not candidate.is_active and candidate.check_password(password):
            messages.error(request, "Подтвердите email по ссылке из письма")
        else:
            messages.error(request, "Неверные учётные данные")
    return render(
        request,
        "account/login.html",
        {
            "form": form,
            "seo_title": "Вход в аккаунт - PotatoFarm",
            "seo_description": "Авторизация в личном кабинете PotatoFarm.",
            "seo_robots": "noindex,nofollow",
            "google_oauth_enabled": bool(
                getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
                .get("google", {})
                .get("APP", {})
                .get("client_id")
            ),
            "captcha_required": captcha_required,
            "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
        },
    )


@require_http_methods(["GET", "POST"])
@log_calls()
def register_view(request):
    if request.user.is_authenticated:
        return redirect("account_home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            _send_email_confirmation(request, user)
        except Exception:
            log.exception("register_email_confirmation_send_failed", extra={"user_id": user.id, "email": user.email})
            messages.error(request, "Не удалось отправить письмо подтверждения. Попробуйте позже.")
            return render(
                request,
                "account/register.html",
                {
                    "form": form,
                    "seo_title": "Регистрация - PotatoFarm",
                    "seo_description": "Создание аккаунта на PotatoFarm.",
                    "seo_robots": "noindex,nofollow",
                    "google_oauth_enabled": bool(
                        getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
                        .get("google", {})
                        .get("APP", {})
                        .get("client_id")
                    ),
                },
            )
        messages.success(request, "Письмо с подтверждением отправлено на вашу почту")
        return redirect("login")
    return render(
        request,
        "account/register.html",
        {
            "form": form,
            "seo_title": "Регистрация - PotatoFarm",
            "seo_description": "Создание аккаунта на PotatoFarm.",
            "seo_robots": "noindex,nofollow",
            "google_oauth_enabled": bool(
                getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
                .get("google", {})
                .get("APP", {})
                .get("client_id")
            ),
        },
    )


@require_http_methods(["POST"])
@log_calls()
def validate_login_form(request):
    form = LoginForm(request.POST or None)
    form.is_valid()
    return render(request, "account/partials/form_errors.html", {"form": form})


@require_http_methods(["POST"])
@log_calls()
def validate_register_form(request):
    form = RegisterForm(request.POST or None)
    form.is_valid()
    return render(request, "account/partials/form_errors.html", {"form": form})


@require_http_methods(["GET"])
@log_calls()
def confirm_email_view(request):
    token = (request.GET.get("token") or "").strip()
    if not token:
        messages.error(request, "Ссылка подтверждения недействительна")
        return redirect("login")
    try:
        payload = AccessToken(token)
    except TokenError:
        messages.error(request, "Ссылка подтверждения истекла или недействительна")
        return redirect("login")

    if payload.get("typ") != "email_confirm":
        messages.error(request, "Некорректный тип токена подтверждения")
        return redirect("login")

    uid = payload.get("uid")
    eml = (payload.get("eml") or "").strip().lower()
    if not uid:
        messages.error(request, "Некорректная ссылка подтверждения")
        return redirect("login")

    user = User.objects.filter(id=uid).first()
    if not user or (eml and (user.email or "").strip().lower() != eml):
        messages.error(request, "Пользователь для подтверждения не найден")
        return redirect("login")

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Email подтверждён. Вы вошли в аккаунт.")
    return redirect("account_home")


@log_calls()
def logout_view(request):
    logout(request)
    return redirect("/")


@require_http_methods(["GET", "POST"])
@log_calls()
def telegram_webapp_login(request):
    # Accept initData from Telegram WebApp and establish Django session
    init_data = request.POST.get("initData") or request.GET.get("initData", "")
    if not init_data:
        log.info("twa_login_no_data")
        messages.error(request, "Нет данных Telegram")
        return redirect("login")
    tg_user = verify_init_data(init_data)
    if tg_user is None:
        log.info("twa_login_invalid_initdata")
        messages.error(request, "Некорректные данные Telegram")
        return redirect("login")
    telegram_id = tg_user.get("id")
    try:
        telegram_id = int(telegram_id)
    except Exception:
        log.info("twa_login_missing_tg_id")
        messages.error(request, "Некорректный Telegram ID")
        return redirect("login")
    username = tg_user.get("username") or f"tg_{telegram_id}"
    user, created = User.objects.get_or_create(username=f"tg_{telegram_id}", defaults={"email": ""})
    # Ensure profile exists
    from .models import UserProfile
    prof, _ = UserProfile.objects.get_or_create(user=user)
    prof.telegram_id = telegram_id
    prof.telegram_username = username
    prof.save()
    # Specify backend explicitly due to multiple backends configured
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    # Avoid clashing with LogRecord.created attribute
    log.info("twa_login_ok", extra={"user_id": user.id, "telegram_id": telegram_id, "user_created": created})
    return redirect("account_home")
