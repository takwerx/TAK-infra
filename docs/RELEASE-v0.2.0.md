# infra-TAK v0.2.0-alpha

Release Date: 2026-03-12

---

## Highlights

- **Two-server TAK Server** — Split core and database across two hosts
- **Remote deployments** — Deploy Authentik, CloudTAK, MediaMTX, and Node-RED to remote servers via SSH
- **Gunicorn production server** — Auto-upgrades from Flask dev server transparently
- **Staggered Docker boot** — Dependency-ordered container startup on reboot
- **Light / high-contrast mode** — Outdoor-readable UI with one toggle
- **Unified controls UI** — Consistent layout across all module pages
- **CloudTAK and Authentik update awareness** — Pinned to stable releases with update indicators

---

## Two-server TAK Server (split core and database)

Deploy TAK Server across two hosts for scale or separation of concerns:

- **Server One** — PostgreSQL database. The console SSHs to Server One and handles everything: installs PostgreSQL, opens remote access, configures `pg_hba.conf` for Server Two's IP, captures the DB password, and opens the firewall.
- **Server Two** — TAK Server core (`takserver-core` package). Connects to the remote PostgreSQL on Server One.

Additional features:
- **SSH key management UI** — Generate an ed25519 key or use an existing one. Button to copy the public key for pasting into Server One's `authorized_keys`.
- **Per-server health monitoring** — Separate status indicators for core and database. Dedicated **Restart DB** and **Restart Both** buttons.
- **Guard Dog two-server awareness** — Monitors the remote database host (PostgreSQL connectivity, disk, port).
- **Version detection** — Reads version from `takserver-core` on Server Two and `takserver-database` on Server One.
- **DB password sync** — "Sync DB password from Server One" button when the password drifts.

---

## Remote deployments

Authentik, CloudTAK, MediaMTX, and Node-RED each support a **remote deployment target**:

1. On the module page, select "On another server via SSH" in the Deployment Target section.
2. Enter the remote host IP, SSH user, and port.
3. Click Deploy — the console SSHs to the remote and runs Docker/scripts there.

Once deployed:
- Module status (running/stopped) is checked via SSH and shown in the sidebar and console cards.
- Remote health metrics (CPU, RAM, disk) are displayed on module detail pages.
- Controls (restart, stop, update config, remove) operate against the remote host.
- The Deployment Target section disappears after deployment.

**Firewall notes:** The console must reach the remote on SSH (port 22). For Authentik remote, the console also needs access to port 9090 (API) for LDAP token injection. See README for full firewall guidance.

---

## Gunicorn production server (auto-upgrade)

The console now runs on **gunicorn** (1 worker, 4 threads, 300s timeout) instead of the Flask development server.

**Automatic upgrade for v0.1.x users:** When the old systemd service runs `python3 app.py`, the boot block in `app.py`:
1. Installs gunicorn into the virtualenv
2. Rewrites the systemd `ExecStart` line to use gunicorn
3. exec's into gunicorn

No manual steps. After the first restart post-pull, the service file is updated and gunicorn runs directly on subsequent boots.

---

## Staggered Docker boot

A systemd `docker-stagger.service` ensures containers start in dependency order on server reboot:

```
Authentik DB (postgresql)  →  5s wait
Authentik (server + worker)  →  10s wait
Authentik LDAP outpost  →  5s wait
TAK Portal  →  5s wait
CloudTAK DB (postgis)  →  5s wait
CloudTAK (api, tiles, events, store, media)
```

This prevents the cascade of OOM kills and 502s that occur when all containers compete for memory on a small VPS during simultaneous startup.

The service is created/updated automatically on every deploy or uninstall, so it always reflects the currently installed containers. If no Docker containers are present, the service is removed.

---

## Light / high-contrast mode

A **Light Mode** toggle in the sidebar switches the entire UI to a high-contrast light theme designed for outdoor/sunlight readability:

- White card backgrounds, light gray surfaces
- Near-black text for maximum contrast
- Darker, more saturated accent colors
- Visible medium-gray borders
- All hardcoded dark backgrounds (log boxes, form inputs, code displays) are overridden

Preference is saved to `localStorage` and persists across sessions and page navigations. The toggle icon switches between sun (light mode) and moon (dark mode).

---

## Unified controls UI

