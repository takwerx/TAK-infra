# infra-TAK — Copy-paste commands

## Fresh clone on a VPS (dev branch)

```bash
git clone -b dev https://github.com/takwerx/infra-TAK.git
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

**Quick sequence:** Ensure the user has a TAK group in TAK Portal → run **Connect LDAP** if needed → **Restart TAK Server** → scan QR again.

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

## Pull dev and restart console (both)

```bash
cd ~/infra-TAK && git fetch origin dev && git checkout dev && git pull origin dev && sudo systemctl restart takwerx-console
```

*(Same path note: use your actual clone path if not `~/infra-TAK`.)*

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
