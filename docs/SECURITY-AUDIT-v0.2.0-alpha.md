# infra-TAK Security Audit (v0.2.0-alpha)

Date: 2026-03-12  
Scope: `app.py` web/API security posture and deployment hardening priorities for government use

---

## Executive Summary

infra-TAK is operationally strong but has several web-app security gaps that should be addressed before high-assurance/government deployment.  
Top risks are:

1. Trusting SSO headers without strict source validation
2. Command injection surfaces in shell command construction
3. Missing CSRF controls on state-changing APIs
4. Plaintext secret storage in settings

This document prioritizes fixes by risk and implementation effort.

---

## Findings (Prioritized)

### Critical

- **Header-based auth trust boundary**
  - Risk: If SSO headers are accepted from untrusted origins, login bypass is possible.
  - Current status: **Partially mitigated now** by trusting Authentik headers only when `request.remote_addr` is loopback (`127.0.0.1` / `::1`).
  - Remaining hardening: add explicit shared-secret proxy header validation and/or bind app to localhost behind Caddy only.

### High

- **Command injection risk in command strings**
  - Risk: User-influenced data interpolated into `shell=True` commands can become RCE.
  - Current status: **Partially mitigated now** for CloudTAK logs:
    - strict container-name regex allowlist
    - local `docker logs` switched to argv-style subprocess (no shell interpolation for container argument)
  - Remaining hardening: migrate more shell string calls to argv form where feasible.

- **Upload path traversal risk**
  - Risk: raw upload filename could write outside intended path.
  - Current status: **Mitigated now** using `secure_filename()` for TAK Server upload filenames.
  - Remaining hardening: add explicit extension allowlist + content-type sniffing where needed.

- **No CSRF protection on authenticated POST APIs**
  - Risk: Cross-site request forgery can trigger admin actions if session cookie is present.
  - Current status: Not mitigated.
  - Recommendation: CSRF token + Origin/Referer checks for all state-changing routes.

### Medium

- **Plaintext secrets in `.config/settings.json`**
  - Includes SSH password mode and third-party API keys (SMS providers).
  - Recommendation: migrate to environment/secret store and encrypt-at-rest for local persistence.

- **No brute-force/rate limit on login endpoints**
  - Recommendation: add `Flask-Limiter` to `/login`, `/`, and sensitive APIs.

- **Weak SSH trust mode for high assurance**
  - Current uses include `StrictHostKeyChecking=accept-new` and optional password mode.
  - Recommendation: key-only mode for production and host key pinning.

- **Missing explicit browser security headers**
  - Recommendation: add `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and HSTS in HTTPS/FQDN mode.

---

## Immediate Changes Applied (This Session)

1. **Auth header trust gated to local proxy source**
   - `_apply_authentik_session()` now ignores `X-Authentik-Username` unless request source is loopback.

2. **CloudTAK logs endpoint hardened**
   - `container` query param validated (`^[a-zA-Z0-9][a-zA-Z0-9_.-]*$`)
   - `lines` clamped to 1..500
   - Local `docker logs` command uses argv subprocess call, not shell interpolation.

3. **TAK package upload filename hardening**
   - Added `werkzeug.utils.secure_filename()`
   - Rejects invalid filenames before writing to disk.

4. **CSRF baseline on state-changing APIs**
   - Added same-origin validation for `POST/PUT/PATCH/DELETE` under `/api/*` (Origin/Referer host must match request host).
   - Localhost-only Guard Dog script endpoint (`/api/guarddog/send-sms`) is exempt.

5. **Built-in rate limiting (no new dependency)**
   - Login POSTs (`/` and `/login`): 12 attempts / 5 minutes per client IP.
   - State-changing API calls (`/api/*`): 240 write requests / minute per client IP.

---

## Recommended Hardening Roadmap

### Phase 1 (next sprint)

- Implement CSRF protections on all state-changing routes.
- Add login and API rate limiting.
- Add baseline security headers via `@app.after_request`.
- Review/convert high-risk `shell=True` calls that include dynamic inputs.

### Phase 2

- Secrets management redesign (remove plaintext credentials from settings file where possible).
- SSH mode hardening profile for regulated deployments (key-only + pinned host keys).
- Add audit logging for privileged actions.

### Phase 3

- Optional RBAC model (beyond single console password).
- CI security checks (SAST, dependency scanning, secret scanning).
- Deployment hardening profile docs (gov baseline checklist).

---

## Government Deployment Guardrails (Minimum)

- Place infra-TAK behind VPN or private management network.
- Restrict public access to management/backdoor port.
- Enforce least-privilege SSH and key-only authentication.
- Rotate and store credentials in enterprise secrets management.
- Enable centralized logging and immutable audit retention.

