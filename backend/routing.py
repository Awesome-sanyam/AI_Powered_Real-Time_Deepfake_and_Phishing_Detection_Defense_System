"""
Django Channels WebSocket URL routing.
Registers all WebSocket consumers at their respective URL patterns.

Consumers:
    DeepfakeStreamConsumer  →  ws/deepfake/<session_id>/
    AlertFeedConsumer       →  ws/alerts/

Used by config/asgi.py → ProtocolTypeRouter → URLRouter.
"""
from django.urls import re_path
from apps.deepfake import consumers as deepfake_consumers
from apps.core import consumers as core_consumers

websocket_urlpatterns = [
    # Deepfake live scan stream — session_id binds to a Channels group
    re_path(
        r"^ws/deepfake/(?P<session_id>[^/]+)/$",
        deepfake_consumers.DeepfakeStreamConsumer.as_asgi(),
        name="ws-deepfake-stream",
    ),

    # Real-time alert broadcast feed — Flutter dashboard subscribes here
    re_path(
        r"^ws/alerts/$",
        core_consumers.AlertFeedConsumer.as_asgi(),
        name="ws-alerts-feed",
    ),
]
