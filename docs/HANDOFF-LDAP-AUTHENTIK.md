# infra-TAK Technical Handoff Document

---

## Prompt for a new chat (copy and paste this)

```
Read docs/HANDOFF-LDAP-AUTHENTIK.md section "0. Current Session State" and the v0.2.0 bullets. We're on v0.2.0.

Summary: Authentik "Update config & reconnect" works for both local and remote deploy; remote reconfigure uses SSH + remote API (no local ~/authentik). We only create Authentik applications for modules that are actually deployed (Node-RED, MediaMTX, TAK Portal); infra-TAK always. Helper _is_module_deployed(settings, key) gates app creation and _repair_embedded_outpost_all_apps. Outpost updates go through _outpost_add_providers_safe so we never remove existing apps. Access policies: admins see infra-TAK + Node-RED (when deployed); all users see MediaMTX + TAK Portal (when deployed).

Node-RED supports remote deploy: Node-RED page has a "Deployment Target" card (local vs remote SSH). When target is remote, run_nodered_deploy branches to _run_nodered_deploy_remote (mkdir ~/node-red, copy settings.js + docker-compose.yml, docker compose up -d, Caddy, optional Authentik app). Caddy uses _get_nodered_upstream(settings); deploy POST sends config; generic routes: /api/nodered/deployment-config (save), /api/nodered/remote/ensure-ssh-key, install-ssh-key, test.

Use docs/HANDOFF-LDAP-AUTHENTIK.md as the single source of truth for what's done and what to do next.
```

---

## 0. Current Session State (Last Updated: 2026-03-12) — v0.2.0-alpha

**This section is the single source of truth.** Update it when server state changes. This doc is a living handoff between machines -- only describe what is true right now.

**Version:** v0.2.0-alpha (not v0.1.10). Main was updated with selective dev->main release commit `50895d2` and release docs.

### v0.2.0-alpha — 2026-03-12 Session Updates (Release + UI + docs)

**Released / merged updates:**
- **Release and docs:** `README.md` changelog refreshed for v0.2.0-alpha; `docs/RELEASE-v0.2.0.md` added; `docs/COMMANDS.md` selective merge block updated for v0.2.0-alpha paths/tag examples.
- **Version bump:** `VERSION` in `app.py` set to `0.2.0-alpha`; sidebar now shows the running version.
- **Sidebar / branding UI:** Added light mode toggle in sidebar; moved TAKWERX logo to top block (always visible), tightened spacing for 13" screens, and matched `infra-TAK` branding font to login style.
- **Console update-check fix:** `/api/update/check` now compares semantic version tuples with `>` (newer-only) instead of `!=` so v0.2.0-alpha no longer incorrectly reports an update when latest tag is v0.1.9-alpha.
- **CloudTAK UX fix:** Access card now renders only when `cloudtak.running` is true (not during deploy / stopped), preventing premature user click-through.
- **TAK Portal branding preservation note:** Release docs now explicitly state that custom branding fields (e.g. `BRAND_LOGO_URL`) are preserved across **Update**, **Update config**, and reconfigure paths.

### Current operational note — CloudTAK channels/update prompt behavior

- Field observation on two deployments: CloudTAK repeatedly showed channel/update prompts ("channels shit again"). A temporary improvement was seen after **Authentik Update config & reconnect**, but behavior returned.
- Reproduced with both admin and regular users; anecdotal report from a non-infra-TAK TAK Portal environment suggests this is likely upstream CloudTAK behavior, not infra-TAK specific.
- Treat as **known upstream issue** for now; keep deployment pinned to stable release and document reproducible steps for CloudTAK maintainers.

### Today's priority (Mac Studio handoff) — MediaMTX token + playback tuning

**Primary focus:** MediaMTX end-user playback stability and token handling simplification.

1. **Token path simplification**
   - Investigate moving token handling into the upstream/regular MediaMTX path we pull from so infra-TAK skin has less token-specific logic.
   - Goal: reduce custom skin surface area and remove one failure domain in overlay logic.

2. **Playback freeze feedback from aircraft live stream (RTF from desktop)**
   - Feedback indicates Chrome native HLS player stalls about every ~35s due to native buffer behavior.
   - Source artifact reviewed: `/Users/atjohansson/Desktop/video firis feedback from claude..rtf`.
   - Suggested direction from feedback file: serve a custom **HLS.js player** page (not native Chrome player) and tune:
     - `liveSyncDurationCount` near segment cadence
     - `liveMaxLatencyDurationCount` aligned with playlist depth
     - bounded buffer settings (`maxBufferLength`, `maxMaxBufferLength`)
   - Working assumption for next session: player-side buffering policy is likely a major factor in aircraft stream freezing, independent of Authentik token flow.

3. **Execution plan for next session**
   - Validate whether freezes reproduce with HLS.js page under same stream/bitrate/network.
   - Compare behavior between tokenized URL path vs authenticated header path.
   - If HLS.js resolves periodic stall, make HLS.js viewer the default for infra-TAK MediaMTX skin and keep Safari fallback to native HLS.
   - If token logic still causes errors, decide whether to upstream token handling into base MediaMTX integration code and remove duplicate skin code.

### v0.2.0 — Authentik reconfigure, four apps, remote reconfigure, install check

**Summary of code changes (2026-03-11):**

- **Outpost safety:** All “add provider to embedded outpost” paths now use `_outpost_add_providers_safe(ak_url, ak_headers, provider_pks_to_add, plog)`. It GETs the full outpost, normalizes `providers` to PKs (handles both `pk`/`id` and int), appends missing PKs, and PATCHes only if the new list is not shorter than the original. This prevents any code path from removing infra-TAK, MediaMTX, or Node-RED when adding TAK Portal (or vice versa).
- **Only deployed modules get Authentik apps (main-branch behavior):** We now create/ensure an Authentik application only when that module is actually deployed. Helper `_is_module_deployed(settings, module_key)` returns True for: `infratak` (always), `takportal` (~/TAK-Portal/docker-compose.yml), `nodered` (~/node-red/docker-compose.yml or ~/node-red / /opt/nodered), `mediamtx` (remote deployed or local /usr/local/bin/mediamtx + mediamtx.yml). Reconfigure (local and remote) and full deploy only create/repair the Node-RED app when Node-RED is deployed; only sync/create TAK Portal app when TAK Portal is deployed; `_ensure_authentik_console_app` only adds MediaMTX (stream) to its entries when MediaMTX is deployed. `_repair_embedded_outpost_all_apps` only adds provider PKs for applications whose module is deployed (by slug: infratak always, stream→mediamtx, node-red→nodered, tak-portal→takportal). Full deploy Step 12c–12e (TAK Portal proxy + app + outpost) runs only when `_is_module_deployed(settings, 'takportal')`; the “No authorization flow found” message is shown only when TAK Portal is deployed but flow is missing. Result: at tak.fqdn, **admins** see infra-TAK, MediaMTX (if deployed), Node-RED (if deployed), TAK Portal (if deployed); **regular users** see MediaMTX and TAK Portal when those modules are deployed (access policies unchanged: admin_only_slugs = infratak, console, node-red).
- **Reconfigure (local):** When “Update config & reconnect” runs for **local** Authentik, the reconfigure branch: syncs TAK Portal provider URL only if TAK Portal deployed; calls `_ensure_authentik_nodered_app` only if Node-RED deployed; calls `_ensure_authentik_console_app` (infra-TAK + MediaMTX only if MediaMTX deployed); runs `_repair_embedded_outpost_all_apps` (adds only deployed apps’ providers to outpost).
- **Remote reconfigure:** When deployment target is **remote** (`authentik_deployment.target_mode == 'remote'`), reconfigure calls `_run_authentik_reconfigure_remote`: ensures containers up on remote via SSH, gets token from remote .env via SSH, then runs API steps against `http://<remote_host>:9090`: cookie domain; TAK Portal sync and Node-RED app only when those modules are deployed (`_is_module_deployed`); console app (infra-TAK + MediaMTX if deployed); repair outpost (deployed apps only); app access policies; show password. No local `~/authentik` or `_find_authentik_install_dir()` is used for remote.
- **Install check for reconfigure:** Replaced the single `~/authentik/docker-compose.yml` check with `_authentik_installed_for_reconfigure()`: returns True if (1) remote and deployed, or (2) that file exists, or (3) `docker ps` shows an authentik-server container, or (4) Authentik HTTP is reachable at the configured API URL. Avoids “Authentik not installed” when the stack is running but the console runs as a different user or has no local compose file (e.g. remote deploy).
- **Local install dir fallback:** For **local** reconfigure only, if `~/authentik` has no .env/compose, we call `_find_authentik_install_dir()` which tries `~/authentik`, `/opt/authentik`, then the Docker Compose project dir from `docker inspect` (label `com.docker.compose.project.working_dir`) so reconfigure can still run when the install lives elsewhere.
- **Deploy log for reconfigure:** “Update config & reconnect” now shows the deploy log: reconfigure no longer redirects immediately; it reveals the log card, streams “Starting update config & reconnect...”, and polls `authentik_deploy_log`. The log card exists in both “installed and running” and “installed but stopped” views.
- **Node-RED remote deploy (v0.2.0):** Node-RED supports deployment to a remote host (same pattern as Authentik). On the Node-RED page, a **Deployment Target** collapsible card lets you choose "On this infra-TAK host" or "On a remote host (SSH)" with host, SSH port, username, SSH key path, and buttons: Generate SSH key, Install SSH key, Test SSH, Save target settings. Deploy POST sends current config; backend `run_nodered_deploy()` branches to `_run_nodered_deploy_remote(settings, deploy_cfg, plog)` when `target_mode == 'remote'`. Remote flow: mkdir ~/node-red, copy settings.js and docker-compose.yml via `_module_copy`, run `docker compose up -d` via `_module_run`, set deployed, save settings, update Caddy (`_get_nodered_upstream` returns `remote_host:1880`), optionally ensure Authentik Node-RED app. Only deployed modules get Authentik apps; Node-RED "installed" for detect_modules when remote + deployed + host set; Caddy uses `_get_nodered_upstream(settings)` for the Node-RED reverse proxy.
- **Docs:** `docs/MAIN-VS-DEV-AUTHENTIK.md` summarizes main vs dev (reconfigure behavior, install check, deploy log). `docs/RELEASE-v0.2.0.md` and README changelog updated for v0.2.0.

### Current struggles — Remote Authentik deployment and applications

