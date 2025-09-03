from django.urls import path
from .views import me, tg_webapp_auth
urlpatterns = [
    path("me/", me),
    path("auth/tg-webapp/", tg_webapp_auth),
]
