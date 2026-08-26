"""Authentication and account-entry HTML views."""

from __future__ import annotations

import hashlib
import logging
import requests
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from core.logging_utils import log_calls
from core.notifications import send_mail_message
from shopfront.cart_store import merge_session_cart_with_persistent

from ..forms import LoginForm, RegisterForm
from ..models import UserProfile
from ..api.views import verify_init_data

log = logging.getLogger("users")
User = get_user_model()


def _build_email_confirm_token(user) -> str:
    nonce = secrets.token_urlsafe(24)
    cache.set(_email_confirm_cache_key(user.id, nonce), 1, timeout=24 * 60 * 60)
    payload = f"{user.id}:{(user.email or '').strip().lower()}:{nonce}"
    return _email_confirm_signer().sign(payload)


def _email_confirm_signer() -> TimestampSigner:
    return TimestampSigner(salt="users.email-confirm")


def _email_confirm_cache_key(user_id: int, nonce: str) -> str:
    digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
    return f"users:email-confirm:{user_id}:{digest}"


def _consume_email_confirm_token(token: str):
    try:
        payload = _email_confirm_signer().unsign(token, max_age=24 * 60 * 60)
    except (BadSignature, SignatureExpired):
        return None, "Ссылка подтверждения истекла или недействительна"

    try:
        uid_raw, email, nonce = payload.split(":", 2)
        uid = int(uid_raw)
    except (TypeError, ValueError):
        return None, "Некорректная ссылка подтверждения"

    user = User.objects.filter(id=uid).first()
    if not user or (user.email or "").strip().lower() != (email or "").strip().lower():
        return None, "Пользователь для подтверждения не найден"

    cache_key = _email_confirm_cache_key(uid, nonce)
    if not cache.get(cache_key):
        return None, "Ссылка подтверждения уже использована или недействительна"
    cache.delete(cache_key)
    return user, ""