- **Remote Authentik:** When Authentik is deployed to a **remote** host (another machine), the console does not have a local `~/authentik` (or `/opt/authentik`). Reconfigure was incorrectly running the **local** path and failing with “Authentik not fully installed” (config dir not found). This is fixed in v0.2.0 by routing remote reconfigure to `_run_authentik_reconfigure_remote`, which only uses SSH + remote API. Remaining risks: (1) SSH or network failures to the remote host during reconfigure; (2) remote .env not having `AUTHENTIK_TOKEN` or `AUTHENTIK_BOOTSTRAP_TOKEN` (reconfigure will fail with a clear log message); (3) firewall blocking console → remote:9090 (Authentik API) so API steps fail even if SSH works.
- **Getting applications to load (four apps on outpost):** On some setups only TAK Portal appeared in the app launcher; infra-TAK, MediaMTX, and Node-RED were missing. Cause: outpost was sometimes PATCHed with a shorter provider list (e.g. only TAK Portal). Fix: all outpost updates go through `_outpost_add_providers_safe` (never shorten), and reconfigure (local and remote) explicitly creates/repairs the four apps and runs `_repair_embedded_outpost_all_apps`. If applications still don’t load after reconfigure: (1) confirm in Authentik Admin → Applications that infratak, stream, node-red, tak-portal exist; (2) confirm in Outposts → embedded outpost that all four providers are attached; (3) run “Update config & reconnect” again and watch the log for API errors (e.g. 403, timeout to remote).
- **Operational note:** For **remote** Authentik, ensure the console host can reach the remote host on port 9090 (Authentik API) and that SSH is configured (Deployment Target → remote host, SSH key). Reconfigure reads the token from the remote .env via SSH; all other steps use HTTP to `http://<remote_host>:9090`.

### Two-Server Split Mode (TAK Server) — In Progress

**Architecture:** Server One = PostgreSQL + TAK database .deb. Server Two = TAK Server core .deb only. Console (infra-TAK) runs on Server Two. JDBC in CoreConfig on Server Two must point at Server One with correct password.

**Implemented and working:**
- **Deploy flow:** Settings → TAK deployment: mode = Two server, Server One host + SSH key (or password), Server Two = local. Buttons: 1. Save Config → 2. Setup SSH key → 3. Copy key to Server One → 4. Deploy Server One (DB) → 5. Deploy Server Two (Core) → then Certificate Information + Deploy TAK Server.
- **Server One setup:** SCP takserver-database .deb, install, configure PostgreSQL (`listen_addresses = '*'`, `pg_hba.conf` host rule for Core IP with `scram-sha-256`), UFW allow 5432 from Core, capture DB password from `/opt/tak/CoreConfig.example.xml` or `CoreConfig.xml` (grep + sed fallback if no `grep -oP`).
- **Server Two setup:** Install takserver-core .deb, patch CoreConfig.xml JDBC URL and password to Server One, restart takserver.
- **Guard Dog two-server:** Remote DB monitor (TCP + SSH to Server One, optional health agent on S1:8080). Services panel shows "PostgreSQL (S1_IP)" with TCP probe; no local PG/CoT monitors under TAK Server when two-server.
- **TAK Server update (two-server):** Upload both takserver-core and takserver-database .deb; upgrade core locally, restore JDBC in CoreConfig, SCP DB .deb to Server One, install via SSH, start takserver.
- **Restart controls:** Restart / Restart DB (Server One) / Restart Both / **Sync DB password** (see below) / Update config / Stop / Remove.
- **VACUUM and CoT DB size:** Run remotely on Server One via SSH when two-server.
- **Sync DB password:** Button "🔑 Sync DB password" (two-server only). **No SSH to Server One.** Uses password from: (1) the "DB password (from Server One)" field on the page (paste from Server One), or (2) saved password in Settings (from deploy). Patches CoreConfig.xml on Server Two and restarts takserver. API: `POST /api/takserver/two-server/sync-db-password` with optional `{"password": "..."}`.

**Known issue — 8443 / 8446 failing (empty DB password):**
- **Symptom:** 8443 (cert auth) shows "Exception performing TAK Server authentication" with root cause `PSQLException: The server requested SCRAM-based authentication, but the password is an empty string.` 8446 may show "bad password" or similar. TAK Server startup can be slow; first load may time out.
- **Cause:** CoreConfig.xml on Server Two has empty `password=""` in the `<connection>` element for the JDBC URL to Server One. Either the password was never captured during deploy or the patch didn’t run (e.g. deploy order, or grep -oP not available on Server One).
- **Fix (UI):** Either (1) In the **deploy wizard** (TAK Server → deployment → Split Server): set **DB password (from Server One)** and click **1. Save Config** — then run step 5 / Deploy TAK Server or use **Sync DB password**; or (2) On the TAK Server page, paste the password in the **DB password (from Server One)** field and click **Sync DB password**. Wait for restart (~1 min) then retry 8443/8446.
- **Fix (manual):** On Server One run `sudo sed -n 's/.*password="\([^"]*\)".*/\1/p' /opt/tak/CoreConfig.example.xml | head -1` to get password. On Server Two run `sudo sed -i 's/password="[^"]*"/password="PASTE_PASSWORD_HERE"/' /opt/tak/CoreConfig.xml` then `sudo systemctl restart takserver`.
- **Code:** Sync DB password uses request body or settings only (no SSH). Deploy steps and "Deploy TAK Server" may still use `_fetch_db_password_from_server_one(s1_cfg)` when SSH is available; Sync DB password is the no-SSH repair.

**Other two-server notes:**
- **pg_hba.conf:** Must have a newline before the new `host ... scram-sha-256` line; otherwise it can concatenate with previous line (e.g. `md5host`). Code does `printf "\\nhost ..."` and a repair `sed` for `md5host` → `md5\nhost`.
- **PostgreSQL start:** Use `pg_ctlcluster 15 main start` (or restart); `systemctl start postgresql` on Debian/Ubuntu often does nothing (ExecStart=/bin/true).
- **Preflight:** "Run Preflight" was removed; DB port check failed until after Server One was configured.

**Where to continue:** If 8443/8446 still fail after Sync DB password, ensure the password in the field (or in Settings) matches the martiuser password in `/opt/tak/CoreConfig.example.xml` (or CoreConfig.xml) on Server One. Optional: "Show DB password" (from settings) for debugging.

**Other recent UI/two-server tweaks (2026-03-07):** TAK Server status area: control buttons (Restart, Restart DB, Sync DB password, etc.) moved to a second row below the status/CA text so the cert expiry (Root CA / Intermediate CA) doesn’t wrap. Cert banner: Intermediate CA shown on its own line below Root CA. Guard Dog: per-monitor green/red status dots (Port 8089, Process, Network, OOM, Disk, Cert, etc.) via `/api/guarddog/monitor-health`; cache-bust on guarddog.js with version query.

### Post-v0.2.0 Backlog — Multi-OS Framework (Plan, not implemented)

**Goal:** Keep Ubuntu behavior unchanged while adding safe cross-OS support (Debian family + Rocky/RHEL family) for local and future remote deploy targets.

**Strategy (low-risk):**
- **Adapter-first, no big-bang rewrite:** Introduce backend wrappers for package install, service control, firewall opens, and package-lock waits. Route existing code through wrappers gradually.
- **Golden baseline:** Ubuntu flows are reference behavior; preserve existing commands/results while wrappers are introduced.
- **Family/capability detection:** Detect `family` (`debian`/`rhel`), `pkg_mgr` (`apt`/`dnf`), `firewall_mgr` (`ufw`/`firewalld`), and service aliases (e.g. PostgreSQL unit names).
- **Incremental migration order:** Caddy + Guard Dog firewall bits first, then TAK deploy/update paths, then remaining modules.
- **Support tiers in UI/docs:** Tested (Ubuntu 22/24, Debian 12, Rocky 9), compatible/untested (RHEL 9/Alma), experimental (others) with clear preflight warnings.

**Inputs captured for Rocky 9 mapping (from user scripts):**
- `Rocky_9_Caddy_setup.sh`
- `Rocky_9_TAK_Server_install.sh`
- `Rocky_9_TAK_Server_Hardening.sh`

**Key Rocky/RHEL behaviors to map into adapters:**
- `dnf` + CRB/EPEL/PGDG repo handling
- `firewall-cmd` (firewalld) port operations
- PostgreSQL service naming differences (`postgresql` vs `postgresql-15`)
- SELinux policy/apply step as best-effort path
- Existing Guard Dog timers/health endpoint patterns (already mostly OS-neutral)

**Current quick wins already done:**
- `start.sh` now supports Debian 12 (bookworm) with `apt` (no longer `PKG_MGR=unknown`).
- Guard Dog/Uptime health is now exposed via Caddy on `https://<infratak-host>/health` so Caddy regenerations (e.g., Node-RED deploy) keep the route.

### v0.1.9 (2026-03-06) — Domain sync hardening, Caddy alias, UX/docs updates

**Authentik domain sync on Update (important):**
- Reconfigure path (`Authentik -> Update`) now syncs Authentik domain from Caddy/Domains into:
  - `~/authentik/.env` (`AUTHENTIK_HOST`)
  - `~/authentik/docker-compose.yml` LDAP `AUTHENTIK_HOST` + `extra_hosts`
  - Authentik brand domain
  - embedded outpost `authentik_host`
- Added provider sync helper to update proxy providers that still point at `authentik.<fqdn>` to the current Authentik base URL (default `tak.<fqdn>`). This fixes redirect loops/SSL mismatch after domain changes.

**Caddy Authentik alias safety net:**
- When Authentik default host is `tak.<fqdn>`, generated Caddyfile now also serves `authentik.<fqdn>` to the same backend (`127.0.0.1:9090`) so stale redirects to `authentik.*` still terminate TLS and load.

**TAK Server link UX fix:**
- 8446 WebGUI links in UI changed from `https://takserver.<fqdn>:8446` to proxied host URL `https://takserver.<fqdn>` (still reaches password WebGUI via Caddy reverse proxy). 8443 link remains explicit `:8443`.

**COMMANDS.md updates this session:**
- Added/expanded:
  - boot/recovery guidance ("After reboot", backdoor-first flow)
  - insecure cert troubleshooting
  - Authentik URL/domain-change full flow
  - brand CSRF API workaround
  - selective dev -> main release flow now explicitly pulls `dev` first
  - release tagging examples updated to `v0.1.9-alpha`

**README requirements update:**
- Clarified full-stack resource expectations:
  - real-world full module deploy can sit around ~26 GB used
  - recommend 50+ GB disk headroom
  - TAK Server minimums referenced (4 cores / 8 GB RAM / 40 GB disk), with guidance that full stack benefits from more.

**Operational note observed repeatedly:**
- CloudTAK can report "done" before frontend/API are comfortably warm on some hosts. Initial load may show transient 502/"Unexpected token '<'" until services settle; hard refresh often clears cached error.

