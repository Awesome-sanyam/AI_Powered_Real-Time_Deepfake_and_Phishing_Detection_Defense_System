"""
URL Forensics — Heuristic phishing signal extractor.
No ML required — runs in microseconds.

Signals detected:
  suspicious-tld-high      — highest-risk free TLDs (.tk, .ml, .ga, .cf, .gq)
  suspicious-tld-med       — medium-risk TLDs (.xyz, .top, .click, .live, .icu)
  suspicious-tld-low       — elevated-risk country TLDs (.ru, .cn, .pw, .cc)
  deep-subdomain           — >3 subdomain levels
  high-entropy-domain      — random-looking domain names (Shannon entropy >4.0)
  brand-impersonation      — known brand keyword in non-brand domain
  homoglyph-ascii          — numeric/ASCII substitution (0→o, 1→l, rn→m)
  homoglyph-cyrillic       — Cyrillic character substitution (а→a, е→e, etc.)
  zero-width-char          — invisible Unicode character injection (ZWSP, RLO, etc.)
  ip-address-hostname      — raw IP used instead of domain
  suspicious-path-keyword  — login/verify/secure/update/expire in path
  urgency-path-keyword     — urgent/expire/suspended/action-required in path
  long-url                 — >100 chars total
  no-https                 — plain HTTP scheme
  excessive-redirects      — multiple redirect-style patterns in URL
"""
from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import urlparse, unquote

# ─────────────────────────────────────────────────────────────────────────────
# Risk tables
# ─────────────────────────────────────────────────────────────────────────────

# Tiered TLD risk scoring (score contribution)
_SUSPICIOUS_TLDS_HIGH = {".tk", ".ml", ".ga", ".cf", ".gq"}          # +0.30
_SUSPICIOUS_TLDS_MED  = {".xyz", ".top", ".click", ".link", ".live",  # +0.20
                          ".icu", ".buzz", ".vip", ".fun", ".online"}
_SUSPICIOUS_TLDS_LOW  = {".ru", ".cn", ".pw", ".cc", ".ws", ".info"}  # +0.10

# ASCII homoglyph substitutions (character-level)
_HOMOGLYPHS_ASCII = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "6": "b", "7": "t", "8": "b", "9": "q",
    "rn": "m", "vv": "w", "cl": "d", "li": "li",
}

# Cyrillic → Latin lookalike map (Unicode confusables)
_CYRILLIC_TO_LATIN = {
    "\u0430": "a",  # Cyrillic а → a
    "\u0435": "e",  # Cyrillic е → e
    "\u043e": "o",  # Cyrillic о → o
    "\u0440": "p",  # Cyrillic р → p
    "\u0441": "c",  # Cyrillic с → c
    "\u0445": "x",  # Cyrillic х → x
    "\u0443": "y",  # Cyrillic у → y
    "\u0456": "i",  # Cyrillic і → i
    "\u0458": "j",  # Cyrillic ј → j
    "\u04cf": "l",  # Cyrillic ӏ → l
}

# Zero-width and direction-override Unicode characters
_ZERO_WIDTH_CHARS = {
    "\u200b",  # Zero-Width Space (ZWSP)
    "\u200c",  # Zero-Width Non-Joiner
    "\u200d",  # Zero-Width Joiner
    "\u200e",  # Left-to-Right Mark
    "\u200f",  # Right-to-Left Mark
    "\u202a",  # Left-to-Right Embedding
    "\u202b",  # Right-to-Left Embedding
    "\u202c",  # Pop Directional Formatting
    "\u202d",  # Left-to-Right Override
    "\u202e",  # Right-to-Left Override (RLO — used in filename spoofing)
    "\u2060",  # Word Joiner
    "\ufeff",  # Byte Order Mark / Zero-Width No-Break Space
}

# Known brand domains — brand keyword must be the SLD for it to be legit
_BRAND_KEYWORDS = {
    "paypal", "apple", "google", "microsoft", "amazon",
    "netflix", "facebook", "instagram", "linkedin",
    "chase", "wellsfargo", "bankofamerica", "citibank",
    "irs", "gov", "usps", "fedex", "dhl", "ups",
    "dropbox", "icloud", "outlook", "office365", "docusign",
}

# Path segments common in credential-harvesting pages
_SUSPICIOUS_PATH_KEYWORDS = {
    "login", "signin", "sign-in", "verify", "secure", "update",
    "confirm", "account", "password", "credential", "authenticate",
    "oauth", "token", "reset", "recovery", "verify-identity",
    "account-suspended", "wire-transfer", "gift-card",
}

# Urgency signals in URL paths
_URGENCY_PATH_KEYWORDS = {
    "urgent", "expire", "expiring", "expired", "suspended",
    "action-required", "immediate", "alert", "locked", "blocked",
    "urgent-request", "account-suspended",
}

# High-threat deterministic red flags in URLs (+0.40 static penalty)
_HIGH_THREAT_URL_KEYWORDS = {
    "wire-transfer", "wiretransfer", "urgent-request", "gift-card",
    "giftcard", "account-suspended", "accountsuspended",
    "verify-identity", "verifyidentity", "verify-your-identity",
}


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


def _has_cyrillic(text: str) -> bool:
    """Check if the string contains any Cyrillic look-alike characters."""
    return any(ch in _CYRILLIC_TO_LATIN for ch in text)


