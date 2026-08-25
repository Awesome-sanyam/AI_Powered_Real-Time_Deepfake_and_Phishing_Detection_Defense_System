"""
URL Forensics — Heuristic phishing signal extractor.
No ML required — runs in microseconds.

Signals detected:
  suspicious-tld         — free TLDs heavily abused by phishers
  deep-subdomain         — >3 subdomain levels
  high-entropy-domain    — random-looking domain names
  brand-impersonation    — known brand keyword in non-brand domain
  homoglyph              — visually similar character substitutions
  ip-address-hostname    — raw IP used instead of domain
  suspicious-path-keyword — login/verify/secure/update in path
  long-url               — >100 chars total
  no-https               — plain HTTP scheme
"""
from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import urlparse


# Homoglyph map: visually similar chars used to impersonate domains
_HOMOGLYPHS = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "6": "b", "7": "t", "8": "b", "9": "q",
    "rn": "m", "vv": "w",
}

_SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top",
    ".click", ".link", ".live", ".icu", ".buzz",
}

_BRAND_KEYWORDS = {
    "paypal", "apple", "google", "microsoft", "amazon",
    "netflix", "facebook", "instagram", "linkedin", "bank",
}

# Path segments commonly used in credential-harvesting pages
_SUSPICIOUS_PATH_KEYWORDS = {
    "login", "signin", "verify", "secure", "update",
    "confirm", "account", "password", "credential",
}


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


class URLForensics:
    """
    Fast heuristic URL risk analyser.
    Returns risk_score [0.0–1.0] and a list of human-readable signal strings.
    """

    def analyze(self, url: str) -> dict:
        signals: list[str] = []
        risk_score: float = 0.0

        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
        except Exception:
            return {"risk_score": 1.0, "signals": ["unparseable-url"], "entropy": 0.0, "subdomain_depth": 0}

        hostname = parsed.hostname or ""
        path = parsed.path.lower() if parsed.path else ""

        # 1. Suspicious TLD
        for tld in _SUSPICIOUS_TLDS:
            if hostname.endswith(tld):
                signals.append(f"suspicious-tld:{tld}")
                risk_score += 0.25

        # 2. Excessive subdomains (> 3 levels)
        subdomain_depth = len(hostname.split("."))
        if subdomain_depth > 3:
            signals.append(f"deep-subdomain:{subdomain_depth}-levels")
            risk_score += 0.15

        # 3. High entropy domain (random-looking, e.g. DGA domains)
        entropy = _shannon_entropy(hostname.replace(".", ""))
        if entropy > 4.0:
            signals.append(f"high-entropy-domain:{entropy:.2f}")
            risk_score += 0.20

        # 4. Brand impersonation in hostname
        for brand in _BRAND_KEYWORDS:
            if brand in hostname.lower() and not hostname.lower().endswith(f"{brand}.com"):
                signals.append(f"brand-impersonation:{brand}")
                risk_score += 0.30

        # 5. Homoglyph attack in hostname
        for fake, real in _HOMOGLYPHS.items():
            if fake in hostname:
                signals.append(f"homoglyph:{fake}->{real}")
                risk_score += 0.25

        # 6. IP address used as hostname
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", hostname):
            signals.append("ip-address-hostname")
            risk_score += 0.35

        # 7. Suspicious path keyword (credential harvesting indicators)
        for keyword in _SUSPICIOUS_PATH_KEYWORDS:
            if keyword in path:
                signals.append(f"suspicious-path:{keyword}")
                risk_score += 0.10
                break  # one match is enough to flag

        # 8. Long URL
        if len(url) > 100:
            signals.append(f"long-url:{len(url)}-chars")
            risk_score += 0.10

        # 9. HTTP (not HTTPS)
        if parsed.scheme == "http":
            signals.append("no-https")
            risk_score += 0.10

        return {
            "risk_score": min(round(risk_score, 4), 1.0),
            "signals": signals,
            "entropy": round(entropy, 3),
            "subdomain_depth": subdomain_depth,
        }
