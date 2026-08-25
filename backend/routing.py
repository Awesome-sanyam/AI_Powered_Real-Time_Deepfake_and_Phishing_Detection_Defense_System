"""
Django Channels WebSocket URL routing.
"""
from django.urls import re_path
from apps.deepfake import consumers as deepfake_consumers

websocket_urlpatterns = [
    # ws://host/ws/deepfake/<session_id>/
    re_path(
        r"^ws/deepfake/(?P<session_id>[^/]+)/$",
        deepfake_consumers.DeepfakeStreamConsumer.as_asgi(),
    ),
]
