# infra-TAK — Copy-paste commands

## Fresh clone on a VPS (dev branch)

```bash
git clone --depth 1 -b dev https://github.com/takwerx/infra-TAK.git
cd infra-TAK
chmod +x start.sh
sudo ./start.sh
```

Then open the URL shown (e.g. `https://<VPS_IP>:5001`) and set your admin password. **start.sh** adds port 5001 to UFW/firewalld (if present) so the backdoor is allowed as soon as the console is running. Caddy deploy also adds 5001; TAK Server deploy adds 22, 8089, 8443, 8446, 5001 and may enable UFW.

---

## TAK Portal enrollment + Authentik (new user password)

When you enroll a user in TAK Portal, they get an email with a link to TAK Portal. In infra-TAK that link goes through **Authentik** first (login/gateway), not straight to a "set password" page. The **standard TAK Portal email template** does not mention this.

**Intended flow:** User clicks the link → lands on Authentik → uses **Forgot password** to set their password (recovery email is sent via your Email Relay / Authentik SMTP) → then can sign in and reach TAK Portal.

**Recommendation:** Edit the **User Created (without Password)** email template in TAK Portal to tell new users to use **Forgot password?** on the login page. A ready-to-paste HTML version is in **`docs/email-template-user-created-without-password.html`**.

---

## Authentik — who sees which applications

**Desired model:**

- **Regular TAK Portal user** (created in TAK Portal, set password via Forgot password): Sees **only TAK Portal** on "My applications".
- **authentik Admins**: See **all** applications (infra-TAK, TAK Portal, MediaMTX, Node-RED).
- **TAK Portal** itself: Once they open TAK Portal, what they see there is controlled by TAK Portal + LDAP (e.g. agency admin vs regular user). Authentik only controls whether the **TAK Portal tile** appears.
- **MediaMTX** tile: Visible to `authentik Admins` + users in `vid_admin`, `vid_private`, or `vid_public` LDAP groups. Once inside, MediaMTX checks LDAP groups for what you get:
  - `vid_admin` → full config editor (like agency admin in TAK Portal)
  - `vid_private` / `vid_public` → active streams page only

**Automated on deploy:** infra-TAK creates two policies during Authentik deploy:

1. **Allow authentik Admins** (group membership) — bound to admin-only apps: infra-TAK, Node-RED, LDAP.
2. **Allow MediaMTX users** (expression) — bound to MediaMTX; allows `authentik Admins` OR `vid_admin` / `vid_private` / `vid_public`.

TAK Portal is left unbound so all authenticated users see it. No manual steps required.

**Manual override (if needed):**

1. **Policies** — Admin → **Policies** → look for `Allow authentik Admins` and `Allow MediaMTX users`.

2. **Admin-only apps** (infra-TAK, Node-RED, LDAP) → bind `Allow authentik Admins`.

3. **MediaMTX** → bind `Allow MediaMTX users` (covers admins + vid groups).

4. **TAK Portal** — should have **no** restrictive bindings.

**Result:**
- Regular TAK Portal users → see only **TAK Portal**.
- Users in `vid_admin` / `vid_private` / `vid_public` → see **TAK Portal** + **MediaMTX**.
- **authentik Admins** → see **all** applications.
- Inside each app, LDAP groups control permissions (agency admin, vid_admin, etc.).

---

## Authentik — what deploy sets up (and what it doesn’t)

**When you click “Deploy Authentik” in infra-TAK, we do this:**

| What we set up | Details |
|----------------|--------|
| **One brand** | We create/use the default brand and set its **domain** to the configured Authentik host (from Caddy/Domains; default `tak.<your-fqdn>` = hub / app tiles). We do **not** set logo, background, or “Default flows” on that brand. |
| **LDAP** | Blueprint installs LDAP provider, service account (`adm_ldapservice`), outpost (port 389). TAK Server CoreConfig is patched if TAK is already installed. |
| **Users & groups** | We create the **tak_ROLE_ADMIN** group and the **webadmin** user (for TAK Server admin). We create **adm_ldapservice** and set its password. |
| **TAK Portal proxy** | We create the “TAK Portal Proxy” provider and application, and add it to the embedded outpost so `takportal.<fqdn>` goes through Authentik. We use Authentik’s existing **authorization** and **invalidation** flows; we don’t create or change those flows. |
| **Policies** | We create **Allow authentik Admins** and **Allow MediaMTX users** and bind them to the right applications so only admins see infra-TAK/Node-RED and the right users see MediaMTX. |
| **Cookie domain** | On reconfigure we set cookie domain so the same session works across subdomains (e.g. stream., takportal., tak.). |

