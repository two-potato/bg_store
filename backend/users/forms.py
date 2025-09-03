from django import forms
from django.contrib.auth import get_user_model
from .models import UserProfile
from commerce.validators import validate_inn, validate_bik, validate_rs_with_bik
from commerce.models import DeliveryAddress, LegalEntityMembership

User = get_user_model()


class LoginForm(forms.Form):
    identifier = forms.CharField(label="Email или телефон", max_length=255)
    password = forms.CharField(widget=forms.PasswordInput)

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

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            prof, _ = UserProfile.objects.get_or_create(user=user)
            phone = self.cleaned_data.get("phone")
            if phone:
                prof.telegram_username = prof.telegram_username or None
                setattr(prof, "phone", phone)
            prof.save()
        return user


class ProfileForm(forms.ModelForm):
    phone = forms.CharField(label="Телефон", max_length=32, required=False)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        user = kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if user:
            self.fields["phone"].initial = getattr(getattr(user, "profile", None), "phone", "")

    def save(self, commit=True):
        user = super().save(commit=commit)
        prof, _ = UserProfile.objects.get_or_create(user=user)
        prof.phone = self.cleaned_data.get("phone")
        prof.save()
        return user


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
