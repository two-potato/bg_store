from django.urls import path
from .views import metrics_view
urlpatterns = [ path("", metrics_view) ]
