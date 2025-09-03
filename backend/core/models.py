from django.db import models
from django.utils import timezone
from datetime import timedelta

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class IdempotencyKey(models.Model):
    user_id = models.IntegerField()
    route = models.CharField(max_length=255)
    key = models.CharField(max_length=64)
    response = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = (("user_id","route","key"),)

    @classmethod
    def create_or_get(cls, user_id:int, route:str, key:str, ttl_sec:int=600):
        obj, created = cls.objects.get_or_create(
            user_id=user_id, route=route, key=key,
            defaults={"expires_at": timezone.now() + timedelta(seconds=ttl_sec)}
        )
        return obj, created
