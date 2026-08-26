"""Django project URL configuration."""
from django.contrib import admin
from django.urls import path, include

from django.views.generic import TemplateView

# UI route patterns with namespaces matching base.html
ui_dashboard_patterns = ([
    path("", TemplateView.as_view(template_name="dashboard/index.html"), name="index"),
], "dashboard")

ui_deepfake_patterns = ([
    path("monitor/", TemplateView.as_view(template_name="deepfake/monitor.html"), name="monitor"),
], "deepfake")

ui_phishing_patterns = ([
    path("scanner/", TemplateView.as_view(template_name="phishing/scanner.html"), name="scanner"),
], "phishing")

ui_graph_patterns = ([
    path("view/", TemplateView.as_view(template_name="threat_graph/view.html"), name="view"),
], "threat_graph")

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # API Routes
    path("api/deepfake/", include("apps.deepfake.urls")),
    path("api/phishing/", include("apps.phishing.urls")),
    path("api/identity/", include("apps.identity.urls")),
    path("api/graph/", include("apps.threat_graph.urls")),

    # Frontend UI Routes
    path("", include(ui_dashboard_patterns)),
    path("deepfake/", include(ui_deepfake_patterns)),
    path("phishing/", include(ui_phishing_patterns)),
    path("threat-graph/", include(ui_graph_patterns)),
]