### v0.1.9 (2026-03-04 / 2026-03-05) — Connect LDAP, CloudTAK, MediaMTX, COMMANDS

**Connect LDAP / CoreConfig:**
- When writing CoreConfig (full replace or password resync), the console ensures `adminGroup="ROLE_ADMIN"` is present in the LDAP block (adds if missing, verifies with grep after write, fails with a clear message if missing). Prevents "no channels" / wrong admin console access.

**CloudTAK:**
- Step 4: Build output streamed; 45 min timeout. Step 5: timeout 600s (10 min). Step 6: Waits for `http://localhost:5000/api/connections` to return 200/401/403 (not just port 5000) before declaring "CloudTAK API is responding (backend ready)" — avoids 502 when Caddy proxies before backend is ready.

**MediaMTX:**
- No longer uses `infratak` branch. Always clones **default branch** from `takwerx/mediamtx-installer`, then applies `mediamtx_ldap_overlay.py` from infra-TAK repo. Log: "LDAP/Authentik detected — will apply LDAP overlay after install".
- **Web editor service:** `mediamtx-webeditor.service` is created and enabled/started **only when** `/opt/mediamtx-webeditor/mediamtx_config_editor.py` exists. If clone fails and no local fallback, we skip creating the service (no restart loop). Pip deps and enable/start for webeditor are also gated on that file.

**TAK Server packages:**
- Deploy and upgrade use `<install_path>/uploads/` (e.g. `/root/infra-TAK/uploads/`). You can rsync or scp the .deb there before running deploy or upgrade.

**COMMANDS.md:**
- **Pull then restart (two steps):** Separate code blocks for `git fetch/checkout/pull` and `sudo systemctl restart takwerx-console`.
- **Server impact and memory:** Section with `free -h`, `docker stats --no-stream`, `top -o %MEM` (and %CPU), plus short note on what typically uses the most (TAK Server Java, PostgreSQL, Docker stack).
- Other: Disk full / container logs, CloudTAK 502 / backend readiness, TAK client "No channels found" and "New groups not synced yet" (60s refresh; client reconnect after 1–2 min).

**Unattended upgrades:**
- Spinner on the toggle so "Disabling…" is visible while the request runs.

### v0.1.9 (2026-03-03) — TAK Server PKI, Guard Dog, Client Certs, UI Overhaul