**What we do *not* set up on deploy:**

- **Recovery flow (“Forgot password”)** — We do **not** create or link the recovery flow during Authentik deploy. That happens when you run **Email Relay → “Configure Authentik to use these settings”**. That step pushes SMTP into Authentik and creates/links the **default-password-recovery** flow so “Forgot password?” works. So if you haven’t run that, the brand’s “Recovery flow” can stay empty and Forgot password won’t work until you configure Authentik from the Email Relay page.
- **Brand “Default flows”** — We never set **Authentication flow**, **Recovery flow**, or **User settings flow** on the brand. Whatever Authentik ships with (or you set manually) is what you get. You don’t have to mirror anything unless you add a **new** brand (e.g. for takportal.<fqdn>) and want that brand to use the same flows.
- **Logo / background / Custom CSS** — All of that is optional and done by you in **System → Brands** → [your brand] → Branding settings.
- **Extra brands** — We only ensure one brand exists and set its domain. If you want a different look for `takportal.<fqdn>`, you create a **new** brand yourself and set its domain to that hostname.

**Short version:** Deploy gives you one brand (domain set), LDAP, webadmin, TAK Portal proxy, and policies. Forgot password comes from **Email Relay → Configure Authentik**. Everything else (flows on the brand, logo, background, extra brands) is optional and up to you.

---

## Authentik — configurable “home” subdomain

The “home” is the hostname where you open Authentik and see the application tiles (infra-TAK, TAK Portal, Node-RED, MediaMTX, etc.). You can also go directly to e.g. `nodered.<fqdn>` or `stream.<fqdn>` and sign in there; the tiles are just one place to start. **Defaults:** Authentik home = `tak.<fqdn>`, TAK Server WebGUI = `takserver.<fqdn>`. Other service URLs (stream, map, takportal, nodered, etc.) are unchanged.

**You can set the Authentik home to any subdomain.** In **Caddy** (Domains), set the **Authentik** service domain to the subdomain you want (default: `tak` → `tak.<fqdn>`). You can change it to e.g. `portal` or `apps` so the home is `portal.<fqdn>` or `apps.<fqdn>`. Do this before you deploy Authentik, or change it later: update the domain in **Caddy → Domains**, save, then on the **Authentik** page click **Update config & reconnect**. We sync the new host to .env, LDAP outpost, brand, and embedded outpost, then restart so everything matches.

---

## Authentik — landing page background (branding)

**Requires authentik 2025.4.0+.** The login/landing page background is controlled by the **Default flow background** setting on the brand.

**Via UI**

1. Log in to Authentik as an admin.
2. Go to **System** → **Brands**.
3. Open your brand (e.g. the one used for `tak.<your-domain>` or whatever you set in Caddy/Domains for Authentik).
4. In **Branding settings**, set **Default flow background** to an image (upload or URL). You can also set **Logo**, **Favicon**, **Branding title**, and **Custom CSS** there.

**Via API**

1. Get a token: Authentik Admin → **System** → **Tokens** → create a token with API access (or use an existing one).
2. List brands and get the brand UUID:
   ```bash
   curl -s -H "Authorization: Bearer YOUR_TOKEN" \
     "https://authentik.YOUR_DOMAIN/api/v3/core/brands/" | jq '.results[] | {brand_uuid, domain}'
   ```
3. Update the brand. The field for the default flow background is **`default_flow_background`** (or in some versions **`flow_background`**). The value is usually the UUID of an uploaded media file. To see current brand fields:
   ```bash
   curl -s -H "Authorization: Bearer YOUR_TOKEN" \
     "https://authentik.YOUR_DOMAIN/api/v3/core/brands/BRAND_UUID/" | jq .
   ```
   Then PATCH the brand with the field you want to change, e.g.:
   ```bash
   curl -X PATCH -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
     -d '{"default_flow_background": "MEDIA_FILE_UUID"}' \
     "https://authentik.YOUR_DOMAIN/api/v3/core/brands/BRAND_UUID/"
   ```
   To use an image URL instead of an uploaded file, some versions accept a URL string; if not, upload the image via Authentik’s **File** / media API first and use the returned UUID.

