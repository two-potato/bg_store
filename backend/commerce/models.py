from django.db import models
from django.conf import settings
from core.models import TimeStampedModel
from .validators import validate_inn, validate_bik, validate_rs_with_bik

User = settings.AUTH_USER_MODEL

class LegalEntity(TimeStampedModel):
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=12, unique=True, validators=[validate_inn])
    bik = models.CharField(max_length=9, validators=[validate_bik])
    checking_account = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    members = models.ManyToManyField(User, through="LegalEntityMembership", related_name="legal_entities")
    def clean(self): validate_rs_with_bik(self.checking_account, self.bik)
    def __str__(self):
        if self.inn:
            return f"{self.name} (ИНН {self.inn})"
        return self.name or f"Юрлицо #{self.pk}"

class LegalEntityMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER="owner","Владелец"
        ADMIN="admin","Админ"
        MANAGER="manager","Менеджер"
        VIEWER="viewer","Наблюдатель"
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MANAGER)
    class Meta:
        unique_together = (("user", "legal_entity"),)
    def __str__(self):
        return f"{self.user} → {self.legal_entity} [{self.role}]"

class DeliveryAddress(TimeStampedModel):
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name="delivery_addresses")
    label = models.CharField(max_length=255)
    country = models.CharField(max_length=128)
    city = models.CharField(max_length=128)
    street = models.CharField(max_length=255)
    postcode = models.CharField(max_length=32)
    details = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    class Meta:
        unique_together = (("legal_entity", "label"),)
    def save(self,*a,**kw):
        super().save(*a,**kw)
        if self.is_default:
            DeliveryAddress.objects.filter(legal_entity=self.legal_entity,is_default=True).exclude(pk=self.pk).update(is_default=False)
    def __str__(self):
        return f"{self.label} — {self.city}, {self.street}"

class MembershipRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING="pending","На рассмотрении"
        APPROVED="approved","Одобрено"
        REJECTED="rejected","Отклонено"
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="membership_requests")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name="membership_requests")
    comment = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

class LegalEntityCreationRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING="pending","На рассмотрении"
        APPROVED="approved","Одобрено"
        REJECTED="rejected","Отклонено"
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entity_creation_requests")
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=12, validators=[validate_inn])
    bik = models.CharField(max_length=9, validators=[validate_bik])
    checking_account = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    # Проверка р/с отключена по требованию; оставим только декларативную модель
    def clean(self):
        pass
