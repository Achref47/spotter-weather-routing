from django.urls import path

from . import views

urlpatterns = [
      path("health", views.health),
      path("trips/analyze", views.analyze),
  ]