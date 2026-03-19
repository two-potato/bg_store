from django import forms
from django.contrib.auth import get_user_model
import logging
from decimal import Decimal
from .models import UserProfile
from commerce.validators import validate_inn
from commerce.models import DeliveryAddress, LegalEntityMembership, SellerStore, CompanyMembership, Company, CompanyContact
import json
from catalog.models import Product, Series, SellerOffer, SellerInventory, ProductQuestion, ProductReview, ProductReviewComment, StockMovement, ProductDocument
from orders.models import OrderClaim, OrderSupportTicket

User = get_user_model()
log = logging.getLogger("users")


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label="Email или телефон",
        max_length=255,
        error_messages={"required": "Обязательное поле"},
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        error_messages={"required": "Обязательное поле"},
    )

    def clean(self):
        cleaned = super().clean()
        ident = cleaned.get("identifier", "").strip()
        if not ident:
            raise forms.ValidationError("Укажите email или телефон")
        return cleaned


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Повторите пароль")
    phone = forms.CharField(label="Телефон", max_length=32, required=False)

    class Meta:
        model = User
        fields = ["username", "email"]
        labels = {"username": "Имя пользователя", "email": "Email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email обязателен")
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Пользователь с таким email уже существует")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            prof, _ = UserProfile.objects.get_or_create(user=user)
            prof.full_name = (self.cleaned_data.get("username") or "").strip()
            prof.contact_email = (self.cleaned_data.get("email") or "").strip()
            phone = self.cleaned_data.get("phone")
            if phone:
                setattr(prof, "phone", phone)
            prof.save()
            log.info("user_registered", extra={"user_id": user.id})
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["full_name", "contact_email", "phone", "photo"]
        labels = {
            "full_name": "Имя",
            "contact_email": "Email",
            "phone": "Телефон",
            "photo": "Фото профиля",
        }

    def save(self, commit=True):
        profile: UserProfile = super().save(commit=commit)
        # Keep auth/login email consistent while profile remains source of truth for account UI.
        email = (self.cleaned_data.get("contact_email") or "").strip()
        user = profile.user
        if user.email != email:
            user.email = email
            user.save(update_fields=["email"])
        return profile


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "notify_email_orders",
            "notify_email_marketing",
            "notify_telegram_orders",
            "notify_telegram_marketing",
        ]
        labels = {
            "notify_email_orders": "Email: статусы заказов и документы",
            "notify_email_marketing": "Email: маркетинг и подборки",
            "notify_telegram_orders": "Telegram: статусы заказов",
            "notify_telegram_marketing": "Telegram: маркетинговые уведомления",
        }


class LegalEntityRequestForm(forms.Form):
    name = forms.CharField(label="Название проекта", max_length=255)
    inn = forms.CharField(label="ИНН", max_length=12, validators=[validate_inn])
    phone = forms.CharField(label="Общий телефон", max_length=32, required=True)
    bik = forms.CharField(label="БИК", max_length=9, required=True)
    checking_account = forms.CharField(label="Расчётный счёт", max_length=30, required=True)
    bank_name = forms.CharField(label="Банк", max_length=255, required=False)
    confirm = forms.BooleanField(label="Подтверждаю правильность данных", required=True)

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        # Простейшая нормализация: оставим цифры и +, проверим длину 7+
        digits = "+" + "".join(ch for ch in raw if ch.isdigit()) if raw.startswith("+") else "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 7:
            raise forms.ValidationError("Укажите корректный телефон")
        return raw

    def clean_bik(self):
        raw = (self.cleaned_data.get("bik") or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) != 9:
            raise forms.ValidationError("БИК должен содержать 9 цифр")
        return raw

    def clean_checking_account(self):
        rs_raw = (self.cleaned_data.get("checking_account") or "").strip()
        rs_digits = "".join(ch for ch in rs_raw if ch.isdigit())
        if len(rs_digits) != 20:
            raise forms.ValidationError("Расчётный счёт должен содержать 20 цифр")
        return rs_raw

    def clean(self):
        cleaned = super().clean()
        # Проверка р/с по БИК отключена — только длина/формат выше
        return cleaned