def _send_email_confirmation(request, user) -> bool:
    token = _build_email_confirm_token(user)
    confirm_url = request.build_absolute_uri(f"{reverse('confirm_email')}?token={token}")
    text = (
        "Подтвердите ваш email для входа в аккаунт Servio.\n\n"
        f"Ссылка подтверждения: {confirm_url}\n\n"
        "Ссылка действует 24 часа."
    )
    return send_mail_message(
        subject="[Servio] Подтверждение email",
        message=text,
        recipient_list=[user.email],
        logger=log,
        extra={"user_id": user.id, "email": user.email},
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


def _client_ip(request) -> str:
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        if xff:
            return xff
    return request.META.get("REMOTE_ADDR", "unknown")


def _normalize_login_identifier(identifier: str | None) -> str:
    return " ".join(str(identifier or "").strip().lower().split())


def _login_fail_keys(request, identifier: str | None = None) -> list[str]:
    keys = [f"auth:login:fail:ip:{_client_ip(request)}"]
    normalized = _normalize_login_identifier(identifier)
    if normalized:
        ident_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        keys.append(f"auth:login:fail:ident:{ident_hash}")
    return keys


def _mark_login_failure(request, identifier: str | None = None) -> None:
    timeout = int(getattr(settings, "LOGIN_CAPTCHA_WINDOW_SECONDS", 900))
    for key in _login_fail_keys(request, identifier):
        current = int(cache.get(key, 0) or 0)
        cache.set(key, current + 1, timeout=timeout)


def _clear_login_failures(request, identifier: str | None = None) -> None:
    cache.delete_many(_login_fail_keys(request, identifier))


def _captcha_required(request, identifier: str | None = None) -> bool:
    threshold = int(getattr(settings, "LOGIN_CAPTCHA_THRESHOLD", 5))
    if threshold <= 0:
        return False
    return any(int(cache.get(key, 0) or 0) >= threshold for key in _login_fail_keys(request, identifier))


def _auth_rate_limit_key(request, scope: str) -> str:
    return f"auth:{scope}:post:{_client_ip(request)}"


def _auth_post_rate_limited(request, *, scope: str, limit: int, window_seconds: int) -> bool:
    if limit <= 0 or window_seconds <= 0:
        return False
    key = _auth_rate_limit_key(request, scope)
    current = int(cache.get(key, 0) or 0)
    if current >= limit:
        return True
    cache.set(key, current + 1, timeout=window_seconds)
    return False


def _login_page_context(*, form, captcha_required: bool, include_google: bool = True) -> dict:
    context = {
        "form": form,
        "seo_title": "Вход в аккаунт — Servio",
        "seo_description": "Авторизация в личном кабинете Servio.",
        "seo_robots": "noindex,nofollow",
        "captcha_required": captcha_required,
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
    }
    if include_google:
        context["google_oauth_enabled"] = _google_oauth_enabled()
    return context


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
    except (requests.RequestException, ValueError):
        return False, "Не удалось проверить капчу. Повторите попытку."
    if bool(payload.get("success")):
        return True, ""
    return False, "Проверка капчи не пройдена"


def _google_oauth_enabled() -> bool:
    return bool(
        getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
        .get("google", {})
        .get("APP", {})
        .get("client_id")
    )


@require_http_methods(["GET", "POST"])
@log_calls()
def login_view(request):
    if request.user.is_authenticated:
        return redirect("account_home")
    form = LoginForm(request.POST or None)
    raw_identifier = (request.POST.get("identifier") or "").strip()
    captcha_required = _captcha_required(request, raw_identifier)
    if request.method == "POST":
        rate_limit = int(getattr(settings, "AUTH_LOGIN_RATE_LIMIT_ATTEMPTS", 30))
        rate_window = int(getattr(settings, "AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 3600))
        if _auth_post_rate_limited(
            request,
            scope="login",
            limit=rate_limit,
            window_seconds=rate_window,
        ):
            log.warning(
                "auth_login_rate_limited",
                extra={"client_ip": _client_ip(request), "limit": rate_limit, "window_seconds": rate_window},
            )
            messages.error(request, "Слишком много попыток входа. Попробуйте позже.")
            return render(
                request,
                "account/login.html",
                _login_page_context(form=form, captcha_required=True),
                status=429,
            )
    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["identifier"].strip()
        password = form.cleaned_data["password"]
        if captcha_required:
            token = (request.POST.get("cf-turnstile-response") or "").strip()
            ok, captcha_error = _verify_turnstile(token, _client_ip(request))
            if not ok:
                _mark_login_failure(request, ident)
                messages.error(request, captcha_error)
                return render(
                    request,
                    "account/login.html",
                    _login_page_context(form=form, captcha_required=True),
                )
        user = None
        for field in ("username", "email"):
            try:
                candidate = User.objects.get(**{field: ident})
            except User.DoesNotExist:
                continue
            user = authenticate(request, username=candidate.username, password=password)
            if user:
                break
        if not user:
            try:
                candidate = User.objects.get(profile__phone=ident)
            except User.DoesNotExist:
                candidate = None
            if candidate is not None:
                user = authenticate(request, username=candidate.username, password=password)
        if user:
            _clear_login_failures(request, ident)
            login(request, user)
            request.session["cart"] = merge_session_cart_with_persistent(user, request.session.get("cart", {}))
            request.session.modified = True
            return redirect(_safe_next(request))
        _mark_login_failure(request, ident)
        captcha_required = _captcha_required(request, ident)
        messages.error(request, "Неверные учётные данные")
    return render(
        request,
        "account/login.html",
        _login_page_context(form=form, captcha_required=captcha_required),
    )


@require_http_methods(["GET", "POST"])
@log_calls()
def register_view(request):
    if request.user.is_authenticated:
        return redirect("account_home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        rate_limit = int(getattr(settings, "AUTH_REGISTER_RATE_LIMIT_ATTEMPTS", 20))
        rate_window = int(getattr(settings, "AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS", 3600))
        if _auth_post_rate_limited(
            request,
            scope="register",
            limit=rate_limit,
            window_seconds=rate_window,
        ):
            log.warning(
                "auth_register_rate_limited",
                extra={"client_ip": _client_ip(request), "limit": rate_limit, "window_seconds": rate_window},
            )
            messages.error(request, "Слишком много попыток регистрации. Попробуйте позже.")
            return render(
                request,
                "account/register.html",
                {
                    "form": form,
                    "seo_title": "Регистрация — Servio",
                    "seo_description": "Создание аккаунта на Servio.",
                    "seo_robots": "noindex,nofollow",
                    "google_oauth_enabled": _google_oauth_enabled(),
                },
                status=429,
            )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if not _send_email_confirmation(request, user):
            log.warning(
                "register_email_confirmation_send_failed",
                extra={"user_id": user.id, "email": user.email},
            )
            messages.error(request, "Не удалось отправить письмо подтверждения. Попробуйте позже.")
            return render(
                request,
                "account/register.html",
                {
                    "form": form,
                    "seo_title": "Регистрация — Servio",
                    "seo_description": "Создание аккаунта на Servio.",
                    "seo_robots": "noindex,nofollow",
                    "google_oauth_enabled": _google_oauth_enabled(),
                },
            )
        messages.success(request, "Письмо с подтверждением отправлено на вашу почту")
        return redirect("login")
    return render(
        request,
        "account/register.html",
        {
            "form": form,
            "seo_title": "Регистрация — Servio",
            "seo_description": "Создание аккаунта на Servio.",
            "seo_robots": "noindex,nofollow",
            "google_oauth_enabled": _google_oauth_enabled(),
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
    user, error_message = _consume_email_confirm_token(token)
    if user is None:
        messages.error(request, error_message)
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
    try:
        telegram_id = int(tg_user.get("id"))
    except (TypeError, ValueError):
        log.info("twa_login_missing_tg_id")
        messages.error(request, "Некорректный Telegram ID")
        return redirect("login")
    username = tg_user.get("username") or f"tg_{telegram_id}"
    user, created = User.objects.get_or_create(username=f"tg_{telegram_id}", defaults={"email": ""})
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.telegram_id = telegram_id
    profile.telegram_username = username
    profile.save()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    log.info("twa_login_ok", extra={"user_id": user.id, "telegram_id": telegram_id, "user_created": created})
    return redirect("account_home")
