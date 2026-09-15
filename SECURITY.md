# 🔒 Enterprise Security Policy & Vulnerability Disclosure

## 1. Scope & Zero-Trust Security Philosophy

**DEFENCESYS** is engineered for deployment in high-assurance Security Operations Centers (SOCs) and critical enterprise infrastructure. As a defense platform tasked with identifying deepfakes and targeted social engineering attacks, the security and integrity of the platform itself are paramount.

The platform strictly adheres to the **Zero-Trust Architecture (ZTA)** principles defined in **NIST SP 800-207**:
* **Explicit Verification:** Continuous authentication across WebSocket and REST communication channels.
* **Least Privilege Access:** Role-Based Access Control (RBAC) separating security analysts, SOC administrators, and automated ingestion services.
* **Assume Breach:** All AI-generated decisions and forensic logs are cryptographically signed using **ECDSA P-256** to prevent data tampering even in the event of database or transport-layer compromise.

---

## 2. Supported Versions

Security updates, patches, and threat-model reviews are actively provided for the following releases:

| Version Branch | Release Status | Security Support | Cryptographic Standard |
|---|---|:---:|---|
| **`v1.0.x` (Current)** | Production / Stable | ✅ Active Support | NIST P-256 / SHA-256 |
| `< 1.0.0` | Development Pre-releases | ❌ End of Life | N/A |

---

## 3. Cryptographic Non-Repudiation & Attestation Architecture

All verdicts produced by the **CrossModalVerificationEngine** and the **PhishingDetectionEngine** are sealed with an asymmetric cryptographic signature before being persisted or transmitted over WebSockets:

$$\text{Payload} = \text{SessionID} \,\|\, \text{Verdict} \,\|\, \text{Confidence} \,\|\, \text{Timestamp}$$
$$\sigma = \text{ECDSA-Sign}_{K_{\text{priv}}}(\text{SHA-256}(\text{Payload}))$$

### Integrity Verification Protocol
1. The active public key is accessible via the Identity Vault API at `/api/identity/keys/` in PEM format (`X.509 SubjectPublicKeyInfo`).
2. External Security Information and Event Management (SIEM) systems (e.g., Splunk, Microsoft Sentinel) can independently verify any forensic report using standard cryptographic tooling without trusting the database contents.
3. If an ECDSA signature fails mathematical verification:
   * The incident must be escalated as a **Severity 1 (P1)** tampering event.
   * Review Daphne ASGI and PostgreSQL audit logs for unauthorized record modification.

---

## 4. Network Isolation & Service Hardening Guidelines

For production enterprise deployments, enforce the following network boundaries:

```
[ External Users / Analysts ]
              │
              ▼  (HTTPS / WSS on Port 443 -> Reverse Proxy)
┌─────────────────────────────────────────────────────────────┐
│ Daphne ASGI Orchestrator (Port 8000)                        │
└─────────────┬───────────────────────────────┬───────────────┘
              │ (Private Subnet / Loopback)    │ (Private Subnet / Loopback)
              ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ AI Engine (Port 8001)     │   │ Redis Broker (Port 6379)  │
│ *NO DIRECT PUBLIC INGRESS*│   │ *BIND 127.0.0.1 ONLY*     │
└───────────────────────────┘   └───────────────────────────┘
              │                               │
              ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ PostgreSQL 16 (Port 5432) │   │ Neo4j 5 Graph (Port 7687) │
│ *ENFORCE SSL CONNECTION*  │   │ *AUTHENTICATION REQUIRED* │
└───────────────────────────┘   └───────────────────────────┘
```

* **AI Engine Isolation:** Port `8001` (FastAPI Uvicorn) should **never** be exposed directly to public ingress. All client traffic must be routed through the Django authentication and rate-limiting gateway.
* **Secrets Management:** Ensure `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and `NEO4J_PASSWORD` are securely injected via vault solutions (e.g., HashiCorp Vault, AWS Secrets Manager, 1Password Secrets Automation) rather than committed to source control.

---

## 5. Vulnerability Severity Categorization & Response SLAs

We categorize security findings according to the **Common Vulnerability Scoring System (CVSS v3.1)**:

| Severity Level | CVSS v3.1 Score | Example Scenarios | Initial Response SLA | Target Resolution SLA |
|---|:---:|---|:---:|:---:|
| 🔴 **Critical (P1)** | 9.0 – 10.0 | Remote Code Execution (RCE), Authentication Bypass, ECDSA Private Key Compromise | **< 24 Hours** | **72 Hours** |
| 🟠 **High (P2)** | 7.0 – 8.9 | SQL Injection, Server-Side Request Forgery (SSRF), Denial of Service of AI Engine | **< 48 Hours** | **7 Business Days** |
| 🟡 **Medium (P3)** | 4.0 – 6.9 | Cross-Site Scripting (XSS), Insecure Direct Object References (IDOR), Rate Limit Bypass | **< 5 Business Days** | **14 Business Days** |
| 🟢 **Low (P4)** | 0.1 – 3.9 | Information Disclosure (e.g., server banner leak), Minor CSRF on non-sensitive actions | **< 7 Business Days** | **30 Business Days** |

---

## 6. Coordinated Vulnerability Disclosure (CVD) Workflow

We appreciate the responsible contributions of security researchers and ethical hackers worldwide:

1. **Private Reporting:**
   * **Do NOT report security vulnerabilities via public GitHub issues.**
   * Contact the project maintainers privately:
     * **Sanyam Gehlot** ([@Awesome-sanyam](https://github.com/Awesome-sanyam))
2. **Report Contents:**
   Please include:
   * Detailed description of the vulnerability.
   * Affected components and endpoints.
   * Step-by-step proof-of-concept (PoC) or reproduction script.
   * Potential threat impact and remediation suggestions.
3. **Mutual Commitment:**
   * We will acknowledge receipt of your disclosure within the specified SLA.
   * We will provide regular status updates as patches are engineered and tested.
   * Once a patch is released, we will publicly credit the researcher in our release notes (unless anonymity is preferred).