**Custom CSS (2025.4.0+)** in the same Brand form can further tweak the look (e.g. overlay, gradients). See [Authentik Custom CSS](https://docs.goauthentik.io/brands/custom-css/).

---

## Authentik password recovery — not receiving email

If users click **Forgot username or password**, enter their username, but never get the reset email, work through these checks. (TAK Portal sending email means the relay works; the break is between Authentik and the relay.)

**Quick diagnostic (run on the server)**

```bash
# 1) Authentik has SMTP in .env?
grep AUTHENTIK_EMAIL__ ~/authentik/.env
# Expect: AUTHENTIK_EMAIL__HOST=host.docker.internal, AUTHENTIK_EMAIL__PORT=25, AUTHENTIK_EMAIL__FROM=...

# 2) Containers can reach host? Override must exist.
grep -A2 "server:" ~/authentik/docker-compose.override.yml
# Expect: extra_hosts: and "host.docker.internal:host-gateway"

# 3) From inside the worker, can we reach host:25? (use python if nc not in image)
docker exec authentik-worker-1 python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('host.docker.internal', 25)); print('OK'); s.close()"
# Expect: OK. If timeout: Postfix inet_interfaces or firewall. Allow Docker→host port 25 (see below).

# 4) When did Postfix last see mail from Authentik?
sudo grep -i "authentik\|127.0.0.1\|relay" /var/log/mail.log | tail -20

# 5) Authentik worker email errors (container name may be authentik-worker-1)
docker ps --format "{{.Names}}" | grep -i authentik
docker logs authentik-worker-1 --tail 300 2>&1 | grep -i "email\|smtp\|error\|failed"
```

If (1) or (2) is missing, run **Email Relay** → **Configure Authentik to use these settings** and reload the page until the card shows **✓ Authentik SMTP: Configured**. If (3) **times out**, fix in order:

**A) Postfix listening only on localhost**
```bash
sudo postconf -e 'inet_interfaces = all'
sudo systemctl restart postfix
```

**B) Firewall blocking Docker → host port 25.** Authentik containers are usually on 172.18.0.0/16; allow that (or 172.16.0.0/12 to cover all Docker subnets):
```bash
sudo ufw allow from 172.18.0.0/16 to any port 25
# or: sudo ufw allow from 172.16.0.0/12 to any port 25
sudo ufw reload
```

Then retest from container (expect `OK`):
```bash
docker exec authentik-worker-1 python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('host.docker.internal', 25)); print('OK'); s.close()"
```

If (4) shows nothing when you trigger a reset, Authentik isn't reaching Postfix. If (5) shows errors, that's the direct cause.

**1. Authentik SMTP configured**

- In the infra-TAK console: **Email Relay** → **Configure Authentik to use these settings** (run this after the relay is deployed so Authentik uses Postfix on the host).
- On the server:
  ```bash
  grep AUTHENTIK_EMAIL__ ~/authentik/.env
  ```
  You should see `AUTHENTIK_EMAIL__HOST=host.docker.internal`, `AUTHENTIK_EMAIL__PORT=25`, and `AUTHENTIK_EMAIL__FROM=...`.

**2. Containers can reach host Postfix**

- Check that the override is present:
  ```bash
  cat ~/authentik/docker-compose.override.yml
  ```
  It should add `extra_hosts: - "host.docker.internal:host-gateway"` for `server` and `worker`. If missing, run **Configure Authentik** again from the Email Relay page, or create the override and run `cd ~/authentik && docker compose up -d --force-recreate`.

**3. Test with a local Authentik user (e.g. superuser)**

- In Authentik Admin: **Directory** → **Users** → open your admin user → ensure **Email** is set.
- Log out, go to the login page, click **Forgot username or password**, enter that user's username.
- If the superuser gets the reset email, SMTP and the recovery flow work; the problem may be specific to users created by TAK Portal (e.g. LDAP user email not set or not visible to Authentik).
- If the superuser also does **not** get the email, the issue is Authentik SMTP or the recovery flow (see below).

**4. Recovery flow and "Forgot" link**

