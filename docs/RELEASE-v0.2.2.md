# infra-TAK v0.2.2-alpha

Release Date: 2026-03-14

---

## Highlights

- **CSRF behind Caddy** — Same-origin check now uses `X-Forwarded-Host` (and `X-Forwarded-Port` when non-standard) so console actions (Update CloudTAK, Apply log limits, etc.) work when accessed through Caddy or another reverse proxy.
- **CloudTAK deploy/update version** — Deploy and Update both use `docker compose build --no-cache` so the running CloudTAK version matches the tag (e.g. v12.103.0) instead of serving a cached older build.
- **CloudTAK deploy log** — Deploy and Update logs now end with an explicit “finished” line so you can tell when restart is complete.
- **Access links after deploy** — CloudTAK Access section (Web UI, Tile Server, Video, Install Dir) is hidden until deploy/update is complete.

---

## CSRF when using console behind Caddy

**Problem:** After the v0.2.1 CSRF baseline, users accessing the console through Caddy (e.g. `https://infratak.yourdomain.com`) saw **403: CSRF validation failed (same-origin required)** when clicking **Update** CloudTAK, **Apply** container log limits, or other POST/PUT/DELETE actions.

**Cause:** The same-origin check compared the request host to `Origin`/`Referer`. Behind a proxy, Flask saw the backend host (e.g. `localhost:5001`) while the browser sent the public host in `Origin`, so the check failed.

**Fix:** The app now derives the “effective” host from **X-Forwarded-Host** (and **X-Forwarded-Port** when not 80/443) when present, so the check uses the host the browser sees. Port normalization treats `host` and `host:443` / `host:80` as the same. Ensure Caddy forwards the Host header (e.g. `header_up Host {host}` and `header_up X-Forwarded-Proto {scheme}` in your reverse_proxy block). See **COMMANDS.md** → “403 CSRF (same-origin) when updating CloudTAK or changing settings”.

---

## CloudTAK deploy and update — version matches tag

**Problem:** Deploy or Update reported “Target: v12.103.0” and checked out that tag, but the running CloudTAK (and Login Settings) still showed an older version (e.g. v12.102.3).

**Cause:** Deploy and Update ran `docker compose build` without `--no-cache`. Docker reused image layers from a previous build (e.g. when 12.102.3 was checked out), so the new tag’s code never made it into the images that were started.

**Fix:** Both **Deploy** (local and remote) and **Update** now run **`docker compose build --no-cache`** before `up -d`. The first build after this change will take longer (often 10–20+ minutes) but the running version will match the tag in the log.

---

## CloudTAK deploy log — “finished” line

Deploy and Update logs now include explicit completion lines:

- After containers are built and started: **✓ Containers built and restarted.** (remote) or **✓ Containers started** and **✓ Restart complete.** (local).
- At the end: **Deploy finished — CloudTAK is running.** (or **Deploy finished — CloudTAK is running and ready.** for local; **Update finished — CloudTAK is running.** for Update).

So you can tell from the log when the restart is done.

---

## CloudTAK Access section

The **Access** block (Web UI, Tile Server, Video, Install Dir) is shown only when CloudTAK is running **and** no deploy/update is in progress. So the links do not appear until the install is complete.

---

## Summary of code/docs changes

| Area | Change |
|------|--------|
| **app.py** | `_effective_request_host()` uses X-Forwarded-Host/Port; `_same_origin_ok()` uses it and normalizes ports. |
| **app.py** | CloudTAK deploy (local + remote) and Update use `build --no-cache`. |
| **app.py** | Deploy/Update log: “Containers built and restarted”, “Restart complete”, “Deploy/Update finished — CloudTAK is running.” |
| **app.py** | Access block gated on `cloudtak.running and not deploying`. |
| **COMMANDS.md** | New section: “403 CSRF (same-origin) when updating CloudTAK or changing settings” with Caddy snippet. |
