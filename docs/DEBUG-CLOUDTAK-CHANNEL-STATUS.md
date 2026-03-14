# Debug: CloudTAK “channels” prompt / constant channel status

When CloudTAK keeps showing the channel-status prompt or “channels thing” repeatedly, the cause is **TAK Server (or CloudTAK backend) polling LDAP very often** (about every 2 seconds) for the same user’s groups. This doc is for debugging and sharing results with upstream (CloudTAK / TAK Server) or your team.

---

## 0. Narrative: what’s going on and how we tested

**What’s going on:** TAK Server is making constant LDAP calls (bind + search for `memberOf` and `ntUserWorkstations`) about every 2 seconds for certain users (admin, webadmin). When an admin or webadmin user has CloudTAK open, that same loop shows up in the UI as the repeated “channels” prompt. The calls are coming from TAK Server (client `172.18.0.1` → Authentik LDAP), not from CloudTAK or from end-user clients.

**How we tested:**

1. **LDAP log:** We ran `docker compose logs -f ldap` on the Authentik host and watched bind+search traffic. The pattern is always the same: bind as `adm_ldapservice`, then search for a user (e.g. `cn=admin` or `cn=webadmin`) with attributes `memberOf` and `ntUserWorkstations`, repeating every ~2 seconds.

2. **CloudTAK stopped, no clients:** We stopped CloudTAK completely from the infra-TAK console (containers down). We kept the LDAP log running. The constant bind+search traffic **did not stop**—it continued at the same rate. TAK Server reported no connected clients. So the constant calls are **not** driven by CloudTAK or by anyone being logged in; they are driven by **TAK Server’s own logic** (e.g. an internal refresh or sync for admin/webadmin).

3. **Admin vs normal user:** With CloudTAK running again, we logged in as a normal user (aj2cacor) only. No “channels” spam in that session. The LDAP log still showed continuous polling for **cn=admin** (and webadmin), and only occasional lookups for **cn=aj2cacor** (e.g. at login). When we logged in as admin, the channels prompt spammed again. So the **UI spam** is tied to having an admin (or webadmin) session in CloudTAK; the **LDAP polling** for admin/webadmin is something TAK Server does on a timer regardless of who is actually using CloudTAK.

**What we found:**

- The constant LDAP calls happen **even with CloudTAK shut down and no clients connected** to TAK Server. So it’s TAK Server’s own background behavior.
- The “channels” prompt in the browser only goes crazy when an **admin or webadmin** is logged into CloudTAK; a normal user (e.g. aj2cacor) does not see that spam.
- LDAP polling for admin/webadmin runs on a timer in TAK Server regardless of who is using CloudTAK; the UI spam is tied to having an admin or webadmin session open.

**What we ruled out:**

- **CloudTAK** as the source of the constant calls: with CloudTAK stopped, the LDAP traffic continued at the same rate.
- **Connected clients** as the source: with no clients connected to TAK Server, the LDAP traffic continued.
- So the constant calls are driven by **TAK Server’s own logic**, not by CloudTAK or by anyone being logged in.

---

## 1. Confirm the pattern (LDAP traffic)

On the host where **CloudTAK, Authentik, and TAK Server** run (Server Two in two-server mode):

**Terminal 1 — LDAP outpost (TAK Server → Authentik LDAP):**

```bash
cd ~/authentik && docker compose logs -f ldap --tail=0
```

**Reproduce:** Open CloudTAK in the browser, log in if needed, use it until the channel prompt appears (or let it run ~60 seconds). Watch Terminal 1.

**What you’re looking for:**

- Repeated **Bind request** (as `adm_ldapservice`) followed by **Search request** for the same user (e.g. `cn=admin`, `baseDN`, `memberOf`).
- If that bind+search pair repeats **every ~2 seconds** while CloudTAK is open, that’s the loop that matches the “constant channel status” behavior.

**Optional — TAK Server logs (connection/channel activity):**