- In Authentik Admin: **Flows & Stages** → **Flows** → open the recovery flow (e.g. **Password Recovery** / `default-password-recovery`). It should have stages: Identification → Recovery Email → prompt (new password) → User Write → User Login.
- **Stages** → **Identification** → open **default-authentication-identification** → **Recovery flow** should be set to that recovery flow (so "Forgot username or password" uses it).

**5. Host Postfix and worker logs**

- On the host, check whether Postfix receives mail from Authentik:
  ```bash
  sudo tail -100 /var/log/mail.log
  ```
- Authentik worker (sends the email):
  ```bash
  docker logs authentik-worker --tail 200 2>&1
  ```
  Look for SMTP or email errors when a user requests a password reset.

**6. Users created by TAK Portal (LDAP)**

- Those users may live in LDAP. Authentik recovery looks up the user and sends to the **email** attribute. If the LDAP user has no email, or it isn't synced into Authentik, no email is sent. In Authentik, open the user (Directory → Users), confirm an email is shown; if not, fix the LDAP attribute or how TAK Portal/Authentik sync it.

---

## Pull dev branch only

```bash
cd ~/infra-TAK && git fetch origin dev && git checkout dev && git pull origin dev
```

*(If your repo lives elsewhere, use that path instead of `~/infra-TAK`, e.g. `~/tak-infra`.)*

---

## Restart console only

```bash
sudo systemctl restart takwerx-console
```

---

## Can't reach console (backdoor 5001 times out)

If **https://YOUR_VPS_IP:5001** never loads (browser says "taking too long" or times out) but the console is running on the server:

