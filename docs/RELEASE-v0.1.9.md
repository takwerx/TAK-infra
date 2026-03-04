# infra-TAK v0.1.9

Release Date: 2026-03-03

---

## Guard Dog — Full Health Monitoring

Guard Dog is now fully operational with **9 monitors** for TAK Server plus service monitors for Authentik, MediaMTX, Node-RED, and CloudTAK.

| Monitor | Interval | Action |
|---------|----------|--------|
| Port 8089 | 1 min | Auto-restart after 3 failures |
| Process (5 Java procs) | 1 min | Auto-restart after 3 failures |
| Network (1.1.1.1 / 8.8.8.8) | 1 min | Alert only |
| PostgreSQL | 5 min | Restart + alert |
| CoT DB size | 6 hr | Alert at 25GB / 40GB |
| OOM | 1 min | Auto-restart + alert |
| Disk | 1 hr | Alert at 80% / 90% |
| Certificate (LE / TAK) | Daily | Alert at 40 days |
| **Root CA / Intermediate CA** | **Escalating** | **Alert at 90, 75, 60, 45, 30 days, then daily** |

Health endpoint on port 8888 for Uptime Robot / external monitoring.

## Certificate Management

### Create Client Certificates

New section on the TAK Server page. Enter a client name, load groups from TAK Server, assign Read (OUT), Write (IN), or Both permissions per group, and download the `.p12` file.

### Rotate Intermediate CA

Phased rotation workflow:
- Generate new Intermediate CA while keeping the old one active for transition
- Regenerates server cert, admin cert, user cert
- Old CA stays in truststore — existing clients continue working
- Users re-enroll via TAK Portal before the old CA is revoked
- **Revoke Old CA** button removes the old CA from the truststore when ready
- TAK Portal certs updated automatically during rotation

### Rotate Root CA

Hard cutover for the rare Root CA rotation (~10 year cycle):
- Generates entirely new PKI: Root CA, Intermediate CA, server cert, admin/user certs
- Updates truststore, CoreConfig, TAK Portal
- Restarts TAK Server
- All clients must re-enroll via QR code
- Double confirmation required

### Certificate Expiry Visibility

- **Console dashboard**: Root CA and Intermediate CA time remaining shown on the TAK Server module card (`Root 10y · Int 1y 12mo 4d`), color-coded green/yellow/red
- **TAK Server page**: Detailed expiry in the status banner and Certificates section
- **Rotate CA cards**: Each shows its relevant CA expiry with time remaining

## TAK Server Update

Upload a `.deb` package with a progress bar, cancel button, and success/failure indicators. The update is blocked if no file has been uploaded.

## UI Overhaul

### TAK Server Page — Collapsible Sections

All major sections are now collapsible cards (uppercase monospace headers, chevron toggle):
- Update TAK Server
- Database Maintenance (CoT)
- Certificates
- Rotate Intermediate CA
- Rotate Root CA
- Create Client Certificate
- Server Log

### Help Page — Collapsible Sections

All help sections converted to the same collapsible card style, left-aligned to match the rest of the console. Reordered: Deployment Order first, then Backdoor, Console Password, Reset Password, SSH Hardening, Uninstall All, Docs.

### Console Dashboard

Removed hidden "Manage" ghost elements from module cards for consistent card heights.

## Changes

- `app.py`: Guard Dog deploy (9 monitors + service monitors), TAK Server update flow, client cert creation, cert expiry API, Intermediate CA rotation, Root CA rotation, revoke old CA, ca-info API, collapsible sections, console dashboard cert expiry, Help page overhaul
- `static/takserver.js`: Extracted TAK Server inline JS to external file
- `static/guarddog.js`: Guard Dog page JavaScript
- `scripts/guarddog/`: All monitor scripts, health endpoint, SMS helper
- `docs/TAK_Server_OpenAPI_v0.json`: In-repo TAK Server OpenAPI 3.1 spec
- `docs/REFERENCES.md`: Added OpenAPI spec reference
- `docs/GUARDDOG.md`: Updated with Root CA / Int CA monitor and rotation workflow
- `docs/HANDOFF-LDAP-AUTHENTIK.md`: Full v0.1.9 session state

## Status

All modules production-ready. Guard Dog fully operational. Certificate lifecycle management (create, rotate, revoke) verified.
