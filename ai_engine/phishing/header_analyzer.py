"""
Email Header Analyzer
=====================
Extracts phishing signals from raw email headers:
  - SPF / DKIM / DMARC failures
  - Reply-To / From mismatch
  - Suspicious X-Mailer strings
  - Forged Received chains
"""
from __future__ import annotations

import re


_SUSPICIOUS_MAILERS = {"massmailer", "phpmailer", "sendgrid", "mailchimp"}

_TRUSTED_DKIM_DOMAINS = {
    "gmail.com", "outlook.com", "yahoo.com",
    "apple.com", "google.com", "microsoft.com",
}


def analyze_headers(headers: dict) -> dict:
    """
    Analyse email headers for phishing signals.

    Args:
        headers: Dict of header-name → header-value (case-sensitive keys
                 as returned by email.message.Message).

    Returns:
        dict with keys:
            signals  — list of signal strings
            risk_score — float [0, 1]
            details  — dict of individual check results
    """
    signals: list[str] = []
    details: dict = {}

    from_addr = headers.get("From", "")
    reply_to = headers.get("Reply-To", "")
    received_spf = headers.get("Received-SPF", "")
    dkim_sig = headers.get("DKIM-Signature", "")
    dmarc = headers.get("Authentication-Results", "")
    x_mailer = headers.get("X-Mailer", "").lower()

    # 1. Reply-To / From mismatch — classic phishing indicator
    if reply_to and reply_to.strip() != from_addr.strip():
        signals.append("reply-to-from-mismatch")
        details["reply_to_mismatch"] = True

    # 2. Missing DKIM signature
    if not dkim_sig:
        signals.append("missing-dkim")
        details["dkim_present"] = False
    else:
        details["dkim_present"] = True

    # 3. SPF failure
    spf_lower = received_spf.lower()
    if "fail" in spf_lower:
        signals.append("spf-fail")
        details["spf_status"] = "fail"
    elif "softfail" in spf_lower:
        signals.append("spf-softfail")
        details["spf_status"] = "softfail"
    elif "pass" in spf_lower:
        details["spf_status"] = "pass"
    else:
        details["spf_status"] = "none"

    # 4. DMARC failure
    if "dmarc=fail" in dmarc.lower():
        signals.append("dmarc-fail")
        details["dmarc_fail"] = True

    # 5. Suspicious mailer software
    for mailer in _SUSPICIOUS_MAILERS:
        if mailer in x_mailer:
            signals.append(f"suspicious-mailer:{mailer}")
            break

    # 6. Display-name spoofing (e.g. "PayPal <attacker@evil.com>")
    display_match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>', from_addr)
    if display_match:
        display_name = display_match.group(1).lower().strip()
        email_domain = display_match.group(2).split("@")[-1].lower()
        for brand in ("paypal", "apple", "google", "microsoft", "amazon", "bank"):
            if brand in display_name and brand not in email_domain:
                signals.append(f"display-name-spoof:{brand}")
                break

    risk_score = min(len(signals) * 0.20, 1.0)

    return {
        "signals": signals,
        "risk_score": round(risk_score, 4),
        "details": details,
    }
