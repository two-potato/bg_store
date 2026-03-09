from django.db import models
from django.conf import settings
from django.utils.text import slugify
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


class Company(TimeStampedModel):
    legal_entity = models.OneToOneField(LegalEntity, on_delete=models.CASCADE, related_name="company")
    display_name = models.CharField(max_length=255, blank=True, default="")
    procurement_email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"

    def __str__(self):
        return self.display_name or self.legal_entity.name

class MembershipRole(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    def __str__(self):
        return self.name

class LegalEntityMembership(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE)
    role = models.ForeignKey(MembershipRole, on_delete=models.PROTECT, null=True, blank=True)
    class Meta:
        unique_together = (("user", "legal_entity"),)
    def save(self, *args, **kwargs):
        if self.role_id is None:
            self.role, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})
        super().save(*args, **kwargs)
    def __str__(self):
        role = getattr(self.role, "name", "-")
        return f"{self.user} → {self.legal_entity} [{role}]"


class CompanyMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        BUYER = "buyer", "Buyer"
        APPROVER = "approver", "Approver"
        FINANCE = "finance", "Finance"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="company_memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.BUYER)
    approval_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_default_approver = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="unique_user_company_membership"),
        ]

    def __str__(self):
        return f"{self.user} -> {self.company} [{self.role}]"


class ApprovalPolicy(TimeStampedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="approval_policy")
    is_enabled = models.BooleanField(default=False)
    auto_approve_below = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    require_approver_role = models.BooleanField(default=True)
    require_comment = models.BooleanField(default=False)
    max_pending_hours = models.PositiveIntegerField(default=24)

    class Meta:
        verbose_name = "Политика согласования"
        verbose_name_plural = "Политики согласования"

    def __str__(self):
        return f"ApprovalPolicy({self.company})"

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

class RequestStatus(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    def __str__(self):
        return self.name

class MembershipRequest(TimeStampedModel):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="membership_requests")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name="membership_requests")
    comment = models.TextField(blank=True, null=True)
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT, null=True, blank=True)
    def save(self, *args, **kwargs):
        if self.status_id is None:
            self.status, _ = RequestStatus.objects.get_or_create(code="pending", defaults={"name": "На рассмотрении"})
        super().save(*args, **kwargs)

class LegalEntityCreationRequest(TimeStampedModel):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entity_creation_requests")
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=12, validators=[validate_inn])
    bik = models.CharField(max_length=9, validators=[validate_bik])
    checking_account = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT, null=True, blank=True)
    # Проверка р/с отключена по требованию; оставим только декларативную модель
    def clean(self):
        pass
    def save(self, *args, **kwargs):
        if self.status_id is None:
            self.status, _ = RequestStatus.objects.get_or_create(code="pending", defaults={"name": "На рассмотрении"})
        super().save(*args, **kwargs)


class SellerStore(TimeStampedModel):
    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        SUSPENDED = "suspended", "Suspended"

    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_store")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, related_name="seller_stores")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    description = models.TextField(blank=True, default="")
    photo = models.ImageField(upload_to="seller_store_photos/", null=True, blank=True)
    moderation_status = models.CharField(max_length=16, choices=ModerationStatus.choices, default=ModerationStatus.PENDING)
    sla_target_hours = models.PositiveIntegerField(default=24)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Магазин продавца"
        verbose_name_plural = "Магазины продавцов"

    def __str__(self):
        return f"{self.name} — {self.owner}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or f"store-{self.owner_id or 'x'}"
            candidate = base
            suffix = 2
            while SellerStore.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class StoreReview(TimeStampedModel):
    store = models.ForeignKey(SellerStore, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="store_reviews")
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True, default="")
    is_verified_buyer = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "user"], name="unique_store_review_per_user"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"StoreReview(store={self.store_id}, user={self.user_id}, rating={self.rating})"
