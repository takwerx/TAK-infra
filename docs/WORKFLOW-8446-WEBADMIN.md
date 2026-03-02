# 8446 Webadmin Login — Workflow and Fix

## Normal workflow (Authentik first)

This is the usual order:

1. **Authentik** — deploy first (LDAP provider, outpost, flows). No `webadmin` user yet — TAK Server isn’t installed, so there’s no password in settings.
2. **Email Relay** — deploy (optional; configures Authentik SMTP).
3. **TAK Server** — upload package and deploy. When configuring, you set the **webadmin password** (for the admin UI on port 8446). That password is:
   - Stored in the console’s **settings** (`.config/settings.json` as `webadmin_password`)
   - Used to create the local TAK Server user `webadmin` (UserManager)

   Until you connect to LDAP, **8446** uses that **local** user: log in with **webadmin** and the password you set.

4. **Connect TAK Server to LDAP** — on the TAK Server page, click **“Connect TAK Server to LDAP”**. That:
   - Patches CoreConfig so 8446 uses **LDAP** (Authentik) instead of the local user store
   - **Creates** the `webadmin` user in Authentik (it didn’t exist at Authentik deploy time) and **sets its password** from settings (your deploy password)
   - Ensures LDAP service account and flow are in place

   After this, **8446 login is checked against Authentik/LDAP**. The password that works is the one **in Authentik** for `webadmin` — which was just set from your deploy password.

**Result:** Use **webadmin** + the **same** password you set at TAK Server deploy to log in to 8446.

---

## Edge case: TAK Server first, then add Authentik

You already had TAK Server (with webadmin password in settings). Now you deploy Authentik and want 8446 to use LDAP.

- When **Authentik** deploys, `/opt/tak` exists and settings already have `webadmin_password`. The Authentik deploy step can create `webadmin` in Authentik and set the password from settings at that time.
- When you click **“Connect TAK Server to LDAP”**, CoreConfig is patched for LDAP and the console ensures `webadmin` in Authentik exists and has the password from settings (create or update).

So the same outcome: **webadmin** + deploy password works on 8446 after you connect LDAP.

---

## If you can’t log in to 8446 with webadmin

If 8446 says “invalid password” even though you’re using the password you set at TAK Server deploy:

1. **Use “Sync webadmin to Authentik”**  
   On the **TAK Server** page, when LDAP is connected and Authentik is deployed, you’ll see the green **“LDAP Connected to Authentik”** card with **“Sync webadmin to Authentik”**. Click it. That reads `webadmin_password` from settings and sets it on the **webadmin** user in Authentik (create/update + set password). No SSH needed.

2. **Try 8446 again** with **webadmin** and the **same** password you set at TAK Server deployment.

3. **If it still fails**  
   Try a private/incognito window, type the password manually (no autocomplete), and ensure special characters (e.g. `#`) match exactly. If you changed the password only in Authentik, run **Sync webadmin to Authentik** again so Authentik matches settings, then try 8446 with that password.

---

## Summary

| Step | What happens |
|------|----------------|
| Deploy Authentik | LDAP provider/outpost and flows. No webadmin yet (TAK Server not installed). |
| Deploy TAK Server | You set webadmin password → saved to settings + local TAK user. 8446 uses local auth until LDAP connected. |
| Click “Connect TAK Server to LDAP” | CoreConfig patched for LDAP; **webadmin created in Authentik** and password set from settings. 8446 now uses LDAP. |
| 8446 login fails | Click **“Sync webadmin to Authentik”** (TAK Server page, when LDAP connected). Then try webadmin + deploy password again. |

**Edge case (TAK Server first):** You deploy Authentik later. Authentik deploy can create webadmin from settings if `/opt/tak` exists. “Connect TAK Server to LDAP” still ensures webadmin exists and password is set from settings.
