"""Django project URL configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/deepfake/", include("apps.deepfake.urls")),
    path("api/phishing/", include("apps.phishing.urls")),
    path("api/identity/", include("apps.identity.urls")),
    path("api/graph/", include("apps.threat_graph.urls")),
]
