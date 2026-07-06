# Security Policy

Thank you for helping keep TheKnowledgeOrbits and its users safe. This document explains what's in
scope, how to report a vulnerability responsibly, and what to expect after you report one.

## Supported Scope

TheKnowledgeOrbits is a single, actively-developed application (no maintained legacy versions). Only
the code currently on the `main` branch, and the live production deployment built from it, are in
scope for security reports.

**In scope:**

- The Django/DRF backend (`backend/`) and all engines within it
- The Next.js frontend (`frontend/`)
- Authentication, authorization, and session/token handling
- The production deployment configuration (`render.yaml`, CI/CD workflows) to the extent a
  misconfiguration is publicly observable or exploitable
- The AI research-agent engine, including prompt-injection and tool-abuse vectors specific to it

**Out of scope:**

- Third-party services this project depends on (Render, Vercel, Supabase, Cloudinary, Brevo, Sentry,
  Langfuse, Groq, Cerebras, HuggingFace, Tavily, Exa) — please report vulnerabilities in those
  platforms directly to their respective security teams
- Denial-of-service attacks achieved purely through volume (rate-limit/cost exhaustion), rather than
  a logic flaw — please report the underlying flaw instead of demonstrating volumetric abuse
- Issues that require physical access to a user's device, a compromised browser/OS, or social
  engineering of the maintainer
- Automated scanner output with no demonstrated, project-specific impact (e.g., a missing
  `X-Content-Type-Options` header with no exploitable consequence)
- Vulnerabilities in dependencies that are already publicly disclosed and awaiting an upstream patch
  (please still let us know if you believe this project is exposed, but a CVE ID alone is sufficient)

## Reporting a Vulnerability

**Please do not open a public GitHub issue, discussion, or pull request for a security
vulnerability.** Public disclosure before a fix is available puts real users at risk.

Instead, report privately using one of these channels:

1. **Preferred — GitHub Private Vulnerability Reporting:** If enabled on this repository, use the
   **"Report a vulnerability"** option under the repository's **Security** tab. This creates a private
   advisory visible only to the maintainer.
2. **Email:** Email the maintainer directly at
   [vishal25goyal25@gmail.com](mailto:vishal25goyal25@gmail.com) with the subject line
   `SECURITY: TheKnowledgeOrbits — <short description>`.

**Please include, where possible:**

- A clear description of the vulnerability and its potential impact
- Steps to reproduce, or a minimal proof-of-concept (no need to demonstrate against live production
  data — a local reproduction is preferred)
- The affected component/engine/endpoint, if known
- Your assessment of severity (optional, but helpful)

**Please do not:**

- Access, modify, or exfiltrate data belonging to other users while investigating a report
- Perform testing that could degrade the availability of the live service for real users
- Publicly disclose the issue before a fix has been released and a reasonable disclosure window has
  passed (see below)

## What to Expect

- **Acknowledgment:** within 5 business days of a report.
- **Initial assessment:** within 10 business days — confirming reproduction, severity, and an
  estimated remediation timeline.
- **Resolution:** timeline depends on severity and complexity; critical issues (e.g., authentication
  bypass, data exposure across users) are prioritized for the fastest reasonable fix.
- **Disclosure:** this is a solo-maintained project without a formal bug-bounty program. Credit will
  be given (if desired) in the fix's commit message or release notes once a patch is live, unless you
  prefer to remain anonymous. Please allow at least 90 days, or until a fix ships (whichever is
  sooner), before any public disclosure.

## A Note on This Project's Security Posture

This project follows standard security practices appropriate to its scale, including (non-exhaustively):
hashed and salted password storage, JWT-based authentication with role-based authorization, HTTPS/HSTS
enforcement and secure cookie configuration in production, environment-based secrets management (no
credentials committed to source control), input validation at API boundaries, and structured error
tracking that avoids leaking internal details to end users.

Like any actively-developed solo project, it has known, honestly-tracked areas for future hardening
(e.g., rate limiting is not yet applied to every authentication endpoint). Reports pointing out gaps
like this are welcome and will be triaged like any other report — this document does not claim the
project is free of vulnerabilities, only that reports are taken seriously and handled responsibly.

## Recognition

If you report a valid vulnerability and would like public credit, let us know in your report and
we'll acknowledge your contribution once the fix is released.

Thank you for practicing responsible disclosure and helping make this project safer for its users.