class AddressForm(forms.ModelForm):
    class Meta:
        model = DeliveryAddress
        fields = [
            "legal_entity",
            "label",
            "country",
            "city",
            "street",
            "postcode",
            "details",
            "latitude",
            "longitude",
            "is_default",
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Ограничим список юрлиц теми, где состоит пользователь
        if user is not None:
            entity_ids = LegalEntityMembership.objects.filter(user=user).values_list("legal_entity_id", flat=True)
            self.fields["legal_entity"].queryset = self.fields["legal_entity"].queryset.filter(id__in=entity_ids)
        # Разрешим сценарий только с координатами: поля адреса не обязательны на уровне формы
        for name in ("country", "city", "street", "postcode", "label"):
            if name in self.fields:
                self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        city = (cleaned.get("city") or "").strip()
        street = (cleaned.get("street") or "").strip()
        lat = cleaned.get("latitude")
        lon = cleaned.get("longitude")
        # Require either address fields or coordinates
        if not ((city and street) or (lat is not None and lon is not None)):
            raise forms.ValidationError("Укажите город и улицу или координаты (lat/lon)")
        return cleaned

    def save(self, commit=True):
        obj: DeliveryAddress = super().save(commit=False)
        # If coordinates provided but address fields empty, reverse geocode
        need_reverse = (
            (not obj.city or not obj.street) and obj.latitude is not None and obj.longitude is not None
        )
        if need_reverse:
            from commerce.utils import reverse_geocode
            result = reverse_geocode(float(obj.latitude), float(obj.longitude))
            if result:
                obj.country = result.get("country") or obj.country
                obj.city = result.get("city") or obj.city
                obj.street = result.get("street") or obj.street
                obj.postcode = result.get("postcode") or obj.postcode
        # Auto-generate label if missing
        if not (obj.label or "").strip():
            base = ", ".join([p for p in [obj.city or "", obj.street or ""] if p]) or "Адрес"
            candidate = base
            n = 1
            # ensure uniqueness per legal_entity
            from commerce.models import DeliveryAddress as DA
            while DA.objects.filter(legal_entity=obj.legal_entity, label=candidate).exclude(pk=obj.pk).exists():
                n += 1
                candidate = f"{base} ({n})"
            obj.label = candidate
        if commit:
            obj.save()
        return obj


class SellerStoreForm(forms.ModelForm):
    class Meta:
        model = SellerStore
        fields = ["name", "description", "legal_entity", "photo", "sla_target_hours", "commission_rate", "moderation_note"]
        labels = {
            "name": "Название магазина",
            "description": "Описание магазина",
            "legal_entity": "Юрлицо",
            "photo": "Аватар магазина",
            "sla_target_hours": "SLA, часов",
            "commission_rate": "Комиссия маркетплейса, %",
            "moderation_note": "Заметка модерации",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            entity_ids = LegalEntityMembership.objects.filter(user=user).values_list("legal_entity_id", flat=True)
            self.fields["legal_entity"].queryset = self.fields["legal_entity"].queryset.filter(id__in=entity_ids)
        for field_name in ("description", "photo", "sla_target_hours", "commission_rate", "moderation_note"):
            if field_name in self.fields:
                self.fields[field_name].required = False


class SellerProductCreateForm(forms.ModelForm):
    attributes_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="JSON-характеристики",
        help_text='Например: {"Материал":"Сталь","Диаметр":"26 см"}',
    )
    image_urls = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Ссылки на фото",
        help_text="По одной ссылке на строку",
    )
    image_files = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"accept": "image/*"}),
        label="Загрузить фото",
    )

    class Meta:
        model = Product
        fields = [
            "sku",
            "manufacturer_sku",
            "name",
            "brand",
            "series",
            "category",
            "material",
            "purpose",
            "pack_qty",
            "unit",
            "barcode",
            "price",
            "stock_qty",
            "min_order_qty",
            "lead_time_days",
            "publication_status",
            "is_new",
            "is_promo",
            "description",
        ]
        labels = {
            "sku": "SKU (8 цифр)",
            "manufacturer_sku": "Артикул производителя",
            "name": "Название товара",
            "brand": "Бренд",
            "series": "Серия",
            "category": "Категория",
            "material": "Материал",
            "purpose": "Назначение",
            "pack_qty": "Количество в упаковке",
            "unit": "Единица",
            "barcode": "Штрихкод",
            "price": "Цена",
            "stock_qty": "Остаток",
            "min_order_qty": "Минимальный заказ",
            "lead_time_days": "Срок поставки, дней",
            "publication_status": "Статус публикации",
            "is_new": "Новинка",
            "is_promo": "Акция",
            "description": "Описание",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["series"].queryset = Series.objects.select_related("brand").order_by("brand__name", "name")
        for name, initial in {
            "pack_qty": 1,
            "unit": "шт",
            "min_order_qty": 1,
            "lead_time_days": 0,
        }.items():
            self.fields[name].required = False
            self.fields[name].initial = initial
        self.fields["publication_status"].required = False
        self.fields["publication_status"].initial = Product.PublicationStatus.PUBLISHED
        if self.instance.pk and self.instance.attributes:
            self.fields["attributes_json"].initial = json.dumps(self.instance.attributes, ensure_ascii=False, indent=2)

    def clean_attributes_json(self):
        raw = (self.cleaned_data.get("attributes_json") or "").strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Некорректный JSON: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise forms.ValidationError("Характеристики должны быть объектом JSON")
        return payload

    def clean_image_urls(self):
        raw = self.cleaned_data.get("image_urls") or ""
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def save(self, commit=True):
        product: Product = super().save(commit=False)
        if self.user is not None:
            product.seller = self.user
        product.attributes = self.cleaned_data.get("attributes_json") or {}
        if commit:
            product.save()
            self.save_m2m()
        return product


class SellerProductImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV файл")

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        filename = (upload.name or "").lower()
        if not filename.endswith(".csv"):
            raise forms.ValidationError("Поддерживается только CSV шаблон")
        return upload


class SellerProductBulkActionForm(forms.Form):
    ACTION_CHOICES = (
        ("set_promo_on", "Включить промо"),
        ("set_promo_off", "Выключить промо"),
        ("set_new_on", "Пометить как новинка"),
        ("set_new_off", "Снять новинку"),
        ("add_stock", "Изменить остаток"),
        ("set_lead_time", "Установить ETA"),
        ("set_draft", "В черновик"),
        ("set_published", "Опубликовать"),
        ("set_archived", "В архив"),
    )

    action = forms.ChoiceField(choices=ACTION_CHOICES)
    stock_delta = forms.IntegerField(required=False, label="Delta остатка")
    lead_time_days = forms.IntegerField(required=False, min_value=0, label="ETA")

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        if action == "add_stock" and cleaned.get("stock_delta") is None:
            raise forms.ValidationError("Для изменения остатка нужен delta")
        if action == "set_lead_time" and cleaned.get("lead_time_days") is None:
            raise forms.ValidationError("Для ETA нужно число дней")
        return cleaned


class SellerOfferForm(forms.ModelForm):
    class Meta:
        model = SellerOffer
        fields = [
            "product",
            "offer_title",
            "price",
            "min_order_qty",
            "lead_time_days",
            "status",
            "warehouse_source",
        ]
        labels = {
            "product": "Товар",
            "offer_title": "Название оффера",
            "price": "Цена оффера",
            "min_order_qty": "Минимальный заказ",
            "lead_time_days": "Lead time, дней",
            "status": "Статус",
            "warehouse_source": "Источник склада",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.select_related("brand", "seller").order_by("name", "id")
        self.fields["min_order_qty"].required = False
        self.fields["lead_time_days"].required = False

    def save(self, commit=True):
        offer: SellerOffer = super().save(commit=False)
        if self.user is not None:
            offer.seller = self.user
            store = getattr(self.user, "seller_store", None)
            if store is not None:
                offer.seller_store = store
        if commit:
            offer.save()
        return offer


class SellerInventoryForm(forms.ModelForm):
    class Meta:
        model = SellerInventory
        fields = [
            "warehouse_name",
            "warehouse_code",
            "stock_qty",
            "reserved_qty",
            "incoming_qty",
            "eta_days",
            "is_primary",
        ]
        labels = {
            "warehouse_name": "Склад",
            "warehouse_code": "Код склада",
            "stock_qty": "Остаток",
            "reserved_qty": "Резерв",
            "incoming_qty": "В пути",
            "eta_days": "ETA, дней",
            "is_primary": "Основной склад",
        }

    def clean(self):
        cleaned = super().clean()
        stock_qty = int(cleaned.get("stock_qty") or 0)
        reserved_qty = int(cleaned.get("reserved_qty") or 0)
        if reserved_qty > stock_qty:
            raise forms.ValidationError("Резерв не может быть больше остатка")
        return cleaned


class InventoryAdjustmentForm(forms.Form):
    inventory_id = forms.IntegerField(widget=forms.HiddenInput)
    field_type = forms.ChoiceField(label="Поле", choices=StockMovement.FieldType.choices)
    delta = forms.IntegerField(label="Изменение")
    reason = forms.CharField(label="Причина", max_length=255, required=False)


class SellerQuestionAnswerForm(forms.ModelForm):
    class Meta:
        model = ProductQuestion
        fields = ["answer_text", "is_public"]
        labels = {
            "answer_text": "Ответ продавца",
            "is_public": "Показывать вопрос публично",
        }


class SellerReviewReplyForm(forms.ModelForm):
    class Meta:
        model = ProductReviewComment
        fields = ["text"]
        labels = {"text": "Ответ продавца"}


class CompanyMemberInviteForm(forms.Form):
    identifier = forms.CharField(label="Username или email", max_length=255)
    role = forms.ChoiceField(label="Роль", choices=CompanyMembership.Role.choices)
    approval_limit = forms.DecimalField(label="Лимит согласования", max_digits=12, decimal_places=2, required=False, min_value=0)
    is_default_approver = forms.BooleanField(label="Default approver", required=False)

    def clean_identifier(self):
        return (self.cleaned_data.get("identifier") or "").strip()


class CompanyMemberUpdateForm(forms.Form):
    role = forms.ChoiceField(label="Роль", choices=CompanyMembership.Role.choices)
    approval_limit = forms.DecimalField(label="Лимит согласования", max_digits=12, decimal_places=2, required=False, min_value=0)
    is_default_approver = forms.BooleanField(label="Default approver", required=False)


class ApprovalPolicyForm(forms.Form):
    is_enabled = forms.BooleanField(label="Включить согласование", required=False)
    auto_approve_below = forms.DecimalField(label="Автосогласование до", max_digits=12, decimal_places=2, required=False, min_value=0)
    require_approver_role = forms.BooleanField(label="Требовать роль approver", required=False)
    require_comment = forms.BooleanField(label="Комментарий обязателен", required=False)
    required_approvals_count = forms.IntegerField(label="Сколько согласований нужно", min_value=1, required=False)
    max_pending_hours = forms.IntegerField(label="SLA pending, часов", min_value=1, required=False)


class CompanySettingsForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "display_name",
            "procurement_email",
            "procurement_phone",
            "invoice_email",
            "preferred_payment_method",
            "payment_comment",
            "is_active",
        ]
        labels = {
            "display_name": "Название компании в кабинете",
            "procurement_email": "Email закупок",
            "procurement_phone": "Телефон закупок",
            "invoice_email": "Email для счетов",
            "preferred_payment_method": "Предпочитаемый способ оплаты",
            "payment_comment": "Комментарий к реквизитам",
            "is_active": "Компания активна",
        }


class CompanyContactForm(forms.ModelForm):
    class Meta:
        model = CompanyContact
        fields = ["name", "email", "phone", "role", "is_default", "notes"]
        labels = {
            "name": "Имя контакта",
            "email": "Email",
            "phone": "Телефон",
            "role": "Роль",
            "is_default": "Контакт по умолчанию",
            "notes": "Комментарий",
        }


class ProductDocumentForm(forms.ModelForm):
    class Meta:
        model = ProductDocument
        fields = ["title", "kind", "file_url"]
        labels = {
            "title": "Название документа",
            "kind": "Тип",
            "file_url": "Ссылка на файл",
        }


class OrderClaimForm(forms.ModelForm):
    class Meta:
        model = OrderClaim
        fields = ["claim_type", "message"]
        labels = {
            "claim_type": "Тип обращения",
            "message": "Описание проблемы",
        }


class OrderClaimUpdateForm(forms.ModelForm):
    class Meta:
        model = OrderClaim
        fields = ["status", "seller_response", "resolution_comment"]
        labels = {
            "status": "Статус диспута",
            "seller_response": "Ответ продавца",
            "resolution_comment": "Финальное решение",
        }


class ShipmentCreateForm(forms.Form):
    warehouse_name = forms.CharField(label="Склад", max_length=120, required=False)
    delivery_method = forms.CharField(label="Способ доставки", max_length=120, required=False)


class SellerOrderItemCancelForm(forms.Form):
    seller_order_item_id = forms.IntegerField(widget=forms.HiddenInput)
    cancel_qty = forms.IntegerField(min_value=1, label="Отменить количество")


class OrderSupportTicketForm(forms.ModelForm):
    class Meta:
        model = OrderSupportTicket
        fields = ["topic", "subject", "message"]
        labels = {
            "topic": "Тема обращения",
            "subject": "Тема",
            "message": "Описание",
        }


class OrderSupportTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = OrderSupportTicket
        fields = ["status", "resolution_comment"]
        labels = {
            "status": "Статус",
            "resolution_comment": "Комментарий / решение",
        }
