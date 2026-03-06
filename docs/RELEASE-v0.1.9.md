# infra-TAK v0.1.9

Release Date: 2026-03-04

---

## Guard Dog — UX and Hardening (v0.1.9-alpha)

- **Sidebar:** Guard Dog appears **directly under Console** when installed (high-priority placement).
- **Apply Docker log limits:** Button on the Guard Dog page applies 50 MB × 3 files per container (no redeploy of Authentik, Node-RED, etc.). Reduces risk of a single container log filling the disk.
- **Collapsible sections:** Notifications, Database maintenance (CoT), and Activity log are collapsible (click header to expand/collapse), matching TAK Server and Help page style.
- **4GB swap on deploy:** When Guard Dog is deployed (or auto-deployed with TAK Server), the console ensures a 4GB swap file at `/swapfile` exists and is enabled (from reference TAK Server Hardening script — memory stability under load).

---

## Authentik deploy reliability

- **Swap before stress:** At the start of Authentik deploy (before pulling images and starting containers), the console ensures 4GB swap exists. So the box has swap before postgres + server + worker run — reduces OOM and unhealthy on small VPS where Guard Dog (which also adds swap) may deploy later.
- **PostgreSQL then server:** PostgreSQL is started first; we wait for `pg_isready` (up to ~48s), then start the Authentik server and worker. Avoids the server hitting the DB before it accepts connections (fewer 502s and connection-refused on fresh installs).

---

## Connect LDAP / CoreConfig

- When writing CoreConfig (full replace or password resync), the console ensures **`adminGroup="ROLE_ADMIN"`** is present in the LDAP block. It adds the attribute if missing and verifies with grep after write; deploy fails with a clear message if it cannot be set. Prevents "no channels" and wrong admin console access (webadmin getting WebTAK instead of admin UI).

---

## CloudTAK deploy

- **Step 4:** Build output streamed; 45 min timeout.
- **Step 5:** Timeout 600s (10 min).
- **Step 6:** Waits for **`http://localhost:5000/api/connections`** to return 200, 401, or 403 (not just "port 5000 open") before declaring "CloudTAK API is responding (backend ready)". Avoids 502 when Caddy proxies to map.fqdn before the CloudTAK backend is ready.

---

## MediaMTX

- **Web editor:** The `mediamtx-webeditor` systemd unit is created and enabled/started **only when** `/opt/mediamtx-webeditor/mediamtx_config_editor.py` exists. If the clone fails and there is no local fallback, the service is not created — no restart loop. MediaMTX streaming still works; only the web config UI is unavailable until the editor file is present.
- **Clone:** Always uses the **default branch** of `takwerx/mediamtx-installer` (no infratak branch). After install, `mediamtx_ldap_overlay.py` from the infra-TAK repo is applied when Authentik/LDAP is present. Log: "LDAP/Authentik detected — will apply LDAP overlay after install".

---

## COMMANDS.md and server visibility

- **Pull then restart (two steps):** Separate copy-paste blocks for pull and for `sudo systemctl restart takwerx-console`.
- **Server impact and memory:** New section with `free -h`, `docker stats --no-stream`, and `top -o %MEM` / `top -o %CPU` for quick resource snapshots, plus a note on typical heavy users (TAK Server Java, PostgreSQL, Docker stack).
- **TAK Server packages:** Deploy and upgrade use `<install_path>/uploads/` (e.g. `/root/infra-TAK/uploads/`); you can rsync or scp the .deb there before deploy or upgrade.
- **Other:** Disk full / container logs, CloudTAK 502 and backend readiness, TAK client "No channels found" and new-groups sync delay (60s refresh; client reconnect after 1–2 min).

---

## Unattended upgrades

- Spinner on the toggle so "Disabling…" is visible while the disable request runs.

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

- `app.py`: Authentik deploy (4GB swap before pull/start, PostgreSQL first then pg_isready then server/worker), Guard Dog deploy (9 monitors + service monitors, 4GB swap on deploy), Guard Dog sidebar under Console, Apply Docker log limits API + card, collapsible Guard Dog sections, TAK Server update flow, client cert creation, cert expiry API, Intermediate CA rotation, Root CA rotation, revoke old CA, ca-info API, collapsible TAK Server/Help sections, console dashboard cert expiry; **Connect LDAP:** ensure `adminGroup="ROLE_ADMIN"` in CoreConfig LDAP block (add/verify, fail with message if missing); **CloudTAK:** Step 4 stream build/45 min, Step 5 timeout 600s, Step 6 wait for `/api/connections` 200/401/403; **MediaMTX:** clone default branch only, webeditor service/enable/start only when editor file exists; **Unattended upgrades:** spinner on toggle
- `static/takserver.js`: Extracted TAK Server inline JS to external file
- `static/guarddog.js`: Guard Dog page JavaScript, `gdSectionToggle`, `gdApplyDockerLogLimits`
- `scripts/guarddog/`: All monitor scripts, health endpoint, SMS helper
- `docs/TAK_Server_OpenAPI_v0.json`: In-repo TAK Server OpenAPI 3.1 spec
- `docs/REFERENCES.md`: Added OpenAPI spec reference
- `docs/GUARDDOG.md`: Root CA / Int CA monitor and rotation workflow, 4GB swap, Docker log limits
- `docs/COMMANDS.md`: Pull dev only, restart console only, **pull then restart (two steps)**, **server impact and memory** (free, docker stats, top), disk full / container logs, CloudTAK 502/backend readiness, TAK client no channels / new-groups sync
- `docs/DISK-AND-LOGS.md`: Disk full recovery, Docker log limits, optional journal/prune
- `docs/HANDOFF-LDAP-AUTHENTIK.md`: Full v0.1.9 session state (Connect LDAP adminGroup, CloudTAK Step 6, MediaMTX webeditor guard, COMMANDS, pull/restart two steps)

## Status

All modules production-ready. Guard Dog fully operational (monitors, 4GB swap, Docker log limits button, collapsible UI). Certificate lifecycle management (create, rotate, revoke) verified.
