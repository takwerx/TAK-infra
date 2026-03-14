# Debug: CloudTAK “channels” prompt / constant channel status

When CloudTAK keeps showing the channel-status prompt or “channels thing” repeatedly, the cause is **TAK Server (or CloudTAK backend) polling LDAP very often** (about every 2 seconds) for the same user’s groups. This doc is for debugging and sharing results with upstream (CloudTAK / TAK Server) or your team.

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
