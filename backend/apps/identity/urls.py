"""Identity app URL patterns."""
from django.urls import path
from .views import IdentityKeyListView, MyIdentityKeyView

urlpatterns = [
    path("keys/", IdentityKeyListView.as_view(), name="identity-key-list"),
    path("me/", MyIdentityKeyView.as_view(), name="identity-key-me"),
]
