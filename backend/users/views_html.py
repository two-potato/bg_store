from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404
from .forms import LoginForm, RegisterForm, ProfileForm, LegalEntityRequestForm, AddressForm
from .views import verify_init_data
from core.logging_utils import log_calls
import logging
from .models import UserProfile

log = logging.getLogger("users")


User = get_user_model()


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


@require_http_methods(["GET", "POST"])
@log_calls()
def login_view(request):
    if request.user.is_authenticated:
        return redirect("account_home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip()
        password = form.cleaned_data["password"]
        # allow login by username/email/phone
        user = None
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
            login(request, user)
            return redirect(request.GET.get("next") or "account_home")
        messages.error(request, "Неверные учётные данные")
    return render(
        request,
        "account/login.html",
        {
            "form": form,
            "google_oauth_enabled": bool(
                getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
                .get("google", {})
                .get("APP", {})
                .get("client_id")
            ),
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
        # Specify backend explicitly due to multiple backends configured
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("account_home")
    return render(request, "account/register.html", {"form": form})


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