All module pages now follow the same layout pattern established by the TAK Server page:

- **Controls section** immediately below the status banner with consistent `control-btn` styling (Restart, Update config, Update, Stop, Remove).
- **Deployment Target** section only appears when a module is not yet deployed. Once deployed, it disappears — no more unused deployment forms cluttering the page.
- **Full-width layout** — All pages are flush with the sidebar (no centering or max-width constraints).

Affected pages: TAK Server, Authentik, TAK Portal, CloudTAK, Node-RED, MediaMTX, Email Relay, Caddy.

---

## CloudTAK — stable release pinning and update awareness

- **Pinned to stable releases:** CloudTAK deployments now check out the latest stable GitHub release tag (e.g. `v12.94.0`) from `opentak-community/cloudtak` instead of building from HEAD. This prevents deploying unreleased/broken code.
- **Update awareness:** The console fetches the latest release tag (1-hour cache) and compares it to the installed version. When an update is available:
  - Console dashboard card shows "update available" indicator.
  - CloudTAK detail page shows the available version in the header.
  - **Update** button gets a glowing cyan border and dot indicator.
- **One-click update:** Pulls the new release tag, rebuilds Docker images, and restarts containers. Config and data are preserved.

---

## Authentik — update awareness and auto-fetch

- **Latest stable release:** Deploy automatically fetches the latest stable Authentik version from GitHub releases (e.g. `2026.2.1`) and pins the Docker Compose image tags.
- **Update awareness:** Console card and Authentik detail page display update availability with a glowing **Update** button when a newer version exists.

---

## Authentik — reconfigure improvements

**Remote reconfigure:**
- Runs entirely against the remote host: SSHs to ensure containers are up, reads the API token from remote `.env`, runs all API steps against `http://<remote>:9090`.
- No local `~/authentik` directory required on the console host.

**Local reconfigure:**
- Creates/repairs all four Authentik applications: infra-TAK, MediaMTX, Node-RED, TAK Portal.
- Ensures all providers are attached to the embedded outpost.
- **Outpost safety:** A single helper (`_outpost_add_providers_safe`) guarantees that adding a provider never removes existing ones from the outpost.
- **Install dir fallback:** Tries `~/authentik`, `/opt/authentik`, and the Docker Compose project dir from the container label.

**Install check:** Reconfigure is allowed when: remote + deployed, compose file exists, authentik-server container running, or Authentik HTTP is reachable.

**Deploy log:** Reconfigure now streams a live log instead of redirecting immediately.

**Show password eyeball:** Reconfigure enables the "show password" (eyeball) toggle on all Authentik password stages, so users can reveal their password on the login page. Applied automatically for existing deployments when you run "Update config & reconnect".

---

## Email Relay — Authentik SMTP auto-configuration

Deploying Email Relay now automatically:
1. Pushes SMTP settings (host, port, credentials) into Authentik's `.env`.
2. Restarts Authentik containers to pick up the new config.
3. Sets up the password recovery flow in Authentik.

Result: "Forgot password" works in Authentik out of the box after Email Relay deploy.

---

## Console UI and branding

- **Version in sidebar:** The current version (e.g. `v0.2.0-alpha`) is displayed in the sidebar logo area below "built by TAKWERX".
- **Orbitron font:** The "infra-TAK" text in the sidebar uses the same Orbitron typeface as the login page.
- **Module versions on dashboard:** TAK Server and CloudTAK versions are shown on their console cards and detail page headers.
- **Update indicators:** Dashboard cards show update availability for CloudTAK and Authentik.

---

## LDAP credential auto-resync

Detects when Authentik LDAP bind credentials have drifted from what's in CoreConfig.xml (e.g. after an Authentik redeploy or password change). Auto-resyncs the credentials to prevent silent LDAP group sync failures that cause "no channels" or missing admin access.

---

## Upgrading from v0.1.9

```bash
cd $(grep -oP 'WorkingDirectory=\K.*' /etc/systemd/system/takwerx-console.service)
git pull origin dev
sudo systemctl restart takwerx-console
```

The gunicorn auto-upgrade runs on first restart. No other manual steps required. All existing module deployments, config, and passwords are preserved.

---

## Status

All modules production-ready. Full stack verified on fresh deploy and upgrade from v0.1.9.