def _has_zero_width(text: str) -> bool:
    """Check if the string contains invisible Unicode control characters."""
    return any(ch in _ZERO_WIDTH_CHARS for ch in text)


class URLForensics:
    """
    Fast heuristic URL risk analyser.
    Returns risk_score [0.0–1.0] and a list of human-readable signal strings.
    """

    def analyze(self, url: str) -> dict:
        signals: list[str] = []
        risk_score: float = 0.0

        # URL-decode the input to catch encoded attacks (%2F, %20, etc.)
        try:
            url_decoded = unquote(url)
        except Exception:
            url_decoded = url

        try:
            parsed = urlparse(
                url_decoded if "://" in url_decoded else f"https://{url_decoded}"
            )
        except Exception:
            return {
                "risk_score": 1.0,
                "signals": ["unparseable-url"],
                "entropy": 0.0,
                "subdomain_depth": 0,
            }

        hostname = parsed.hostname or ""
        path     = parsed.path.lower() if parsed.path else ""
        full_url = url_decoded.lower()

        # ── 1. Zero-width / invisible character injection ─────────────────────
        if _has_zero_width(url):
            signals.append("zero-width-char-injection")
            risk_score += 0.40

        # ── 2. Cyrillic homoglyph substitution ───────────────────────────────
        if _has_cyrillic(hostname):
            cyrillic_chars = [ch for ch in hostname if ch in _CYRILLIC_TO_LATIN]
            signals.append(f"homoglyph-cyrillic:{','.join(cyrillic_chars[:3])}")
            risk_score += 0.45

        # ── 3. ASCII homoglyph substitution ──────────────────────────────────
        for fake, real in _HOMOGLYPHS_ASCII.items():
            if fake in hostname:
                signals.append(f"homoglyph-ascii:{fake}->{real}")
                risk_score += 0.20

        # ── 4. Tiered TLD risk scoring ─────────────────────────────────────────
        for tld in _SUSPICIOUS_TLDS_HIGH:
            if hostname.endswith(tld):
                signals.append(f"suspicious-tld-high:{tld}")
                risk_score += 0.30
        for tld in _SUSPICIOUS_TLDS_MED:
            if hostname.endswith(tld):
                signals.append(f"suspicious-tld-med:{tld}")
                risk_score += 0.20
        for tld in _SUSPICIOUS_TLDS_LOW:
            if hostname.endswith(tld):
                signals.append(f"suspicious-tld-low:{tld}")
                risk_score += 0.10

        # ── 5. Excessive subdomains (>3 levels) ───────────────────────────────
        subdomain_depth = len(hostname.split("."))
        if subdomain_depth > 3:
            signals.append(f"deep-subdomain:{subdomain_depth}-levels")
            risk_score += 0.15

        # ── 6. High Shannon entropy domain (DGA-style) ────────────────────────
        domain_clean = hostname.replace(".", "")
        entropy = _shannon_entropy(domain_clean)
        if entropy > 4.0:
            signals.append(f"high-entropy-domain:{entropy:.2f}")
            risk_score += 0.20

        # ── 7. Brand impersonation in hostname ─────────────────────────────────
        for brand in _BRAND_KEYWORDS:
            if brand in hostname.lower():
                # It's OK if the brand IS the registered domain (e.g. paypal.com)
                # Flag only if brand appears as subdomain or with extra text
                sld = hostname.lower().split(".")[-2] if subdomain_depth >= 2 else hostname.lower()
                if sld != brand:
                    signals.append(f"brand-impersonation:{brand}")
                    risk_score += 0.30

        # ── 8. IP address as hostname ──────────────────────────────────────────
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", hostname):
            signals.append("ip-address-hostname")
            risk_score += 0.35

        # ── 9. Suspicious credential-harvesting path keywords ─────────────────
        for keyword in _SUSPICIOUS_PATH_KEYWORDS:
            if keyword in path:
                signals.append(f"suspicious-path:{keyword}")
                risk_score += 0.10
                break  # one flag is enough

        # ── 9b. High-threat deterministic red flags in URL (+0.40 static penalty) ─
        for keyword in _HIGH_THREAT_URL_KEYWORDS:
            if keyword in full_url or keyword.replace("-", "") in full_url:
                signals.append(f"high-threat-url-keyword:{keyword}")
                risk_score += 0.40
                break

        # ── 10. Urgency path keywords ─────────────────────────────────────────
        for keyword in _URGENCY_PATH_KEYWORDS:
            if keyword in path:
                signals.append(f"urgency-path:{keyword}")
                risk_score += 0.12
                break

        # ── 11. Long URL ───────────────────────────────────────────────────────
        if len(url) > 100:
            signals.append(f"long-url:{len(url)}-chars")
            risk_score += 0.10

        # ── 12. HTTP (not HTTPS) ───────────────────────────────────────────────
        if parsed.scheme == "http":
            signals.append("no-https")
            risk_score += 0.10

        # ── 13. Multiple redirect patterns (url= param, redirect=) ────────────
        redirect_count = len(re.findall(r"(?:url|redirect|redir|return|next)=https?", full_url))
        if redirect_count > 0:
            signals.append(f"redirect-chain:{redirect_count}")
            risk_score += 0.15

        return {
            "risk_score":     min(round(risk_score, 4), 1.0),
            "signals":        signals,
            "entropy":        round(entropy, 3),
            "subdomain_depth": subdomain_depth,
        }
