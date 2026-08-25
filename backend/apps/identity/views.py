"""Identity app views."""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import IdentityKey
from .serializers import IdentityKeySerializer


class IdentityKeyListView(generics.ListAPIView):
    """GET /api/identity/keys/ — list all identity keys (admin use)."""
    queryset = IdentityKey.objects.select_related("user").all()
    serializer_class = IdentityKeySerializer


class MyIdentityKeyView(generics.RetrieveAPIView):
    """GET /api/identity/me/ — get the calling user's identity key."""
    serializer_class = IdentityKeySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> IdentityKey:
        return IdentityKey.objects.get(user=self.request.user)
