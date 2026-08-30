"""
Identity App Views
==================
Phase 4: Adds HTML session auth views (login, register, logout)
alongside the existing DRF API views for ECDSA key management.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import IdentityKey
from .serializers import IdentityKeySerializer
from .services import generate_key_pair_for_user

logger = logging.getLogger(__name__)
User = get_user_model()


# ── HTML Auth Views ────────────────────────────────────────────────────────────

def login_view(request: HttpRequest) -> HttpResponse:
    """GET/POST /auth/login/ — session-based login."""
    if request.user.is_authenticated:
        return redirect("/")

    error: str | None = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get("next") or request.POST.get("next") or "/"
                return redirect(next_url)
            else:
                error = "Invalid username or password."

    return render(request, "identity/login.html", {
        "error": error,
        "next": request.GET.get("next", "/"),
    })


def register_view(request: HttpRequest) -> HttpResponse:
    """GET/POST /auth/register/ — create user + generate ECDSA keypair."""
    if request.user.is_authenticated:
        return redirect("/")

    error: str | None = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm  = request.POST.get("password_confirm", "")

        # Server-side validation
        if not username or not password:
            error = "Username and password are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.objects.filter(username=username).exists():
            error = f"Username '{username}' is already taken."
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            # Generate ECDSA identity keypair and store public key
            try:
                _private_pem, identity_key = generate_key_pair_for_user(user)
                logger.info(
                    "ECDSA identity key created for user '%s' fingerprint=%s…",
                    username, identity_key.fingerprint[:16],
                )
            except Exception as exc:
                logger.warning("ECDSA keygen failed for user '%s': %s", username, exc)

            login(request, user)
            messages.success(request, f"Welcome, {username}! Your ECDSA identity key has been generated.")
            return redirect("/")

    return render(request, "identity/register.html", {"error": error})


def logout_view(request: HttpRequest) -> HttpResponse:
    """POST /auth/logout/ — session logout."""
    logout(request)
    return redirect("/auth/login/")


# ── DRF API Views ──────────────────────────────────────────────────────────────

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