**Guard Dog — full deploy with 9 monitors:**
- TAK Server: Port 8089, Process, Network, PostgreSQL, CoT DB size, OOM, Disk, Certificate (Let's Encrypt / TAK Server cert), Root CA / Intermediate CA (escalating schedule: 90/75/60/45/30 days then daily until expiry).
- Additional service monitors (when installed): Authentik, MediaMTX, Node-RED, CloudTAK.
- Notifications via Email Relay (Brevo SMTP) and optional SMS (Twilio/Brevo).
- Guard Dog scripts in `scripts/guarddog/`, deployed as systemd timers. Health endpoint on port 8888.

**TAK Server page — new features:**
- **Update TAK Server:** Collapsible card with upload (.deb), progress bar, cancel button, success/failure indicators. Blocks update if file not uploaded.
- **Certificate expiry display:** Root CA and Intermediate CA expiry shown on TAK Server page (banner + Certificates section) and on the Console dashboard module card. Color-coded: green (>1yr), yellow (<=1yr), red (<=90 days). Format: `Xy Xmo Xd`.
- **Create Client Certificate:** Collapsible card. Enter client name, load groups from TAK Server (via Marti API), select groups with Read (OUT), Write (IN), or Both permissions. Downloads .p12 file. Uses `makeCert.sh` + `UserManager.jar certmod`.
- **Database Maintenance (CoT):** Collapsible card (was open section).
- **Certificates:** Collapsible card with Root CA and Intermediate CA expiry details.
- **Server Log:** Collapsible card for `takserver-messaging.log`.
- **Rotate Intermediate CA:** Collapsible card. Shows current Root/Intermediate CA names, expiry, time remaining. Input for new CA name (auto-suggested). Steps: restore root CA → create new intermediate → new server cert → regenerate admin/user certs → update truststore (old CA kept for transition) → update CoreConfig → update TAK Portal certs → restart TAK Server. "Revoke Old CA" section lists trusted CAs in truststore, allows removing old CA after transition period.
- **Rotate Root CA:** Collapsible card. Shows Root CA expiry. Hard cutover: removes old PKI, creates new Root CA, new Intermediate CA, new server cert, regenerates admin/user certs, updates truststore, CoreConfig, TAK Portal, restarts TAK Server. Double confirmation required. All clients must re-enroll via QR code after rotation.
- **Section order:** Access, Services, Update TAK Server, Database Maintenance, Certificates, Rotate Intermediate CA, Rotate Root CA, Create Client Certificate, Server Log.

**TAK Server page — JS extraction:**
- Entire inline `<script>` moved to `static/takserver.js` served via `/takserver.js` route. Fixed `SyntaxError: missing ) after argument list` caused by extra closing brace in `pollUpgradeLog`.

**Console dashboard — cert expiry on module card:**
- TAK Server card shows `Root Xy · Int Xy Xmo Xd` below the Running badge, color-coded. Removed hidden "Manage"/"Deploy" spans from console cards to eliminate ghost height.

**Help page — collapsible sections:**
- All 7 help sections converted to collapsible cards matching TAK Server style (uppercase monospace titles, chevron arrow on right).
- Left-aligned layout (removed centered max-width).
- Reordered: Deployment Order, Backdoor, Console Password, Reset Console Password, Server Hardening (SSH), Uninstall All, Docs.

**Guard Dog — Root CA / Intermediate CA monitor:**
- New systemd timer `takintcaguard.timer` (runs daily).
- Script `tak-intca-watch.sh` checks both Root CA and Intermediate CA expiry.
- Escalating notification schedule: first alert at 90 days, then 75, 60, 45, 30, then daily until expiry.
- Email includes the CA name, days remaining, and exact expiry date.

**API endpoints added:**
- `GET /api/takserver/cert-expiry` — Root CA and Intermediate CA days left + expiry date.
- `GET /api/takserver/groups` — Fetches TAK Server groups via Marti API (extracts PEM from admin.p12 with `-legacy` flag for OpenSSL 3.x compatibility).
- `POST /api/takserver/create-client-cert` — Creates client cert, assigns to groups with IN/OUT permissions.
- `GET /api/takserver/ca-info` — Current CA names, expiry, truststore contents, suggested new names.
- `POST /api/takserver/rotate-intca` — Intermediate CA rotation (background thread, streamed log).
- `GET /api/takserver/rotate-intca/status` — Poll rotation progress.
- `POST /api/takserver/revoke-old-ca` — Remove old CA from truststore.
- `POST /api/takserver/rotate-rootca` — Root CA rotation (background thread, hard cutover).
- `GET /api/takserver/rotate-rootca/status` — Poll root rotation progress.

**Docs added:**
- `docs/TAK_Server_OpenAPI_v0.json` — In-repo copy of TAK Server OpenAPI 3.1 spec.
- `docs/REFERENCES.md` — Added OpenAPI spec reference.

**Key fixes:**
- `curl` exit code 58 for TAK Server API: legacy PKCS12 (RC2-40-CBC) from `makeCert.sh` incompatible with OpenSSL 3.x. Fixed by extracting PEM with `openssl pkcs12 -legacy`.
- `makeCert.sh` permission denied: Fixed with `chmod +r cert-metadata.sh` + `sudo -u tak bash -c "cd ... && ./makeCert.sh ..."`.
- `keytool -list` showing "mykey" (PrivateKeyEntry) as revocable CA: Filtered to only include `trustedCertEntry` aliases.
- TAK Portal cert update during CA rotation: Re-encodes admin.p12 to tak-client.p12 with `-legacy` for Node.js compatibility, copies CA chain, restarts tak-portal container.

**Git workflow:** Same as v0.1.8. dev = full workspace. main = public-facing only. Selective checkout for merge.

### v0.1.8-alpha Release (2026-03-02 night)

**LDAP QR registration fix:** LDAP app was restricted to authentik Admins (in `admin_only_slugs`), blocking QR enrollment for non-admin users. **Fix:** Removed `ldap` from `admin_only_slugs`; added loop in `_ensure_app_access_policies` to remove "Allow authentik Admins" binding from LDAP app if present; Connect LDAP now runs `_ensure_app_access_policies` so the fix applies on Resync. LDAP is open to all authenticated users.

**Fresh deploy flow:** 8446 webadmin login and QR registration work on initial deployment without manual Sync webadmin or Resync LDAP. `_ensure_authentik_webadmin()` (includes LDAP outpost restart) runs at end of TAK Server deploy and during Connect LDAP.

**Authentik deploy:** Caddy reload had no timeout → could hang indefinitely. Added 30s timeout. Added progress message "Updating Caddy config..." before slow steps so log doesn't appear stuck.

**README:** 8 cores, 32 GB RAM recommended for full stack. Updated deployment order: Caddy → Authentik → Email Relay → TAK Server → Connect LDAP → TAK Portal → Node-RED/CloudTAK/MediaMTX.

**Git workflow:** dev = full workspace (handoff, prompts, etc.). main = public-facing only. **Never merge dev into main.** Use selective checkout:
```bash
git checkout main
git checkout dev -- app.py mediamtx_ldap_overlay.py README.md start.sh .gitignore TESTING.md fix-console-after-pull.sh reset-console-password.sh docs/MEDIAMTX-TAKPORTAL-ACCESS.md docs/WORKFLOW-8446-WEBADMIN.md docs/RELEASE-v0.1.8-alpha.md
git add -A && git status   # verify
git commit -m "v0.1.8-alpha"
git push origin main
git checkout dev
```
Exclude from main: HANDOFF, COMMANDS, PROMPT, email-template (optional).

**Removed:** `scripts/fix-mediamtx-stream-redirect.sh`, `scripts/ldap-diagnose-and-fix.sh` (optional diagnostic scripts, user deleted).

**`.gitignore`:** Added `uploads/` and `ignite/` to prevent accidental commit of deployment artifacts.

**Release:** `docs/RELEASE-v0.1.8-alpha.md` — copy contents when creating GitHub release for tag v0.1.8-alpha.

### Help Page and Uninstall-All (2026-03-02)

**Help page (`/help`):** Sidebar has a "Help" link. The Help page includes:
- **Backdoor (IP:5001)** — URL `https://<server_ip>:5001`, accept self-signed cert, log in with console password. **Full lockout:** If you can't log in at all, you must use the CLI; the **README on the GitHub repo** has the exact commands (e.g. `./reset-console-password.sh`).
- **Console password** — Same password for backdoor and "Uninstall all". Not stored in plaintext. Forgot it? Use the reset form below if logged in; for full lockout use CLI (README).
- **Reset console password** — Form (current + new + confirm) calls `POST /api/console/password/reset`; only works when already logged in. For full lockout, use CLI (README has commands).
- **Uninstall all services** — Card + modal (password, type UNINSTALL to confirm). Runs full uninstall in background; console and config remain.
- **Deployment order** and **Docs** (GitHub link) — Moved from console footer to Help.

**Uninstall all (full uninstall):**
- **Location:** Only on the Help page (removed from Console page).
- **APIs:** `POST /api/console/uninstall-all` (body: `password`, `confirm: "UNINSTALL"`), `GET /api/console/uninstall-all/status`, `POST /api/console/uninstall-all/validate` (password check for green check in UI).
- **Order:** MediaMTX → TAK Portal → CloudTAK → Node-RED → TAK Server → Email Relay → Authentik → Caddy. Console and `.config` are left in place.
- **Caddy cleanup:** Full uninstall now purges Caddy package and explicitly removes `/usr/bin/caddy`, `/usr/local/bin/caddy`, and `/etc/caddy` so the console no longer shows Caddy as installed (detection uses `which caddy`). Same cleanup applied when uninstalling Caddy from the Caddy page.
- **Leftover Caddy:** If the binary was left behind (e.g. uninstall ran before this logic), `detect_modules()` cleans up when it sees Caddy binary present but service **disabled** and **inactive** — removes binary and `/etc/caddy` so the card disappears on next page load after git pull + restart.

### This Session (2026-03-02 evening) — LDAP 403 Root Cause Found and Fixed

**STATUS: LDAP fully working. QR enrollment confirmed. SA bind, user bind, group lookups all verified.**

**Root cause of "403 Forbidden / Authentication credentials were not provided":**

The Authentik LDAP outpost uses the field `bind_flow_slug` for ALL LDAP bind operations. This field maps to the provider's `authorization_flow`, **NOT** `authentication_flow`. The provider's `authorization_flow` had been set to `ldap-authorization-flow` (an empty pass-through flow with no stages). The outpost executed this empty flow, got an anonymous session (`"authenticated":false`), and then the `/api/v3/core/users/me/` call returned 403 because the session had no user identity.

**THIS IS THE SINGLE MOST IMPORTANT THING TO KNOW:** Both `authentication_flow` and `authorization_flow` on the LDAP provider MUST point to `ldap-authentication-flow` (the flow with identification + password + login stages). If `authorization_flow` points to anything else, LDAP binds will fail with 403.

**Three bugs fixed in app.py:**

1. **Blueprint permission format** (line ~6691): `permission: search_full_directory` crashed the Authentik worker with `ValueError: For global permissions, first argument must be in format: 'app_label.codename'`. The worker retried endlessly, flooding PostgreSQL with connections ("Too many clients already"). **Fix:** Changed to `permission: authentik_providers_ldap.search_full_directory`.

2. **LDAP outpost cookie domain mismatch** (line ~6796): The LDAP outpost connected to `http://authentik-server-1:9000` (Docker internal hostname), but `AUTHENTIK_COOKIE_DOMAIN=.{fqdn}` scoped session cookies to `*.{fqdn}`. Go's HTTP client stored the authenticated session cookie for `.{fqdn}` and never sent it to `authentik-server-1` because the domain didn't match. **Fix:** When FQDN is set, the LDAP outpost now connects via `https://authentik.{fqdn}` (matching the cookie domain) with `extra_hosts` to resolve DNS internally. When no FQDN, falls back to `http://authentik-server-1:9000` (no cookie domain issue since `AUTHENTIK_COOKIE_DOMAIN` is only set when FQDN exists).

3. **Flow lookup pagination miss** (line ~8090): `_ensure_ldap_flow_authentication_none()` searched for the flow via `flows/instances/?designation=authentication` which returns paginated results. If `ldap-authentication-flow` wasn't on the first page, it was missed, and the code tried to CREATE the flow — failing with `400: slug already exists`. **Fix:** Changed to search by `slug=ldap-authentication-flow` directly.

**How the fix was diagnosed (methodology for future reference):**

1. Checked Authentik server logs: ALL outpost requests arrived as `auth_via: unauthenticated`
2. Verified outpost token was valid (worked with direct curl)
3. Used `tcpdump` inside Docker to capture actual HTTP headers from the outpost
4. Found the session cookie being sent was `"sub":"anonymous","authenticated":false"`
5. Traced the outpost Go source code: `bind_flow_slug` comes from `authorization_flow`
6. Confirmed via `/api/v3/outposts/ldap/` that `bind_flow_slug: ldap-authorization-flow` (wrong)
7. Set `authorization_flow` to `ldap-authentication-flow` → immediate fix

### Prior Session (2026-03-02 morning) — UI and Deploy Fixes

**Authentik deploy crash at Step 6:** `UnboundLocalError: local variable 're' referenced before assignment`. Step 6 (Patching Docker Compose) used `re.search()` but `import re` lived later in the same function (Step 10). Python treated `re` as local for the whole function, so it was unassigned at first use. **Fix:** Added `re` to top-level imports in `app.py` and removed the inner `import re` in Step 10.

**TAK Portal dashboard metrics (-- / not connected):** Portal could not talk to TAK Server. Two causes: (1) CA file was single-cert or used `-----BEGIN TRUSTED CERTIFICATE-----`, which Node.js does not accept; (2) Node.js needs the full cert chain (intermediate + root) for `rejectUnauthorized: true`. **Fix:** Prefer `takserver.pem` (full chain) for TAK Portal CA; fallback: build bundle from `ca.pem` + `root-ca.pem` in standard PEM format. Copy into portal `data/certs/tak-ca.pem`. Justin confirmed `takserver.pem` is the right file (server + intermediate + root in one file).

**infratak application missing in Authentik:** After redeploy (or older app.py), visiting `infratak.<fqdn>` showed "Not Found" even though the proxy provider existed. **Cause:** `_ensure_authentik_console_app` fallback search used application slug `infratak` when looking up the provider; provider name is `infra-TAK`, so search failed and app creation was skipped. **Fix:** Use URL-encoded provider *name* for search; add verification pass after loop — if application is missing (404), find provider and recreate application.

**LDAP outpost version drift:** LDAP outpost image was hardcoded (e.g. `2025.12.4`) while Authentik server moved to `2026.2.0`. **Fix:** Read server image tag from docker-compose and use same tag for LDAP outpost; if LDAP container exists but tag differs, update its image.

**Authentik UI — next steps order:** After deploy and on healthy bar, show: (1) Configure SMTP (Email Relay), (2) Deploy TAK Server, (3) Deploy TAK Portal. Buttons added for Email Relay, TAK Server, TAK Portal. Wording changed from "create users" to "make additional Admin users."

**MediaMTX deploy log:** Removed 1.5s auto-reload after deploy. Log stays visible with "✓ Deployment Complete" and "↻ Refresh Page" button (same pattern as other deploy pages).

**Removed:** "Fix LDAP bindings" button on TAK Server page (confusing once LDAP version/flow issues were fixed).

**Justin / TAK Portal feedback (for reference):** Use `takserver.pem` for CA (full chain). Portal may need restart after uploading certs. Future: adopt-existing workflow (detect TAK Server, Authentik, TAK Portal and offer to adopt into console).

### LDAP Bind Issue — FULLY RESOLVED (2026-03-02)

**Status:** LDAP fully working. SA bind, user bind, user search, group lookups, TAK Server LDAP auth, and QR enrollment ALL confirmed functional.

**Server:** `root@responder` (190.102.110.224)

**The Critical Rule (commit this to memory):**

The Authentik LDAP outpost gets its bind flow from the provider's `authorization_flow` field (exposed as `bind_flow_slug` in the outpost API). It does NOT use `authentication_flow` for binds. **Both `authentication_flow` AND `authorization_flow` MUST point to `ldap-authentication-flow`** — the flow with identification, password, and login stages. If `authorization_flow` points to anything else (empty flow, consent flow, etc.), the outpost will execute that flow instead, get an anonymous session, and ALL binds will fail with 403.

**Full root cause chain (in order of discovery):**

1. **Blueprint permission format** — `permission: search_full_directory` crashed Authentik worker with ValueError. Worker retried endlessly, flooding PostgreSQL. **Fix:** `authentik_providers_ldap.search_full_directory`.

2. **Stage recursion** — identification stage had `password_stage` set, creating a loop. **Fix:** `password_stage: None`, `user_fields: ['username']` only.

3. **LDAP app policy** — "Allow authentik Admins" policy binding blocked non-admin users. **Fix:** Removed restrictive policy binding from LDAP application.

4. **authorization_flow mismatch** (THE 403 root cause) — Provider's `authorization_flow` pointed to `ldap-authorization-flow` (empty). Outpost used this as its `bind_flow_slug`, executed an empty flow, got anonymous session, `/api/v3/core/users/me/` returned 403. **Fix:** Set `authorization_flow` to `ldap-authentication-flow`.

5. **Cookie domain mismatch** — `AUTHENTIK_COOKIE_DOMAIN=.{fqdn}` scoped session cookies to `*.{fqdn}`, but outpost connected to `http://authentik-server-1:9000` (internal hostname). Go's cookie jar stored the authenticated cookie for `.{fqdn}` and never sent it to `authentik-server-1`. **Fix:** LDAP outpost connects via `https://authentik.{fqdn}` with `extra_hosts` for DNS resolution.

6. **Flow lookup pagination** — `_ensure_ldap_flow_authentication_none()` searched by `designation=authentication` (paginated). Flow could be missed on page 2+, causing "slug already exists" error. **Fix:** Search by `slug=ldap-authentication-flow` directly.

**Diagnostic commands (run from the Authentik host; for remote Authentik use the same curls against `http://<remote_host>:9090` with token from remote `~/authentik/.env`).** User-facing summary for 8446/LDAP 49: **docs/COMMANDS.md** → "8446 / LDAP 49 (Invalid Credentials)".

```bash
TOKEN=$(grep AUTHENTIK_BOOTSTRAP_TOKEN ~/authentik/.env | cut -d= -f2)

# 1. Check LDAP provider flows (MOST IMPORTANT — both must show ldap-authentication-flow)
echo "=== LDAP provider ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:9090/api/v3/providers/ldap/?search=LDAP' | \
  python3 -c "import sys,json; r=json.loads(sys.stdin.read())['results']; [print(f'  pk={p[\"pk\"]} auth_flow={p.get(\"authentication_flow\")} authz_flow={p.get(\"authorization_flow\")} bind_mode={p.get(\"bind_mode\")}') for p in r]"

# 2. Check outpost bind_flow_slug (must be ldap-authentication-flow)
echo "=== Outpost config ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:9090/api/v3/outposts/ldap/' | \
  python3 -c "import sys,json; r=json.loads(sys.stdin.read())['results']; [print(f'  name={p.get(\"name\")} bind_flow={p.get(\"bind_flow_slug\")}') for p in r]"

# 3. Check flow bindings (should show 3 stages)
echo "=== Flow bindings ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:9090/api/v3/flows/instances/?slug=ldap-authentication-flow' | \
  python3 -c "import sys,json; r=json.loads(sys.stdin.read())['results']; pk=r[0]['pk'] if r else 'NOT FOUND'; print(f'  flow_pk={pk}')"

# 4. Check outpost logs (look for "successfully authenticated" or errors)
echo "=== Recent LDAP outpost logs ==="
docker compose logs ldap --tail=15 --no-log-prefix 2>/dev/null

# 5. Test SA bind
LDAP_PASS=$(grep AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD ~/authentik/.env | cut -d= -f2-)
echo "=== SA bind test ==="
ldapsearch -x -H ldap://127.0.0.1:389 -D 'cn=adm_ldapservice,ou=users,dc=takldap' -w "$LDAP_PASS" -b 'dc=takldap' -s base '(objectClass=*)' 2>&1 | head -5
```

### What's Deployed on the Server
- **Caddy** -- running, TLS for subdomains
- **Authentik** -- running (server, worker, postgres, LDAP outpost). Blueprint + provider correctly configured.
- **TAK Server** -- running (systemd), CoreConfig has LDAP section, connected to Authentik LDAP
- **TAK Portal** -- running (Docker)
- **Email Relay** -- running, SMTP + recovery flow auto-configured in Authentik
- **MediaMTX** -- running (LDAP overlay deployed, stream visibility, share links, themed viewer all working)

### What Works (Verified)
- All services deploy and run (Authentik-first deployment order verified on fresh VPS)
- Authentik SSO via Caddy forward_auth (infratak, takportal, nodered, mediamtx subdomains)
- Password recovery flow (forgot username or password -> email -> reset -> login)
- **LDAP bind — SA and user bind both working** (verified via ldapsearch and outpost logs)
- **QR enrollment — confirmed working** (user scans QR, connects to TAK Server, LDAP auth succeeds)
- **LDAP group lookups** — memberOf attributes correctly returned (tak_CA-COR TRT, tak_CA-COR HAZMAT, etc.)
- TAK Server 8443 (cert auth), 8446 (password auth via LDAP, admin console works for webadmin)
- TAK Portal user creation -> Authentik user creation
- **No user-profile.pref popup** -- fixed by stripping extra LDAP attributes
- **Authentik SMTP auto-configuration** -- Email Relay deploy auto-configures Postfix inet_interfaces, mynetworks, firewall rules
- **App access policies** -- auto-created on Authentik deploy
- **MediaMTX LDAP overlay** -- fully working: Authentik header auth, Web Users page, stream visibility (public/private), tokenized share links, themed viewer page, self-healing overlay
- **TAK Portal dashboard metrics** -- working (requires full TAK_URL with `:8443/Marti`)
- **TAK Portal email auto-config** -- pulls SMTP settings from Email Relay module if deployed
- **TAK Portal group filtering** -- `GROUPS_HIDDEN_PREFIXES` hides `vid_` and `tak_ROLE_` groups
- **Help page** -- Sidebar link to `/help`; backdoor URL, console password, reset form (when logged in), full-lockout note (CLI + README), Uninstall all services (modal), deployment order, Docs link
- **Uninstall all** -- Only on Help; full uninstall order MediaMTX→Portal→CloudTAK→Node-RED→TAK Server→Email→Authentik→Caddy; Caddy purge + binary/config removal; leftover Caddy cleanup in `detect_modules()` when service disabled/inactive

- **Guard Dog** -- Full deploy with 9 monitors (TAK Server) + service monitors for Authentik, MediaMTX, Node-RED, CloudTAK. Root CA / Intermediate CA escalating notification schedule. Health endpoint port 8888.
- **TAK Server update** -- Upload .deb, progress bar, cancel, update with pre-upload guard
- **Client certificate creation** -- Name + group selection (Marti API) + IN/OUT/Both permissions → .p12 download
- **Certificate expiry** -- Displayed on TAK Server page (banner + Certificates card), Console dashboard card, Rotate CA cards. Color-coded time remaining.
- **Intermediate CA rotation** -- Full workflow: new CA, server cert, admin/user certs, truststore (old CA kept), CoreConfig, TAK Portal update, TAK Server restart. Revoke old CA after transition.
- **Root CA rotation** -- Hard cutover: new PKI, all certs regenerated, TAK Portal update, restart. All clients re-enroll via QR.
- **Collapsible sections** -- TAK Server page (Update, DB Maintenance, Certificates, Rotate Int CA, Rotate Root CA, Client Cert, Server Log) and Help page (all 7 sections)
- **Console dashboard cert expiry** -- Root/Int CA time remaining on TAK Server module card, color-coded

### What's Broken (Verified)
- Nothing critical. LDAP fully resolved.

### Changes Made to app.py (Cumulative)

1. **Blueprint fix (CRITICAL)** — Removed `configure_flow`, `password_stage`, `LDAPBackend`, and `email` user field from `tak-ldap-setup.yaml` blueprint definition (lines ~6340-6364). This fixes the root cause of `exceeded stage recursion depth`.

2. **Blueprint password line removal (prior session)** — Removed `password: !Context password` from the `authentik_core.user` model in the blueprint. This prevented Authentik from overwriting the service account password on every restart.

3. **LDAP verification block** — Added comprehensive LDAP verification at end of `run_authentik_deploy` (ensures `authentication: none`, resets password, verifies bind).

4. **TAK Portal email auto-config** — `_portal_email_settings()` helper populates email settings from Email Relay config.

5. **TAK Portal TAK_URL fix** — Includes `:8443/Marti` when FQDN is set.

6. **Self-healing MediaMTX overlay** — `ensure_overlay.py` re-injects overlay on service start if upstream updates overwrite it.

7. **Session 2026-03-02 morning:** Top-level `import re` (fix Authentik Step 6 UnboundLocalError). TAK Portal CA: prefer `takserver.pem`, else build bundle from `ca.pem` + `root-ca.pem`. `_ensure_authentik_console_app`: provider search by name, application verification/recreation. LDAP outpost image tag synced from server tag in compose. MediaMTX deploy log: no auto-reload, Refresh button. Authentik next steps UI: configure SMTP → TAK Server → TAK Portal; "additional Admin users" wording; healthy bar with Email Relay, TAK Server, TAK Portal buttons. Removed "Fix LDAP bindings" button.

8. **Session 2026-03-02 evening (LDAP 403 fix):**
   - **Blueprint permission format** (line ~6691): `search_full_directory` → `authentik_providers_ldap.search_full_directory` (prevents worker crash).
   - **LDAP outpost AUTHENTIK_HOST** (lines ~6796-6800): When FQDN is set, outpost connects via `https://authentik.{fqdn}` with `extra_hosts` (prevents cookie domain mismatch). No FQDN: falls back to `http://authentik-server-1:9000`.
   - **Flow lookup fix** (lines ~8090-8094): `_ensure_ldap_flow_authentication_none()` now searches by `slug=ldap-authentication-flow` instead of `designation=authentication` (prevents pagination miss / slug-already-exists 400).
   - **JavaScript fix in TAKSERVER_TEMPLATE**: Moved `resyncLdap` and `syncWebadmin` functions to top of script block; escaped newlines in confirm() dialogs.

9. **Help page and Uninstall-all (2026-03-02):** Sidebar "Help" link and `HELP_TEMPLATE` at `/help`: backdoor (IP:5001), console password, reset form (`POST /api/console/password/reset`), full-lockout wording (CLI + README). Uninstall all moved to Help only (removed from Console template); modal with password + "UNINSTALL" confirm. Full uninstall: Caddy step purges package and removes `/usr/bin/caddy`, `/usr/local/bin/caddy`, `/etc/caddy`; Caddy page uninstall does same. In `detect_modules()`: when Caddy binary exists but service is disabled and inactive, one-time cleanup removes binary and `/etc/caddy` so card disappears (fixes leftover after uninstall before this commit). Auto-updates: show "Running..." only when enabled and running; disable also stops/disables `apt-daily-upgrade.timer`.

### Key Files Changed
- `app.py` — All prior changes plus (v0.1.9): Guard Dog deploy with 9 monitors + service monitors, TAK Server update flow (upload/progress/cancel), client cert creation (groups via Marti API), cert expiry API + display, Intermediate CA rotation, Root CA rotation, revoke old CA, ca-info API, collapsible sections (TAK Server page + Help page), console dashboard cert expiry, Help page reorder + left-align. Removed hidden "Manage" spans from console cards.
- `static/takserver.js` — Extracted TAK Server page inline script. All TAK Server JS: services, deploy, upgrade, cert expiry, groups, client cert creation, CA rotation (intermediate + root), collapsible section toggle.
- `static/guarddog.js` — Guard Dog page JavaScript.
- `scripts/guarddog/` — All Guard Dog monitor scripts (tak-port-watch.sh, tak-proc-watch.sh, tak-net-watch.sh, tak-pg-watch.sh, tak-cot-watch.sh, tak-oom-watch.sh, tak-disk-watch.sh, tak-cert-watch.sh, tak-intca-watch.sh), health endpoint script, sms_send.sh.
- `docs/TAK_Server_OpenAPI_v0.json` — TAK Server OpenAPI 3.1 spec (in-repo reference).
- `docs/REFERENCES.md` — Added OpenAPI spec entry.
- `docs/GUARDDOG.md` — Guard Dog documentation with all monitors, VACUUM guidance, scope.
- `mediamtx_ldap_overlay.py` — Stream visibility, share links, themed viewer, External Sources UI, Admin Active Streams UI

### Server Access
```bash
# SSH
ssh root@63.250.55.132

# Pull latest code, then restart console (two steps — see docs/COMMANDS.md)
cd ~/infra-TAK && git fetch origin dev && git checkout dev && git pull origin dev
sudo systemctl restart takwerx-console

# Fix LDAP / webadmin: Use infra-TAK UI → TAK Server → Connect TAK Server to LDAP
# Or manually: the Connect button runs _ensure_ldap_flow_authentication_none() which now recreates missing bindings

# Start TAK Server (currently stopped)
sudo systemctl start takserver

# Check LDAP outpost logs
cd ~/authentik && docker compose logs ldap --tail=20 --no-log-prefix

# Test LDAP bind
LDAP_PASS=$(grep AUTHENTIK_BOOTSTRAP_LDAPSERVICE_PASSWORD ~/authentik/.env | cut -d= -f2-)
ldapsearch -x -H ldap://127.0.0.1:389 -D 'cn=adm_ldapservice,ou=users,dc=takldap' -w "$LDAP_PASS" -b 'dc=takldap' -s base '(objectClass=*)'
```

### Application visibility (authentik.fqdn)
- **Admins** (users in group *authentik Admins*): see all applications (infra-TAK, Node-RED, TAK Portal, MediaMTX, LDAP, etc.).
- **Regular users**: see only **TAK Portal** and **MediaMTX** (stream). infra-TAK and Node-RED are not listed and are not accessible (proxy returns 403 if they try the URL directly).

---

## 1. Project Overview

| Field | Value |
|---|---|
| **Project name** | infra-TAK |
| **Version** | 0.1.9 |
| **Purpose** | Unified web console for deploying and managing TAK ecosystem infrastructure (TAK Server, Authentik SSO, LDAP, Caddy reverse proxy, TAK Portal, Node-RED, MediaMTX, CloudTAK, Email Relay) |
| **Intended users** | System administrators deploying TAK (Team Awareness Kit) infrastructure |
| **Operating environment** | Ubuntu 22.04/24.04 or Rocky Linux 9, single VPS, accessible via `https://<ip>:5001` (backdoor) or `https://infratak.<fqdn>` (behind Authentik) |
| **Current completion status** | Alpha → approaching beta. All modules deploy and run. Guard Dog monitoring active. Certificate management (create, rotate, revoke) operational. LDAP fully working. |

---

## 2. System Architecture

### High-Level Components

```
+-----------------------------------------------------------------+
|  Caddy (reverse proxy, TLS termination, forward_auth)            |
|  - infratak.<fqdn>  -> Flask app :5001 (via Authentik)           |
|  - authentik.<fqdn> -> Authentik :9090                           |
|  - tak.<fqdn>       -> TAK Server :8446                          |
|  - takportal.<fqdn> -> TAK Portal :3000 (via Authentik)          |
|  - nodered.<fqdn>   -> Node-RED :1880 (via Authentik)            |
|  - stream.<fqdn>    -> MediaMTX :5080 (via Authentik)            |
|  - map.<fqdn>       -> CloudTAK :5000                            |
+-----------------------------------------------------------------+
         |
+---------+--------------------------------------------+
|  Authentik (SSO / IdP)                                |
|  - Server + Worker + PostgreSQL + Redis (Docker)      |
|  - Embedded Outpost (proxy provider, forward_auth)    |
|  - LDAP Outpost (Docker, port 389->3389)              |
|  - Policies: Allow authentik Admins (group membership)|
|              Allow MediaMTX users (expression)        |
+---------+--------------------------------------------+
         | LDAP bind (port 389)
+---------+--------------------------------------------+
|  TAK Server (systemd, /opt/tak)                       |
|  - CoreConfig.xml -> <auth default="ldap">            |
|  - Service account: adm_ldapservice                   |
|  - User auth: cn={username},ou=users,dc=takldap       |
|  - Ports: 8089 (TLS / TAK clients), 8443 (cert),     |
|           8446 (pw)                                   |
+---------+--------------------------------------------+
         |
+---------+--------------------------------------------+
|  MediaMTX (systemd, /opt/mediamtx-webeditor)          |
|  - With Authentik: LDAP overlay auto-applied          |
|    - Auth via X-Authentik-* headers (no local login)  |
|    - Web Users page at /stream-access                 |
|    - Stream visibility: public/private toggle         |
|    - Tokenized share links (4h/8h/12h/24h TTL)       |
|    - Themed viewer page (/viewer)                     |
|    - vid_private/vid_public -> Active Streams only    |
|  - Without Authentik: vanilla editor (local login)    |
+------------------------------------------------------+
```

### App Access Policy Model

| App | Who sees the tile | Policy |
|---|---|---|
| TAK Portal | All authenticated users | No binding (open) |
| MediaMTX | authentik Admins + vid_private + vid_public | Expression: Allow MediaMTX users |
| infra-TAK, Node-RED, LDAP | authentik Admins only | Group membership: Allow authentik Admins |

### LDAP Group Namespaces

| Prefix | Used by | Purpose |
|---|---|---|
| `tak_` | TAK Server, TAK Portal, TAK clients | Missions, roles, agency groups |
| `vid_` | MediaMTX | Stream access (vid_private, vid_public) |
| `authentik-` | TAK Portal agencies | Agency admin groups |

TAK Portal hides `vid_*` and `tak_ROLE_*` groups via `GROUPS_HIDDEN_PREFIXES`. MediaMTX Web Users only shows `vid_*` groups.

### Data Flow: User Authentication via TAK client

1. User created in TAK Portal -> Authentik API creates user
2. User scans QR code in TAK client -> client connects to TAK Server :8089
3. TAK Server authenticates via LDAP (`LdapAuthenticator.java`)
4. TAK Server binds as service account -> `cn=adm_ldapservice,ou=users,dc=takldap`
5. TAK Server binds as user -> `cn={username},ou=users,dc=takldap` with user's password
6. LDAP outpost executes `ldap-authentication-flow` against Authentik core
7. If flow succeeds -> user authenticated -> TAK Server grants access

### LDAP Authentication Flow (Blueprint-Defined)

The `ldap-authentication-flow` is defined in `tak-ldap-setup.yaml` blueprint with:
- `authentication: none` (required — `require_outpost` causes "Flow does not apply" errors)
- 3 stages:
  - **order 10**: `ldap-identification-stage` — `user_fields: [username]`, NO `password_stage` (CRITICAL: having `password_stage` causes recursion)
  - **order 15**: `ldap-authentication-password` — backends: `[InbuiltBackend, TokenBackend]`, NO `configure_flow` (CRITICAL: having `configure_flow` causes recursion)
  - **order 20**: `ldap-authentication-login` — simple user login stage
- LDAP provider: `bind_mode: cached`, `search_mode: cached`, `mfa_support: false`

### External Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| Python 3 / Flask | Latest | Web console backend |
| Docker / Docker Compose | 29.x | Authentik, TAK Portal, Node-RED, CloudTAK |
| Caddy | Latest | Reverse proxy, auto-TLS, forward_auth |
| Authentik | 2026.2.0 | SSO, LDAP provider, proxy provider |
| TAK Server | 5.6-RELEASE-6 | CoT server, installed via .deb |
| Postfix | System | Email relay for password recovery |
| psutil | Latest | System metrics |

---

## 3. Development Environment

| Field | Value |
|---|---|
| **Language** | Python 3 (Flask), Jinja2 templates (inline in app.py), JavaScript (inline), YAML (blueprints) |
| **Framework** | Flask |
| **Platform** | Linux (Ubuntu 22.04/24.04, Rocky Linux 9) |
| **Build tools** | None (single-file app). `start.sh` bootstraps venv + systemd |
| **Config** | `.config/settings.json`, `.config/auth.json`, `.config/ssl/` |
| **Key constraint** | Entire app is a single ~550KB `app.py` file with inline HTML/JS/CSS templates |

---

## 4. Design Decisions and Rationale

### 4.1 Single-file architecture (`app.py`)

- **Decision**: Everything in one file -- routes, templates, deploy logic, API calls
- **Why**: Simplifies deployment (just `git pull && restart`), no build step
- **Tradeoff**: File is 9000+ lines, difficult to navigate and debug
- **Risk**: Merge conflicts, hard for multiple developers

### 4.2 LDAP Blueprint vs API-only approach

- **Decision**: Use Authentik blueprints (`tak-ldap-setup.yaml`) to create LDAP provider, flow, outpost, and service account
- **Why**: Blueprints are idempotent and run on Authentik startup
- **Alternatives considered**: Pure API calls (used as fallback)
- **Tradeoff**: Blueprint behavior can be opaque; `state: created` only creates once, `state: present` updates every restart
- **CRITICAL LESSON**: Blueprint `state: present` OVERWRITES API changes on every Authentik restart. Any manual API fix to stages/bindings will be lost. The blueprint file itself must be correct.

### 4.3 LDAP flow stage design (CRITICAL — learned the hard way)

- **Decision**: LDAP flow stages must NOT have `configure_flow` or embedded `password_stage`
- **Why**: The LDAP outpost executes flows programmatically (not via browser). When the password stage has a `configure_flow`, a failed password check redirects to the password-change flow, which loops back. When the identification stage has `password_stage` embedded, it creates a double-password collection pattern. Both cause `exceeded stage recursion depth` in the outpost.
- **Symptoms**: Outpost logs show `"error":"exceeded stage recursion depth","event":"failed to execute flow"`. The bind returns `Invalid credentials (49)`.
- **Why it was hidden**: `bind_mode: cached` means the outpost caches successful bind sessions. When the flow worked once (before the recursion bug was triggered), the cache masked the problem. Only when caches expired or were cleared (restart, recreate) did the actual broken flow execution surface.
- **Resolution**: Removed `configure_flow` and `password_stage` from the blueprint. Also removed `LDAPBackend` (not needed) and `email` from user_fields (LDAP uses username only).

### 4.4 LDAP flow authentication setting

- **Decision**: The `ldap-authentication-flow` uses `authentication: none` (was `require_outpost`)
- **Why**: `require_outpost` caused "Flow does not apply to current user" -- the outpost was not recognized when executing user binds. The flow is only reachable via LDAP on port 389, so `none` adds no security risk.
- **Implementation**: Blueprint has `authentication: none`; "Connect TAK Server to LDAP" runs `_ensure_ldap_flow_authentication_none()` which PATCHes the live flow and restarts the LDAP outpost

### 4.5 LDAP provider authorization_flow = authentication_flow (CRITICAL)

- **Decision**: Both `authentication_flow` and `authorization_flow` on the LDAP provider point to `ldap-authentication-flow`
- **Why**: The outpost reads `authorization_flow` as its `bind_flow_slug` — this is the flow executed for every LDAP bind. Despite the name, `authentication_flow` is NOT used for binds. If `authorization_flow` points to an empty or consent-only flow, no authenticated session is created, and all binds fail with 403 on the `/api/v3/core/users/me/` call.
- **How discovered**: tcpdump + Go source analysis of the LDAP outpost. The `FlowExecutor` reads `bind_flow_slug` which maps to `authorization_flow` in the provider API.
- **NEVER change `authorization_flow` to a different flow** (consent flow, empty flow, etc.) — this silently breaks ALL LDAP binds.

### 4.5b LDAP outpost AUTHENTIK_HOST and cookie domain matching

- **Decision**: When FQDN is set, LDAP outpost `AUTHENTIK_HOST` = `https://authentik.{fqdn}` with `extra_hosts` for DNS. When no FQDN, = `http://authentik-server-1:9000`.
- **Why**: `AUTHENTIK_COOKIE_DOMAIN=.{fqdn}` scopes session cookies to `*.{fqdn}`. After a successful flow execution, the outpost stores an authenticated session cookie. If the outpost's `AUTHENTIK_HOST` doesn't match the cookie domain (e.g., it connects to `authentik-server-1`), Go's `http.CookieJar` never sends the cookie, and subsequent API calls (like `/api/v3/core/users/me/`) return 403 anonymous.
- **`extra_hosts`**: Maps `authentik.{fqdn}` to `host-gateway` (Docker's host IP) so the LDAP container can resolve the FQDN internally without external DNS / hairpin NAT.

### 4.6 LDAP outpost token injection

- **Decision**: Docker-compose starts LDAP with `AUTHENTIK_TOKEN: placeholder`, then Step 11 injects the real token and recreates the container
- **Why**: The real token doesn't exist until after Authentik is running and the blueprint creates the outpost
- **Risk**: If token injection fails, the LDAP outpost runs with an invalid token and stays unhealthy

### 4.7 Caddy forward_auth pattern

- **Decision**: Caddy uses `forward_auth 127.0.0.1:9090` with Authentik's embedded outpost
- **Why**: Native Caddy integration, no separate proxy container needed
- **Pattern**: `/outpost.goauthentik.io/*` routes must come before `forward_auth` in Caddy's `route` block
- **Backdoor**: `infratak.<fqdn>/login*` skips `forward_auth` so the console password login always works
- **MediaMTX bypasses**: `/watch/*`, `/hls-proxy/*`, `/shared/*`, `/shared-hls/*` bypass `forward_auth` on the stream subdomain for public/shared stream access

### 4.8 Service account in authentik Admins group

- **Decision**: `adm_ldapservice` is added to the `authentik Admins` group (superuser)
- **Why**: Workaround for Authentik bug where `search_full_directory` permission doesn't work reliably
- **Risk**: Overprivileged service account

### 4.9 CoreConfig LDAP stanza -- matches TAK Portal reference

- **Decision**: The `<ldap>` element uses only the attributes from TAK Portal's known-good reference, plus `adminGroup="ROLE_ADMIN"`
- **Why**: Extra attributes (`style="DS"`, `ldapSecurityType="simple"`, `groupObjectClass`, `userObjectClass`, `matchGroupInChain`, `roleAttribute`) caused a phantom `user-profile.pref` push to TAK clients on connect. Stripping them fixed the issue. `adminGroup="ROLE_ADMIN"` is required for webadmin to access the admin console (without it, everyone gets WebTAK).
- **Reference stanza** (TAK Portal project `docs/authentik-tak-server.md`):
  ```xml
  <ldap url="ldap://..." userstring="cn={username},ou=users,dc=takldap"
    updateinterval="60" groupprefix="cn=tak_"
    groupNameExtractorRegex="cn=tak_(.*?)(?:,|$)"
    serviceAccountDN="cn=adm_ldapservice,ou=users,dc=takldap"
    serviceAccountCredential="..." groupBaseRDN="ou=groups,dc=takldap"
    userBaseRDN="ou=users,dc=takldap" dnAttributeName="DN" nameAttr="CN"/>
  ```
- **Our addition**: `adminGroup="ROLE_ADMIN"` appended

### 4.10 CoreConfig auth block structure

- **Decision**: The `<auth>` block uses `<ldap .../>` before `<File .../>` (not the other way around)
- **Why**: Matches the known-good CoreConfig from a working deployment. Reversing the order caused issues.
- **Critical attributes on `<auth>`**: `x509groups="true"`, `x509useGroupCache="true"`, `x509useGroupCacheDefaultActive="true"`, `x509checkRevocation="true"` -- without these, TAK clients get disconnected when webadmin logs into 8446

### 4.11 CoreConfig LDAP detection

- **Decision**: Check for substring `adm_ldapservice` in CoreConfig, not `serviceAccountDN="cn=adm_ldapservice"`
- **Why**: The full attribute value is `serviceAccountDN="cn=adm_ldapservice,ou=users,dc=takldap"` -- checking for `serviceAccountDN="cn=adm_ldapservice"` (with closing `"`) never matches because `"` follows `dc=takldap`, not `adm_ldapservice`. This bug caused false negatives.

### 4.12 MediaMTX LDAP overlay (deploy-time patching)

- **Decision**: Keep one branch on the MediaMTX repo (vanilla editor). infra-TAK applies `mediamtx_ldap_overlay.py` at deploy time when Authentik is detected.
- **Why**: Standalone MediaMTX users get the vanilla editor unchanged. infra-TAK users get Authentik header auth + Stream Access page without maintaining a separate LDAP branch.
- **Implementation**: Copy overlay file, inject gated import (`LDAP_ENABLED` env var) before `app.run()`, set env vars in systemd service.
- **Self-healing**: `ensure_overlay.py` runs as `ExecStartPre` in the systemd service. If the upstream editor self-updates and overwrites the overlay injection, this script re-applies it on every service start.

### 4.13 App access policies (automated)

- **Decision**: Auto-create and bind Authentik policies during Authentik deploy
- **Why**: Regular users should only see TAK Portal tile. Admins see everything. MediaMTX visible to vid_* group members.
- **Implementation**: `_ensure_app_access_policies()` creates "Allow authentik Admins" (group membership) and "Allow MediaMTX users" (expression policy checking vid_private OR vid_public OR authentik Admins). Idempotent -- safe to run on every deploy.

### 4.14 Blueprint password management

- **Decision**: The blueprint `authentik_core.user` model does NOT set `password` (the line `password: !Context password` was removed)
- **Why**: With `state: created`, Authentik only applies the user model once. But `state: present` or blueprint reconciliation could overwrite the API-set password with a hashed version of the env var, causing LDAP bind failures. The password is set exclusively via the Authentik API (`/api/v3/core/users/{pk}/set_password/`) after user creation.
- **CRITICAL LESSON**: Never set password in blueprints for service accounts that need to authenticate via LDAP. The password must be set via API to ensure proper hashing.

---

## 5. Problems Encountered During Development

| # | Problem | Root Cause | Resolution |
|---|---|---|---|
| 1 | Recovery flow redirects to "Welcome to Authentik" | Wrong stage bindings | Rewrote to fetch ALL bindings, filter client-side |
| 2 | "When no user fields are selected..." (HTTP 400) | Creating separate identification stage | Reuse `default-authentication-identification` |
| 3 | "Forgot password?" link not showing | recovery_flow set on wrong stage | Set on `default-authentication-identification` |
| 4 | infratak bypasses Authentik login | route block missing forward_auth | Removed specific route; generic route handles all |
| 5 | LDAP service account path mismatch | path defaults to service-accounts | Added `path: users` to blueprint and API |
| 6 | ldapsearch always returns error 49 | Authentik LDAP outpost incompatibility | Check outpost Docker logs instead |
| 7 | "Flow does not apply to current user" | authentication: require_outpost | Changed to authentication: none |
| 8 | LDAP outpost unhealthy after deploy | Token still "placeholder" | Moved LDAP start to after token injection |
| 9 | search_full_directory ValueError | Authentik 2025.x permission format change | Service account in Admins group (workaround) |
| 10 | CoreConfig patch not applying | Regex required exact whitespace | Replaced with str.find() span replacement |
| 11 | CoreConfig LDAP detection false negative | Substring check matched wrong part | Check for `adm_ldapservice` substring only |
| 12 | webadmin not in LDAP after Authentik-first | Only created when /opt/tak existed | Added to Connect flow regardless of order |
| 13 | user-profile.pref phantom popup | Extra LDAP attributes (style, roleAttribute, etc.) | Stripped to match TAK Portal reference stanza |
| 14 | webadmin gets WebTAK not admin console | adminGroup="ROLE_ADMIN" was stripped | Added adminGroup back (the only extra attr needed) |
| 15 | Authentik not sending recovery emails | Postfix inet_interfaces=localhost, firewall blocking Docker | Auto-configure inet_interfaces=all, mynetworks, ufw/firewalld rules |
| 16 | MediaMTX editor not found at deploy | Clone dir deleted before file copied | Moved cleanup after copy+patching |
| 17 | **"exceeded stage recursion depth"** | **Blueprint password stage had `configure_flow` pointing to default-password-change; identification stage had embedded `password_stage`** | **Removed both from blueprint. The `configure_flow` redirected on auth failure, creating infinite loop. The embedded `password_stage` created double-password pattern. Fixed in blueprint definition in app.py.** |
| 18 | **Blueprint overwrites API fixes** | **`state: present` in blueprint re-applies stage config on every Authentik restart** | **Must fix the blueprint file itself, not just API. Any API-only fix gets overwritten.** |
| 19 | **Blueprint overwrites service account password** | **`password: !Context password` in user model caused password drift** | **Removed password line from blueprint user model. Password set exclusively via API.** |
| 20 | **"Access denied for user" after flow fix** | **LDAP app policy binding restricted to "authentik Admins" group** | **Deleted restrictive policy binding from LDAP application via API** |
| 21 | Authentik deploy Step 6 crash | `re` used before assignment (inner `import re` in same function) | Top-level `import re`, remove inner import |
| 22 | TAK Portal dashboard -- / not connected | CA single cert or TRUSTED CERTIFICATE format; missing full chain | Use takserver.pem or ca.pem+root-ca.pem bundle |
| 23 | infratak app missing after redeploy | Provider search used slug; app never recreated if missing | Search by provider name; verify apps exist, recreate if 404 |
| 24 | LDAP outpost version mismatch | Hardcoded LDAP image tag | Read server tag from compose, set LDAP image to same |
| 25 | **403 "Authentication credentials were not provided" on all LDAP binds** | **Provider `authorization_flow` pointed to empty flow; outpost uses it as `bind_flow_slug`, NOT `authentication_flow`** | **Set both `authentication_flow` AND `authorization_flow` to `ldap-authentication-flow`** |
| 26 | **Cookie domain mismatch for LDAP outpost** | **Outpost connected to Docker internal hostname; `AUTHENTIK_COOKIE_DOMAIN` scoped cookies to FQDN; Go cookie jar never sent auth cookies** | **LDAP outpost `AUTHENTIK_HOST` = `https://authentik.{fqdn}` with `extra_hosts` when FQDN set** |
| 27 | **Blueprint permission ValueError** | **`search_full_directory` not in `app_label.codename` format; worker crash-looped, flooding PostgreSQL** | **Changed to `authentik_providers_ldap.search_full_directory`** |
| 28 | **Flow lookup "slug already exists" 400** | **Searched by `designation=authentication` (paginated), missed flow, tried to recreate** | **Search by `slug=ldap-authentication-flow` directly** |

---

## 6. Patterns and Methods That Worked Well

### 6.1 Non-destructive flow binding management
Fetch ALL bindings across all flows, filter client-side. Only delete bindings on the target flow that shouldn't be there.

### 6.2 Outpost log verification
`docker logs authentik-ldap-1 --since Xs` for "authenticated" strings is the only reliable LDAP bind verification.

### 6.3 Idempotent API calls with fallback
POST to create -> catch 400 -> GET to find existing -> PATCH to update. Used for providers, applications, users, groups, and policies.

### 6.4 Blueprint + API redundancy
Blueprint creates resources on startup. API code also creates/ensures them. System works regardless of blueprint success.

### 6.5 Pre-LDAP backup
`CoreConfig.xml.pre-ldap.bak` created before patching. Only created once (won't overwrite).

### 6.6 TAK Portal reference as source of truth
LDAP stanza matches TAK Portal's `docs/authentik-tak-server.md` exactly (plus adminGroup). Any deviation causes issues.

### 6.7 Substring matching for config detection
Match unique substring (`adm_ldapservice`) rather than full `key="value"` pattern.

### 6.8 Blueprint debugging methodology
When LDAP breaks: check outpost logs FIRST for the specific error. "exceeded stage recursion depth" = flow stage problem. "Access denied" = permission/authorization problem. "Invalid credentials (49)" = password mismatch. Don't change passwords if the error is about stages.

---

## 7. Known Limitations and Technical Debt

### HIGH

- `search_full_directory` permission requires `authentik_providers_ldap.search_full_directory` format — workaround is superuser via Admins group
- Single 550KB `app.py` file
- No automated tests
- No CI/CD pipeline

### MEDIUM

- LDAP `bind_mode: cached` and `search_mode: cached` -- cache behavior during outpost recreation poorly understood. Cache masks flow execution bugs until it expires.
- Hardcoded LDAP base DN `DC=takldap` and group prefix `tak_`
- Inline HTML/JS/CSS in Python strings
- systemd service still named `takwerx-console`
- VM needs 8+ cores / 16GB+ RAM for all services (4-core machines get overloaded during cascading restarts)

### LOW

- Browser cache causes stale UI
- No rate limiting or CSRF protection beyond Flask session

---

## 8. Configuration and Setup Instructions

### Fresh Deployment

```bash
git clone --depth 1 -b dev https://github.com/takwerx/infra-TAK.git ~/infra-TAK
cd ~/infra-TAK && chmod +x start.sh && sudo ./start.sh
```

### Deployment Order (Authentik-first, verified 2026-02-23)

1. **Caddy** -- set FQDN and TLS
2. **Authentik** -- auto-creates recovery flow, LDAP, apps, access policies
3. **Email Relay** -- auto-configures Authentik SMTP + Postfix + firewall
4. **TAK Server** -- upload .deb and deploy
5. **Connect TAK Server to LDAP** -- button on TAK Server page
6. **TAK Portal** -- deploy (auto-configures email if relay deployed, TAK_URL with :8443/Marti)
7. **MediaMTX** -- deploy (auto-applies LDAP overlay when Authentik present, self-healing on update)
8. **Node-RED, CloudTAK** -- as needed

---

## 9. Critical Knowledge Transfer Notes

### Hidden Assumptions

- TAK Server is a **systemd service**, NOT Docker. `sudo systemctl restart takserver` after CoreConfig changes.
- LDAP outpost maps host port **389->3389** (not 389->389).
- `authentik_host` for LDAP outpost: when FQDN is set, uses `https://authentik.{fqdn}` with `extra_hosts` (must match cookie domain). When no FQDN, uses `http://authentik-server-1:9000` (Docker internal). Embedded outpost always uses public URL. These are DIFFERENT.
- **The outpost `bind_flow_slug` comes from the provider's `authorization_flow`, NOT `authentication_flow`.** This is the #1 LDAP debugging gotcha.
- The LDAP stanza MUST match TAK Portal's reference. Extra attributes cause phantom device profile pushes.
- `adm_ldapservice` user pk is **54** on the current server (was recreated during debugging — original was pk=48).

### Gotchas

- **LDAP provider `authorization_flow` = `bind_flow_slug`** — This is the flow executed for EVERY LDAP bind. `authentication_flow` is NOT used. Both must be `ldap-authentication-flow`. If wrong, you get 403 on all binds.
- **LDAP outpost `AUTHENTIK_HOST` must match cookie domain** — If `AUTHENTIK_COOKIE_DOMAIN=.{fqdn}`, the outpost must connect to a `*.{fqdn}` hostname, not a Docker internal name.
- **`ldapsearch` CLI is UNRELIABLE** against Authentik's LDAP outpost. Use Docker logs.
- **Authentik blueprints with `state: present`** re-apply on every restart. API changes get overwritten. FIX THE BLUEPRINT FILE.
- **Browser cache** aggressively caches Authentik login pages. Hard refresh often needed.
- **`flow__pk` API filter on bindings is broken**. Always fetch all and filter client-side.
- **CoreConfig `.pre-ldap.bak`** is only created once. Don't overwrite.
- **Never check for `serviceAccountDN="cn=adm_ldapservice"`** (with closing quote). Check for `adm_ldapservice` substring.
- **CoreConfig auth block element order**: `<ldap .../>` before `<File .../>`.
- **LDAP flow stages MUST NOT have `configure_flow` or `password_stage`** — causes `exceeded stage recursion depth`.
- **LDAP outpost caches flow execution results** — `docker compose up -d --force-recreate ldap` required after flow changes.
- **Password MUST be set via API**, never via blueprint. Use `/api/v3/core/users/{pk}/set_password/`.
- **4-core VMs struggle** under full load. Cascading restarts of Authentik + TAK Server can spike load to 25+ and cause all services to become unresponsive.

### Edge-Case Logic That Must Not Be Removed

- `_ensure_authentik_recovery_flow`: Client-side binding filter (`target == recovery_flow_pk`) is critical
- `_ensure_authentik_ldap_service_account`: `path: 'users'` patch is required
- `generate_caddyfile`: `/login*` route without `forward_auth` is the backdoor
- `generate_caddyfile`: `/watch/*`, `/hls-proxy/*`, `/shared/*`, `/shared-hls/*` bypass `forward_auth` on stream subdomain
- `_coreconfig_has_ldap`: Must check `adm_ldapservice` substring, NOT full attribute
- `_apply_ldap_to_coreconfig`: Uses `str.find()` NOT regex. `<ldap>` before `<File>`.
- `_ensure_authentik_webadmin`: Must run during Connect flow regardless of deploy order
- `_ensure_app_access_policies`: Runs after all apps created in Authentik deploy. Idempotent.
- `ensure_overlay.py`: Self-healing script that re-injects LDAP overlay if upstream editor updates overwrite it. Runs as `ExecStartPre` in systemd service.

### Authentik LDAP Flow Architecture (MUST understand to debug)

**THE CRITICAL MAPPING:**
```
Provider Field             → Outpost Behavior
authentication_flow        → NOT used for binds (confusingly named)
authorization_flow         → bind_flow_slug (THIS is what runs for every LDAP bind)
```
Both fields MUST point to `ldap-authentication-flow`. If `authorization_flow` is wrong, binds will silently fail with 403.

**Cookie domain constraint:** The LDAP outpost stores an authenticated session cookie after flow execution. `AUTHENTIK_COOKIE_DOMAIN` scopes these cookies. The outpost's `AUTHENTIK_HOST` must match the cookie domain or cookies won't be sent on subsequent requests. When FQDN is set: outpost connects via `https://authentik.{fqdn}` (matches `.{fqdn}` cookie domain). When no FQDN: outpost connects via `http://authentik-server-1:9000` (no cookie domain set).

```
LDAP Bind Request (port 389)
  → LDAP Outpost Container (authentik-ldap-1)
    → Extracts username from bind DN (cn=USERNAME,ou=users,dc=takldap)
    → Checks session cache (bind_mode: cached)
      → If cached session matches DN+password hash: return success immediately
      → If no cache hit: execute bind_flow_slug (= provider's authorization_flow)
        → Stage 1 (order 10): ldap-identification-stage
          - Finds user by username field
          - MUST NOT have password_stage (causes recursion)
        → Stage 2 (order 15): ldap-authentication-password
          - Verifies password against InbuiltBackend
          - MUST NOT have configure_flow (causes recursion)
        → Stage 3 (order 20): ldap-authentication-login
          - Creates authenticated session
        → Flow complete: session cookie stored
    → Outpost calls /api/v3/core/users/me/ with session cookie
      → Cookie domain MUST match AUTHENTIK_HOST or this returns 403
    → If user info retrieved: bind succeeds, cache session
    → Return LDAP bind result to client
```

Error decoding:
- `exceeded stage recursion depth` = flow stage misconfiguration (configure_flow, password_stage, MFA)
- `Invalid credentials (49)` = password wrong OR flow failed to execute
- `Insufficient access (50)` / `Access denied for user` = user authenticated but not authorized for LDAP application
- `403 Authentication credentials were not provided` = cookie domain mismatch OR authorization_flow is wrong (no session created)
- `Flow does not apply to current user` = flow `authentication` setting is wrong (should be `none`)
- `authenticated from session` in logs = using cached bind (may mask underlying flow issues)

---

## 10. Future Work

### Two-server remote deployment (TAK Server DB / core split)

**Status:** **Implemented** (see Section 0 — Two-Server Split Mode). Console supports full two-server deploy (Server One = DB, Server Two = Core), Guard Dog remote DB monitoring, two-server TAK Server update, Restart DB / Restart Both, Sync DB password, and remote VACUUM/CoT size. Remaining follow-up: ensure 8443/8446 work reliably after Sync DB password (and that password capture works on all Server One images, including those without `grep -P`). Optional: "Test DB connection" or "Show DB password" in UI for debugging.

**Future:** Reuse the same pattern (SSH, config sync, health checks) for other services (e.g. Authentik, TAK Portal, MediaMTX on separate hosts) if needed. Design decisions for any new remote services could go in `docs/REMOTE-SERVICES-DEPLOYMENT.md`.
