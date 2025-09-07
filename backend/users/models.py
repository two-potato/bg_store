from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import TimeStampedModel

class User(AbstractUser):
    email = models.EmailField(blank=True, null=True)

class Friendship(TimeStampedModel):
    """Tracks friendship requests/acceptances between users."""
    from_user = models.ForeignKey('User', related_name='friendships_initiated', on_delete=models.CASCADE)
    to_user = models.ForeignKey('User', related_name='friendships_received', on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = (('from_user', 'to_user'),)

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({'accepted' if self.accepted else 'pending'})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=32, blank=True, null=True)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=255, blank=True, null=True)
    discount = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    photo = models.ImageField(upload_to='user_photos/', null=True, blank=True)
    friends = models.ManyToManyField('self', through=Friendship, symmetrical=False, blank=True, related_name='friend_of')

    def __str__(self):
        return f"{self.user.username} profile"