1. **Port is 5001** (five-zero-zero-one), not 50001.
2. **During heavy installs** (e.g. TAK Server deploy, unattended-upgrades) the VPS load can spike and the backdoor may be slow or time out — wait a few minutes and retry, or use a second SSH session to check `systemctl status takwerx-console` and `ss -ltn 'sport = :5001'`.
3. **Open the port on the server** (if it wasn't added — e.g. UFW was enabled before start.sh ran):
   ```bash
   sudo ufw allow 5001/tcp
   sudo ufw reload
   sudo ufw status | grep 5001
   ```
4. **Open the port in the cloud** (AWS Security Group, DigitalOcean Firewall, GCP VPC, etc.): add an **inbound** rule for **TCP 5001** from your IP or 0.0.0.0/0.
5. **Confirm the app is listening** (on the VPS):
   ```bash
   ss -ltn 'sport = :5001'
   # Should show LISTEN 0.0.0.0:5001
   curl -k -s -o /dev/null -w "%{http_code}" https://127.0.0.1:5001/
   # Should return 200 or 302
   ```
   If `curl` works but the browser still times out, the block is between your network and the VPS (firewall or ISP).
6. **Try another network** (e.g. phone hotspot) to rule out corporate or home firewall blocking 5001.

---

## Authentik 502 / connection refused (9090) on fresh deploys

If Authentik keeps going unhealthy or Caddy logs `127.0.0.1:9090: connection refused` (502) soon after deploy:

1. **Ensure swap is present** so the server doesn't thrash under load (Guard Dog deploy adds 4GB; if you skipped it, run Guard Dog deploy or create swap manually).
2. **Don't overload the box during first 15–20 minutes** after Authentik deploy — avoid deploying TAK Server, Node-RED, and MediaMTX all at once; space them out.
3. **Check Authentik server container:**
   ```bash
   docker ps -a --filter name=authentik-server
   docker logs authentik-server-1 --tail 100
   ```
   Look for OOM, PostgreSQL connection errors, or repeated restarts.
4. **Restart Authentik if it's stuck:** from the infra-TAK Authentik page use **Restart**, or on the server:
   ```bash
   cd ~/authentik && docker compose restart
   ```
5. **Use the backdoor** (https://VPS_IP:5001) to reach the console when the domain path (Caddy → Authentik) is broken.

---

## TAK client: No channels found

When you scan the QR code and the client connects but says **No channels found** (or "Enable channels" with nothing listed), the server isn’t returning any groups/channels for that user. Common causes:

1. **User has no TAK groups**  
   Channels come from LDAP groups with the `tak_` prefix. The user must be in at least one such group.  
   - In **TAK Portal**: open the user → **Groups** → add a group (e.g. create one like "Field" or use an existing one). Those map to `tak_<name>` in LDAP and become channels.  
   - In **Authentik** (Directory → Users → user → Groups): the user can have `tak_ROLE_ADMIN` or custom `tak_*` groups. TAK Portal–created groups show up here after sync.

2. **Connect LDAP not run**  
   TAK Server must use LDAP for auth and groups. In infra-TAK: **TAK Server** page → **Connect LDAP**. Run it if you haven’t; it patches CoreConfig and creates the webadmin user. Then restart TAK Server.

3. **TAK Server slow or stuck**  
   If the box was under load (e.g. CloudTAK build, low RAM), TAK Server might not answer in time and the client gets an empty list. Restart TAK Server and try again:
   ```bash
   sudo systemctl restart takserver
   ```
   Check resources: `free -h` and `docker stats --no-stream` (if you run Docker services).

4. **CoreConfig has no connections**  
   TAK Server needs at least one Input and one Output in CoreConfig. A fresh install usually has defaults. If you replaced or heavily edited CoreConfig and removed all connections, add them back (or restore a known-good CoreConfig) and restart TAK Server.

5. **New groups not synced yet**  
   TAK Server refreshes group membership from LDAP on an interval (30 seconds with infra-TAK’s default). Right after you add a user or assign groups in TAK Portal, the client may connect before the next refresh and see no channels. **Have the client disconnect and reconnect** (or close and reopen ATAK) after ~30–45 seconds; channels should then appear. No server restart needed.

**Quick sequence:** Ensure the user has a TAK group in TAK Portal → run **Connect LDAP** if needed → if no channels, have the client reconnect after ~30–45 s.

### Why do I get on the server but see no channels?

You create the user and assign groups at the same time; Portal → Authentik sync is nearly instant, so the user and their groups are in LDAP right away. So how can you get on the server (auth OK) but have no channels?

**What happens step by step when you connect:**

1. **Client connects** (e.g. QR scan). TAK Server needs to: (a) decide “is this user allowed on?” and (b) decide “what channels do they get?”

2. **Auth (“are you allowed on?”)**  
   TAK Server does a **direct LDAP check**: “Does this user exist? Bind/lookup.” Your user is already in LDAP (Portal synced them). LDAP says yes → **you get on.** So you’re connected to the server.

3. **Channels (“what do you see?”)**  
   TAK Server does **not** do a fresh “what groups is this user in?” LDAP query on every new connection. It uses an internal **cache**: “user → list of groups.” That cache is filled and refreshed from LDAP on an interval (CoreConfig **`updateinterval`**; infra-TAK sets it to **30** seconds). So when you connect for the first time:
   - You’re a new user; you’re either not in the cache yet, or you’re in the cache with an empty group list from before the next refresh ran.
   - TAK Server answers the client’s “give me my channels” request from that cache → empty list → **no channels** in ATAK even though LDAP has your groups.

4. **After the next refresh or after reconnect**  
   The next refresh runs (every 30 seconds with infra-TAK’s default); TAK Server pulls your group membership from LDAP into the cache. On the next connection (or when the client asks again), it sends the correct channel list.

So you get on because **auth uses a live LDAP check** (user exists → OK). You get no channels because **the channel list comes from a cache that only updates from LDAP on an interval**, so on first connect the cache might not have your groups yet. Two different code paths, one immediate and one on a timer.

**What infra-TAK does:** Connect LDAP sets CoreConfig **`updateinterval="30"`** (30 seconds) so the cache refreshes often and the “no channels” window is usually under 30 seconds. If you already had Connect LDAP run with the old default (60s), run **Connect LDAP** again to apply the 30s interval, then restart TAK Server.

**Why doesn’t the QR code “have” my channels?**  
The QR code only holds connection info (server, port, etc.). It does not contain your channel list. When you scan it, the client connects and asks the server “what channels do I get?” The server does **not** query LDAP at that moment. It answers from its **cache** of “user → groups,” which it refreshes from LDAP every 30 seconds (with infra-TAK’s default). So the first time you connect, the server sends “whatever is in the cache for you” — and that cache entry is often empty until the next refresh. Your channels are already assigned in LDAP; the server just isn’t reading LDAP on your connection, it’s reading the cache. Hence: wait ~30–45 s or reconnect so the cache has been refreshed and the server sends the right list.

**Practical rule:** After creating a user and assigning groups, wait ~30–45 seconds before scanning the QR code, or have the client disconnect and reconnect once; channels will then appear.

---

## Fresh deploy: user groups (avoid "only ROLE_ADMIN")

On a **fresh deployment**, if you create a user, assign two (or more) groups, and after QR scan the client only shows **ROLE_ADMIN**, the usual cause is **order of operations**: the groups did not exist in Authentik when the user was created/synced.

**Required order (nail it down):**

1. **Create TAK groups in TAK Portal first**  
   In TAK Portal, open **Groups** (or the group-management area) and create the groups you will use (e.g. "Field", "MyTeam"). Those become `tak_Field`, `tak_MyTeam` in Authentik/LDAP. Do this **before** creating the first user.

2. **Then create the user and assign groups**  
   Create the user in TAK Portal and assign the groups you created in step 1. TAK Portal syncs the user and their group memberships to Authentik. If the groups already exist, the user gets the correct `tak_*` groups.

3. **Connect LDAP and sync**  
   Run **Connect TAK Server to LDAP** before or after; it does not overwrite non-admin users' groups. After adding or changing groups, wait ~30–45 seconds and have the client **disconnect and reconnect** so TAK Server (30 s LDAP refresh with infra-TAK) sends updated channels.

**Who controls groups:**

- **You control all group membership from TAK Portal.** Create groups there, then create users and assign exactly the groups you choose. infra-TAK does not assign any user to any group except **webadmin** → **tak_ROLE_ADMIN** (for 8446 admin login). No other users are touched; no default or automatic group assignment.
- Authentik deploy / Connect LDAP create only the **tak_ROLE_ADMIN** group in Authentik (used for webadmin). All other TAK groups are created by you in TAK Portal and sync to Authentik.

**If a user still ends up with only ROLE_ADMIN:**

- **Check Authentik first.** Directory → Users → that user → **Groups**. If they already have the right `tak_*` groups there, the problem is the client connection (stale cert or cached membership), not TAK Portal sync. Have them **delete the connection in the TAK client and rescan the QR code** to re-enroll; the new connection will get the correct groups from LDAP.
- If the user’s groups in Authentik are wrong: add the correct `tak_*` groups (e.g. `tak_Field`), remove `tak_ROLE_ADMIN` if they are not an admin. Save, wait ~30–45 s, then have the client reconnect (or delete connection and rescan).
- **Group names**: TAK Server only uses LDAP groups whose `cn` starts with `tak_`. In Authentik, use names like `tak_Field`, `tak_MyTeam`. Names without the `tak_` prefix do not become channels.
- If you created the user **before** creating any groups in TAK Portal, recreate the user's group membership in Authentik as above, or in TAK Portal (and wait for sync), then reconnect the client.

---

## Server impact and memory (full stack)

Quick snapshot of what’s using CPU and RAM. Run on the VPS.

**Memory and swap (one-shot):**
```bash
free -h
```

**Docker containers (CPU %, memory, container name):**
```bash
docker stats --no-stream
```

**Load and top processes (live; quit with `q`):**
```bash
top -o %MEM
```
Or by CPU: `top -o %CPU`.

**Rough breakdown:** TAK Server (Java) and PostgreSQL (Authentik) are usually the heaviest. Authentik (server + worker + postgres), TAK Portal, CloudTAK, Node-RED, and MediaMTX add up. Guard Dog’s 4GB swap helps when load spikes during deploy or many clients.

---

## CloudTAK deploy: long build and “Failed to fetch”

The first CloudTAK deploy builds several Docker images (api, tiles, events) and can take **10–15+ minutes**. The browser polls the deploy log; if the tab is closed, the network drops, or the server is very busy, you may see **“Request failed: Failed to fetch”**. The deploy often **continues on the server**.

- **Don’t click Deploy again** — only one deploy runs at a time; a second click is ignored.
- **Check whether it’s still running:** Open the CloudTAK page again; if it shows “Deployment in progress” and new log lines, it’s still going.
- **Check containers:** `docker ps` (look for `cloudtak-api`, `cloudtak-tiles`, etc.). If they’re up, open the map URL (e.g. `https://map.<your-domain>`) to confirm.
- If the deploy actually failed, fix the cause (e.g. disk space, memory) and run Deploy again.

---

## Disk full / container logs (Node-RED, Authentik, etc.)

If root is 100% full, the cause is often **one huge container log** (e.g. Node-RED 8+ GB). Fix and prevent:

1. **Free space now:** Find and truncate the biggest log (containers keep running):
   ```bash
   sudo du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -hr | head -5
   sudo truncate -s 0 /var/lib/docker/containers/CONTAINER_ID/CONTAINER_ID-json.log
   ```
2. **Prevent it:** Set Docker log limits, then restart Docker:
   ```bash
   cd ~/infra-TAK && sudo ./scripts/set-docker-log-limits.sh
   sudo systemctl restart docker
   ```
   Each container will keep at most 150 MB of logs (3 × 50 MB).

**Full guide:** [docs/DISK-AND-LOGS.md](DISK-AND-LOGS.md) — truncate steps, optional journal/prune, moving Docker to a larger disk at `/mnt`.

---

## Pull then restart console (two steps)

Run the pull, then run the restart (separate lines):

```bash
cd ~/infra-TAK && git fetch origin dev && git checkout dev && git pull origin dev
```

```bash
sudo systemctl restart takwerx-console
```

*(Use your actual clone path if not `~/infra-TAK`.)*

---

## Merge dev → main (selective — release only)

When you want to release a version but **not** put internal/reference files on `main` (no HANDOFF, PROMPT, testing notes, retention PDFs, etc.), merge only the files users need to run, update, or start fresh. Run from repo root (e.g. `~/infra-TAK`).

**Included on main:** app, overlay, start/scripts, static, modules, Guard Dog scripts, user-facing docs (README, COMMANDS, RELEASE, GUARDDOG, DISK-AND-LOGS, MEDIAMTX-TAKPORTAL-ACCESS, WORKFLOW-8446-WEBADMIN, REFERENCES, email template, OpenAPI spec).

**Excluded from main:** `docs/HANDOFF-LDAP-AUTHENTIK.md`, `docs/PROMPT-update-handoff.txt`, `docs/TAK-Data-Retention-notes.md`, `docs/TAK_Server_Configuration_Guide.pdf`, `docs/TAK-Data-Retention-Tool.pdf`, `TESTING.md`, `scripts/ldap-diagnose-and-fix.sh` (and any other internal-only files you add to dev).

```bash
git checkout main
git pull origin main
git checkout dev -- \
  app.py \
  mediamtx_ldap_overlay.py \
  start.sh \
  fix-console-after-pull.sh \
  reset-console-password.sh \
  .gitignore \
  static/ \
  modules/ \
  scripts/set-docker-log-limits.sh \
  scripts/guarddog/ \
  scripts/fix-mediamtx-stream-redirect.sh \
  README.md \
  docs/COMMANDS.md \
  docs/RELEASE-v0.1.9.md \
  docs/GUARDDOG.md \
  docs/DISK-AND-LOGS.md \
  docs/MEDIAMTX-TAKPORTAL-ACCESS.md \
  docs/WORKFLOW-8446-WEBADMIN.md \
  docs/REFERENCES.md \
  docs/email-template-user-created-without-password.html \
  docs/TAK_Server_OpenAPI_v0.json
git add -A && git status
git commit -m "v0.1.9"
git push origin main
git checkout dev
```

**Note:** If a file doesn’t exist on dev (e.g. you removed `scripts/fix-mediamtx-stream-redirect.sh`), drop that line from the `git checkout dev --` list. For a new release, change `docs/RELEASE-v0.1.9.md` to the new release doc and the commit message to the new tag. After pushing, create the tag on main if you use one: `git tag v0.1.9 && git push origin v0.1.9`.

---

## Remove clone and start over

Stops the console, removes the repo directory (and its `.config`), so you can re-clone from scratch. **Replace `~/infra-TAK` with your actual clone path if different.**

```bash
sudo systemctl stop takwerx-console
sudo systemctl disable takwerx-console
rm -rf ~/infra-TAK
cd ~
```

Then run the **Fresh clone** commands above. (`cd ~` is required — after `rm -rf` you're still "in" the deleted dir and clone will fail until you change to a real directory.) If you used a different path (e.g. `~/tak-infra`), use that in the `rm -rf` line instead.