```bash
sudo journalctl -u takserver -f -n 0
```

Run this in a second terminal while you reproduce. Look for connection/channel or LDAP-related lines in the same time window as the LDAP burst.

---

## 1b. Is it CloudTAK? (Stop test)

With the LDAP log running (Terminal 1 above), use the **CloudTAK** module page in the infra-TAK console and click **■ Stop**. Keep watching the LDAP log.

- **If the bind+search traffic stops** → CloudTAK (or its backend) is driving those lookups.
- **If it keeps going** → something else is (e.g. TAK Server on its own, or another client like 8446 / another tab).

When you’re done testing, start CloudTAK again from the same page (**▶ Start**).

---

## 1c. Findings (observed)

- **CloudTAK stopped:** With CloudTAK containers stopped via the infra-TAK console, the LDAP bind+search traffic (same user, `memberOf` / `ntUserWorkstations`) continued at the same rate from client `172.18.0.1`.
- **No clients connected:** TAK Server showed no connected clients during that period.
- **Conclusion:** The LDAP lookups are driven by **TAK Server’s own logic** (e.g. an internal refresh or sync), not by CloudTAK and not by connected TAK clients.
- **Admin vs normal user:** With only a normal user (e.g. aj2cacor) logged into CloudTAK, the “channels” prompt does not spam; the LDAP log still shows continuous polling for **cn=admin** and **cn=webadmin**. The UI spam is tied to having an admin or webadmin session open.

---

## 2. What this means

- **Direction:** Traffic is **TAK Server → LDAP** (port 389). Authentik/LDAP is not calling TAK Server.
- **Cause:** Something in the TAK Server or CloudTAK path is doing an LDAP lookup for the user’s groups/attributes on a very short interval (e.g. every 2 s) instead of using a cache or a longer refresh.
- **Fix:** The change needs to be in **TAK Server or CloudTAK** (e.g. throttle or cache these LDAP lookups for channel/connection checks). Authentik/LDAP config on its own does not fix it.

See **docs/TAK-SERVER-LDAP-BEHAVIOR.md** for the observed pattern and **docs/COMMANDS.md** → “Diagnose CloudTAK channel status” for the full flow.

---

## 3. Workarounds to try

- **Resync LDAP** (TAK Server page → LDAP card → “Resync LDAP to TAK Server”). Sometimes reduces the issue temporarily.
- **Authentik → Update config & reconnect** (Authentik page → Update). Same: temporary improvement reported in some setups.
- **One CloudTAK tab:** Avoid many open tabs/sessions for the same user; can reduce load and sometimes makes the prompt less frequent.
- If you see **504 / “Unexpected token '<'”** in the browser console, Caddy is timing out while waiting for the backend; we increased map timeouts (120 s). If it still happens, note the failing request URL and share with your host or infra-TAK.

---

## 4. Reporting upstream

When reporting to **CloudTAK** or **TAK Server**:

1. Say you see the **channel status / “channels” prompt repeatedly** when using CloudTAK (and optionally 8446).
2. Attach or describe:
   - A short **LDAP outpost log** (1–2 minutes) while reproducing: `cd ~/authentik && docker compose logs ldap --tail=200` (after reproducing).
   - That **bind+search for the same user repeats every ~2 seconds** while the client is active.
3. Point to **TAK Server → Authentik LDAP** (outpost on 389); traffic is TAK Server → LDAP, not the other way around.
4. Ask if they can **throttle or cache** LDAP lookups used for channel/connection status so the prompt stops repeating.

---

## 5. infra-TAK side

- **Connect LDAP** sets CoreConfig `updateinterval="30"` (group cache refresh from LDAP every 30 s). That does not stop the ~2 s loop, which appears to be a separate code path (e.g. per-request or per-connection checks).
- No infra-TAK config change is known to remove the constant prompt; the fix is in TAK Server or CloudTAK.
