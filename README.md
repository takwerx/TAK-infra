# infra-TAK

Tea Awarness Kit Infrastructure Management Platform.

One clone. One password. One URL. Manage everything from your browser.

**Goal: universal installer.** Currently supported platform: **Ubuntu 22.04 LTS**.

## What Is This?

A unified web console for deploying and managing TAK ecosystem infrastructure:

- **TAK Server** — Upload your .deb/.rpm, configure, deploy, manage CoreConfig — all from the browser
- **Authentik** — Identity provider with automated LDAP configuration for TAK Server auth
- **TAK Portal** — User and certificate management portal with auto-configured Authentik + TAK Server integration
- **Caddy SSL** — Let's Encrypt certificates and reverse proxy management
- **CloudTAK** — Browser-based TAK client
- **MediaMTX** — Video streaming server for real-time feeds
- **Node-RED** — Flow-based automation engine, protected behind Authentik forward auth
- **Email Relay** — Outbound email for notifications and alerts
- **Guard Dog** — TAK Server health monitoring and auto-recovery (port 8089, processes, OOM, PostgreSQL, CoT DB size, disk, certificates; optional monitors for Authentik, Node-RED, MediaMTX, CloudTAK)

*All modules are production-ready.*

No more SSH. No more editing XML by hand. No more running scripts and hoping.

## Quick Start

```bash
git clone --depth 1 -b dev https://github.com/takwerx/infra-TAK.git
cd infra-TAK
chmod +x start.sh
sudo ./start.sh
```

For the stable branch use `git clone --depth 1 https://github.com/takwerx/infra-TAK.git` (no `-b dev`).

The script will:
1. Detect your OS (**Ubuntu 22.04 only** for now; goal is a universal installer)
2. Install Python dependencies
3. Ask you to set an admin password
4. Start the web console

Then open your browser to the URL shown and log in.

**Updating:** After `git pull`, restart the console with `sudo systemctl restart takwerx-console`. Your password and config live in the install directory’s `.config/`. If you run `start.sh` from a different clone or path, the service keeps using the original install directory so your password continues to work.

**Password not working after update?** Use the **backdoor**: **https://&lt;VPS_IP&gt;:5001**. If login spins or fails, on the server run (from the directory where you do `git pull`, e.g. `/root/infra-TAK`): **`sudo ./fix-console-after-pull.sh`** — it pins the config path in the systemd unit and prompts you to set a new password so you can log in again. Alternatively run `sudo ./reset-console-password.sh` from that same directory. After pulling, open the Caddy module and re-save your domain once so the Caddyfile (login bypass) is applied.

## Recovery / backdoor (when Authentik or Caddy is broken)

If Authentik or Caddy is down and you can’t reach **https://infratak.yourdomain.com**:

- **Backdoor:** Open **https://&lt;VPS_IP&gt;:5001** in your browser (use the server’s real IP, not the domain). Log in with the **console password** you set when you ran `start.sh`. That path skips Caddy and Authentik, so you can get back into the console and fix things.

The console password is stored as a **hash** in the install directory at `.config/auth.json` (e.g. `/root/infra-TAK/.config/auth.json`). You **cannot** recover the plaintext password from that file. If you forget it:

```bash
cd /root/infra-TAK   # or your install path
sudo ./reset-console-password.sh
```

Enter a new password twice; the script updates `.config/auth.json` and restarts the console. Then use **https://&lt;VPS_IP&gt;:5001** with the new password. Store the console password somewhere safe (e.g. password manager); it’s your only way in when the domain or Authentik is broken.

## Deployment Order

Deploy services in this order — each step auto-configures the next:

```
1. Caddy SSL         Set your FQDN, get Let's Encrypt certs (recommended first if using a domain)
         ↓
2. Authentik         Identity provider + LDAP outpost (automated deploy)
         ↓
3. Email Relay       Optional; configure SMTP for password recovery
         ↓
4. TAK Server        Upload .deb, deploy, configure ports + certs
         ↓
5. Connect LDAP      On TAK Server page — patches CoreConfig, creates webadmin in Authentik
         ↓
6. TAK Portal        User/cert management portal
         ↓
7. Anything else     CloudTAK, Node-RED, MediaMTX — any order
```

**Connect LDAP** runs after TAK Server deploy and wires LDAP auth to CoreConfig. 8446 webadmin login and QR enrollment work immediately after. **For MediaMTX-only (or standalone Authentik):** Deploy Authentik without TAK Server — it skips CoreConfig and webadmin; add TAK Server later and use Connect LDAP.

## What Gets Automated

**Authentik Deploy (~7 minutes):**
Console ensures 4GB swap and starts PostgreSQL first, then server/worker after the DB is ready (reduces OOM and 502s on small VPS). Bootstrap credentials generated, LDAP blueprint installed, Docker Compose patched with standalone LDAP container, API polled for outpost token, CoreConfig.xml patched with LDAP auth block, TAK Server restarted.

**TAK Portal Deploy (~4 minutes):**
Repository cloned, container built, TAK Server certs (admin.p12, tak-ca.pem) copied into container, settings.json auto-configured with Authentik URL/token and TAK Server connection, forward auth configured in Caddy, 2-minute sync wait for Authentik outpost.

After deployment, create users in TAK Portal — they flow through Authentik → LDAP → TAK Server automatically.

## Requirements

- **Ubuntu 22.04 LTS** (currently the only supported platform; goal is a universal installer). Fresh installation recommended.
- Root access
- 8GB+ RAM recommended for TAK Server
- Internet connection for initial setup
- TAK Server .deb or .rpm package from [tak.gov](https://tak.gov)

## Architecture

```
start.sh                    ← One CLI command to launch everything
├── app.py                  ← Flask web application (HTTPS on :5001)
├── uploads/                ← Uploaded .deb/.rpm packages
└── .config/                ← Auth + settings (gitignored)
```

## Ports

| Service | Port | Description |
|---------|------|-------------|
| TAK-infra Console | 5001 | Management web UI |
| TAK Server | 8089 | TAK client connections (TLS) |
| TAK Server | 8443 | WebGUI (cert auth) |
| TAK Server | 8446 | WebGUI (Let's Encrypt, password auth) |
| Authentik | 9090 | Identity provider |
| LDAP | 389 | LDAP auth for TAK Server |
| TAK Portal | 3000 | User management portal |

## Access Modes

**IP Address Mode** — Self-signed certificate, works anywhere (field deployments, no DNS needed)

**FQDN Mode** — Caddy + Let's Encrypt for proper SSL. Required for TAK client QR enrollment. Can upgrade from IP mode through the web console without SSH.

## QR Code Enrollment

| Client | Status | Notes |
|--------|--------|-------|
| ATAK (Android) | ✅ Working | Requires FQDN mode with Let's Encrypt |
| TAKAware (iOS) | ✅ Working | Works in both IP and FQDN mode |

## Security

- Password required before any access (set during `./start.sh`)
- HTTPS from the start (self-signed or Let's Encrypt)
- Session-based authentication
- All config files are 600 permissions
- Authentik bootstrap credentials auto-generated per deployment

## Design notes

- **[References](docs/REFERENCES.md)** — Canonical links (e.g. [TAK Server API](https://docs.tak.gov/api/takserver)) for development and integration.
- **[Guard Dog](docs/GUARDDOG.md)** — How Guard Dog works: monitors, 15‑minute boot delay and cooldowns, TAK Server soft start (after PostgreSQL and network), 4GB swap on deploy for memory stability, and restart-loop protection. Apply Docker container log limits from the Guard Dog page without redeploying a module.
- **[MediaMTX access driven by TAK Portal / LDAP](docs/MEDIAMTX-TAKPORTAL-ACCESS.md)** — How stream.fqdn admin vs viewer logic can be driven from TAK Portal (one place to manage users, no separate MediaMTX or Authentik user management). **Do not configure the email/SMTP portion of MediaMTX** — request access and approval notifications are handled by TAK Portal’s open request-access page and Email Relay.

---

## Changelog

### v0.1.9-alpha — 2026-03-04

**Guard Dog**
- Guard Dog appears in the sidebar **directly under Console** when installed (high-priority placement).
- **Apply Docker log limits** button on the Guard Dog page — set 50 MB × 3 files per container without redeploying Authentik, Node-RED, or another Docker module. Reduces risk of a single container log filling the disk (e.g. Node-RED).
- **Collapsible sections** on the Guard Dog page: Notifications, Database maintenance (CoT), and Activity log are now collapsible (click header to expand/collapse), matching the TAK Server and Help page style.
- **4GB swap on deploy** — When Guard Dog is deployed (or auto-deployed with TAK Server), the console ensures a 4GB swap file at `/swapfile` exists and is enabled. Matches the reference TAK Server Hardening script for memory stability under load.

**Connect LDAP / CoreConfig**
- When writing CoreConfig (full replace or password resync), the console ensures `adminGroup="ROLE_ADMIN"` is present in the LDAP block (adds if missing, verifies after write). Prevents wrong admin console access and "no channels" issues.

**CloudTAK**
- Step 6 waits for the CloudTAK API (`/api/connections` returns 200/401/403) before declaring backend ready, not just port 5000 — avoids 502 when Caddy proxies before the backend is up. Step 4 build output streamed; Step 5 timeout 600s.

**MediaMTX**
- Web editor systemd unit is created and enabled only when `mediamtx_config_editor.py` is present (clone or local fallback). If the editor file is missing, MediaMTX streaming still works; no restart loop. Clone uses default branch of `takwerx/mediamtx-installer`; LDAP overlay applied from repo.

**Unattended upgrades**
- Spinner on the toggle so "Disabling…" is visible while the request runs.

**Docs**
- [GUARDDOG.md](docs/GUARDDOG.md) documents the 4GB swap step and Docker log limits. [COMMANDS.md](docs/COMMANDS.md) has pull-then-restart (two steps), server impact and memory (`free -h`, `docker stats`, `top`), disk-full recovery, CloudTAK 502/backend readiness, and TAK client "no channels" / new-groups sync delay.

---

### v0.1.8-alpha — 2026-03-02

**LDAP QR Registration Fix**
LDAP application was restricted to authentik Admins, blocking QR code enrollment for non-admin users. LDAP is now open to all authenticated users. Connect LDAP / Resync LDAP applies this fix automatically.

**Fresh Deploy Flow**
8446 webadmin login and QR registration now work on initial deployment without manual Sync webadmin or Resync LDAP. LDAP outpost restart runs at end of TAK Server deploy and during Connect LDAP.

**Authentik Deploy**
Caddy reload timeout (30s) prevents indefinite hang. Progress message "Updating Caddy config..." before slow steps.

**Recommended deployment order:** Caddy → Authentik → Email Relay → TAK Server → Connect LDAP → TAK Portal → Node-RED / CloudTAK / MediaMTX

---

### v0.1.7-alpha — 2026-02-24

**Node-RED Authentik Integration**
Node-RED is now protected behind Authentik forward auth at `nodered.{fqdn}`. Requires Authentik login — same flow as TAK Portal.

**Bug Fix: Node-RED proxy provider was never created**
The provider creation payload used `authentication_flow` instead of `authorization_flow` (typo). Every POST returned 400 validation error, not "duplicate" — so the provider was never created. Also added the missing `invalidation_flow` field.

**Bug Fix: Orphaned Node-RED application**
Previous failed deploys created the application with no provider linked. The deploy now PATCHes the existing application to link the provider if it already exists.

**Bug Fix: Update mechanism didn't restart the service**
Clicking "Update Now" ran `git pull` but never restarted `takwerx-console`. Users saw "Updated!" but the old code kept running. The update now triggers a delayed `systemctl restart` after responding.

---

### v0.1.6 — 2026-02-22

**Rebranding:** Project renamed from `takwerx-console` to `tak-infra`. The console interface is now a component within the broader TAK-infra platform.

**Bug Fix: Console not loading after fresh deploy**
The auto-generated Caddyfile was missing the `tls` directive in the console reverse proxy transport block. Since the Flask app runs on HTTPS, Caddy was unable to forward requests to it, causing browsers to spin indefinitely. The TAK Server block already had the correct configuration — the console block now matches.

- `app.py`: Added `tls` to console Caddy transport block

---

### v0.1.5-alpha — 2026-02-21

**LDAP Authentication Fixed**
Authentik blueprint was setting `authentication_flow` instead of `authorization_flow` on the LDAP provider. This was the root cause of "Flow does not apply to current user" errors on every deploy since LDAP was introduced.

**Duplicate LDAP Provider Removed**
A second LDAP provider was being created via API after the blueprint, pointing to the wrong authentication flow. The API block has been removed. The deploy now waits for the blueprint worker to create the correct provider and injects its token directly.

**Token Injection Retry Loop**
LDAP outpost token fetch now retries indefinitely at 5-second intervals instead of timing out. No more manual token injection required after deploy.

**Caddy Reverse Proxy Redirect Fix**
TAK Server behind a reverse proxy was sending `Location: 127.0.0.1:8446` redirects back to the browser after login. Caddy now rewrites these headers to the correct FQDN automatically.

**TAK Portal Forward Auth**
Forward auth and invalidation flow lookups now retry indefinitely. TAK Portal deploy waits 2 minutes after completion for Authentik's embedded outpost to fully sync. Public paths bypass forward auth to support self-service enrollment.

**UX Improvements**
Deploy logs for Authentik and TAK Portal persist after completion. Completion screens show direct launch buttons for each service.

---

### v0.1.4-alpha — 2026-02-18

**GitHub Update Checker**
Switched from Releases API to Tags API — the previous implementation hit `/releases/latest` which returns 404 unless a Release is manually created on GitHub. Now uses `/tags` with semver sorting and 1-hour cache.

**Deploy State Reset**
TAK Server, Authentik, and TAK Portal pages now clear the `deploy_done` flag when services are running. Previously, refreshing after a deploy would keep showing the log instead of the running state.

**CoreConfig LDAP Auth**
`default="ldap"` preserved in the auth block — required for TAK Portal QR code enrollment.

---

### v0.1.3-alpha — 2026-02-18

**CoreConfig LDAP Auth**
`default="ldap"` preserved and File auth listed before LDAP in the auth block.

**Deploy State Reset**
All three module pages (TAK Server, Authentik, TAK Portal) now reset deploy state correctly on refresh.

---

### v0.1.2-alpha — 2026-02-17

**CoreConfig Auth Default Fix**
Changed `default` from `ldap` to `file` to fix `webadmin` access on port 8446. Password auth uses flat file, LDAP users still authenticate via the LDAP block, x509 cert auth still routes groups through LDAP.

**TAK Portal Container Log Cleanup**
Filtered `npm error`, `SIGTERM`, and `command failed` messages from container log display — these were cosmetic restart noise with no functional impact.

**Console Cross-Navigation**
Added links between Authentik, TAK Portal, and TAK Server pages.

---

### v0.1.1-alpha — 2026-02-17

**Authentik Module — Automated Deploy**
Full 10-step automated deployment: bootstrap credentials, LDAP blueprint, Docker Compose patching, API-driven token retrieval, CoreConfig.xml auto-patch, TAK Server restart. Smart API polling handles the full 503 → 403 → 200 startup progression.

**TAK Portal Module — Automated Deploy**
6-step automated deployment: repository clone, container build, TAK Server certificate copy, settings.json auto-configuration.

**Console UI**
Cross-service navigation between all module pages. Real-time step-by-step deploy logging.

---

### v0.1.0-alpha — 2026-02-16

Initial release.

- Services dashboard with live TAK Server process monitoring (Messaging, API, Config, Plugin Manager, Retention)
- Live server log streaming with color-coded ERROR/WARN highlighting
- Certificates page with file browser and direct download
- Deployment improvements: countdown timers, unattended-upgrades detection, cancel button, log reconnection
- Upload management: duplicate detection, cancellation, remove button
- Ubuntu 22.04 support

---

## License

MIT

## Credits

Built by [TAKWERX](https://github.com/takwerx) for emergency services.
