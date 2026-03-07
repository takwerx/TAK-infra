# Guard Dog — How it works

Guard Dog is TAK Server health monitoring and auto-recovery: nine monitors plus an HTTP health endpoint. It runs as systemd timers and a small health service.

## Monitors

| Monitor      | Interval | What it does | On failure |
|-------------|----------|--------------|------------|
| **Port 8089** | 1 min  | Checks TAK Server port 8089 is listening and accepting connections | Auto-restart after 3 consecutive failures |
| **Process**   | 1 min  | Verifies all 5 TAK Server Java processes (messaging, api, config, plugins, retention) | Auto-restart after 3 consecutive failures |
| **Network**   | 1 min  | Pings 1.1.1.1 and 8.8.8.8 | Alert only (no restart) — helps tell network vs server issues |
| **PostgreSQL**| 5 min  | Checks PostgreSQL is running | Attempts restart and sends alert |
| **CoT database size** | 6 hr | Monitors the TAK Server CoT (Cursor on Target) database size | Alert when over 25GB (warning) or 40GB (critical). Retention deletes rows but PostgreSQL does not free disk until **VACUUM**; alert includes tips (retention, tak-db-cleanup.service, VACUUM). |

**How to run VACUUM:** On the **TAK Server** page in the console, use **Database maintenance (CoT)** → **Run VACUUM ANALYZE** (safe while TAK is running). For maximum space reclaim, use **VACUUM FULL** during a maintenance window (it locks tables).

| **OOM**       | 1 min  | Scans TAK Server logs for OutOfMemoryError | Auto-restart and alert (once until log clears) |
| **Disk**      | 1 hr   | Root and TAK logs filesystem usage | Alert at 80% (warning) and 90% (critical) |
| **Certificate**| Daily | Let's Encrypt / TAK Server cert expiry | Alert when **40 days or less** remaining until expiry |
| **Root CA / Intermediate CA** | Escalating | Monitors Root CA and Intermediate CA certificate expiry | First alert at 90 days, then 75, 60, 45, 30, then daily until expiry. Email includes CA name, days remaining, and exact expiry date. |

## Avoiding restart loops and boot races

Guard Dog is designed so that **a restart does not trigger another monitor to restart again in a loop**. Multiple safeguards prevent that:

- **15-minute boot skip**  
  Port 8089, Process, and OOM monitors do not run for the first 15 minutes after boot. That gives TAK Server and PostgreSQL time to start without Guard Dog restarting them during startup.

- **15-minute grace after any restart**  
  After Guard Dog (or anything) restarts TAK Server, no monitor will trigger another restart for 15 minutes. This avoids rapid restart loops.

- **15-minute cooldown between restarts**  
  At most one TAK Server restart per 15 minutes from the 8089 monitor, regardless of how many times the check fails.

- **Restart lock**  
  Only one monitor can perform a restart at a time. Others see the lock and skip, so 8089 and Process (and OOM) never restart in parallel.

- **TAK Server soft start**  
  When Guard Dog is deployed, it installs a systemd drop-in for `takserver.service` so TAK Server starts **after** `network-online.target` and `postgresql.service` (or `postgresql-15.service`). That prevents TAK Server from starting before the network or database are ready, which can cause immediate failure and a restart loop on boot.

- **4GB swap**  
  On deploy, Guard Dog ensures a 4GB swap file exists at `/swapfile` (create if missing, enable and add to `/etc/fstab`). This matches the reference TAK Server Hardening script and helps memory stability under load (reduces OOM risk during spikes).

## Health endpoint

Guard Dog runs a small HTTP service that answers on port 8888 (by default). The path `/health` returns 200 when TAK Server is considered healthy (port 8089 and processes). Use this URL in Uptime Robot or other outside-in monitoring.

## Remote Database — Health Agent red

In **two-server** mode, Guard Dog deploys a small **health agent** on Server One (the DB server) that listens on **port 8080** and serves `/health`. The **Health Agent** monitor (under Remote Database in the UI) is **green** when the console can reach `http://<Server One IP>:8080/health` and it returns 200.

**Why it might be red:**

- **Agent not deployed** — The agent is installed automatically during **two-server step 4 (Deploy Server One)** when an SSH key to Server One is set, so a fresh two-server install gets the agent before Guard Dog is deployed. Guard Dog also deploys the agent when you deploy Guard Dog (if two-server + SSH are configured). If you set up two-server after installing Guard Dog, or SSH failed during step 4 or Guard Dog deploy, the agent may not be there. **Fix:** Use **Deploy health agent to Server One** on the Guard Dog page, or re-deploy Guard Dog.
- **Agent not running on Server One** — On Server One run `systemctl status tak-db-health`. If it’s inactive, run `sudo systemctl start tak-db-health` and `sudo systemctl enable tak-db-health`.
- **Port 8080 not reachable** — Server Two (the console host) must be able to reach Server One:8080. On Server One run `sudo ufw allow 8080/tcp` (or allow from Server Two’s IP only) and ensure nothing else is blocking 8080.
- **Agent returns 503** — The agent returns 200 only when PostgreSQL is ready, the `cot` database exists, and disk usage is under 90%. If any of those fail, it returns 503 and the monitor shows red. Fix PG, the database, or disk on Server One.

**TCP + SSH** (the other Remote Database check) only verifies port 5432 and SSH; it does not run the agent. So TCP + SSH can be green while Health Agent is red if the agent isn’t installed or 8080 isn’t open.

## Alerts

Configure an alert email in the Guard Dog **Notifications** section. Alerts are sent via your Email Relay (e.g. Brevo SMTP) when configured. Optional SMS (Twilio or Brevo) can be set for critical alerts.

## Where to do things (VACUUM, retention, etc.)

| Task | Where | Notes |
|------|--------|------|
| **VACUUM** (reclaim CoT DB disk after retention deletes) | **infra-TAK console → TAK Server** → **Database maintenance (CoT)** | Use **Run VACUUM ANALYZE** (safe while TAK is running). Use **VACUUM FULL** only during a maintenance window (locks tables). |
| **Data retention** (how long to keep CoT data) | **TAK Server's own web UI** (Core Config / Data Retention) | Set TTL and schedule; retention deletes rows but PostgreSQL does not free disk until you run VACUUM. |
| **tak-db-cleanup.service** (if present) | **CLI** | `systemctl status tak-db-cleanup.service`, `sudo journalctl -u tak-db-cleanup.service -f` to see deletion activity. |
| **VACUUM from CLI** | **CLI** | `sudo -u postgres psql -d cot -c 'VACUUM ANALYZE;'` (same as the console button). |
| **Guard Dog activity** (restarts, alerts) | **infra-TAK console → Guard Dog** → **Activity log** | Or on the server: `cat /var/log/takguard/restarts.log`. |

## Scope

Guard Dog monitors **TAK Server** (port 8089, processes, PostgreSQL, CoT DB size, OOM, disk, network, certificate, Root CA / Intermediate CA). When installed, Guard Dog also monitors Authentik, MediaMTX, Node-RED, and CloudTAK (alert and restart on failure). For those, use each module's page for status and the **health endpoint + Uptime Robot** for outside-in checks. Re-deploy Guard Dog to add monitors for services you install later.

## Certificate Rotation Workflow

The Root CA / Intermediate CA monitor is the first step in a rotation workflow:

1. **90 days out** — Guard Dog sends first notification. Go to **TAK Server → Rotate Intermediate CA** to begin rotation.
2. **Rotate** — Creates new Intermediate CA, new server cert, regenerates admin/user certs, keeps old CA in truststore for transition.
3. **Notify users** — At 60 days, notify users to re-enroll via TAK Portal (delete old connection, scan new QR code).
4. **Revoke old CA** — At 30 days, use **Revoke Old CA** on the TAK Server page to remove the old CA from the truststore. Only the new CA is valid.

For **Root CA rotation** (rare, ~10 year cycle): this is a hard cutover. New Root CA, new Intermediate CA, all certs regenerated. All clients must re-enroll. Use **TAK Server → Rotate Root CA** during a planned maintenance window.

## Runbook vs Guard Dog (disk full, Docker logs, etc.)

If you have a **TAK Server VM runbook** (disk full, Docker container logs, PostgreSQL recovery, journal limits), here’s how it maps:

| Runbook “watch for” | In Guard Dog? | Where else |
|--------------------|----------------|------------|
| **Root disk full** | Yes — **Disk** monitor (alert at 80% / 90%) | [DISK-AND-LOGS.md](DISK-AND-LOGS.md): truncate big container logs, set Docker log limits |
| **Docker container logs (e.g. Node-RED 8 GB)** | No — Guard Dog doesn’t truncate or cap logs | One-time: truncate + `scripts/set-docker-log-limits.sh`; see DISK-AND-LOGS.md |
| **PostgreSQL down / recovery** | Yes — **PostgreSQL** monitor + TAK starts *after* Postgres (Guard Dog deploy sets that) | — |
| **TAK Server down (port 8089, processes)** | Yes — **Port 8089**, **Process** monitors (auto-restart after 3 failures) | — |
| **CoT DB size / retention** | Yes — **CoT database size** monitor (alert at 25 GB / 40 GB); VACUUM via TAK Server page | — |
| **OOM in TAK logs** | Yes — **OOM** monitor (scans logs, restart + alert) | — |
| **Authentik / Node-RED / MediaMTX / CloudTAK down** | Yes — service monitors (alert + restart after 3 failures) when those services are installed | — |
| **Journal / APT / Docker build cache** | No | One-time or periodic: journald limit, `apt-get clean`, `docker builder prune`; see runbook or DISK-AND-LOGS.md |

**Do Guard Dog monitors “just have to run”?** Yes. Once Guard Dog is **deployed**, systemd **timers** run the watch scripts on a schedule (every 1 min, 5 min, 1 hr, 6 hr, or daily). You don’t run them by hand; they run automatically. Use the Guard Dog page **Activity log** (or `/var/log/takguard/restarts.log`) to see restarts and alerts.

**Can you add more?** Yes. If you install more services later (e.g. another Docker stack), **re-deploy Guard Dog** and it will enable the matching service monitors (Authentik, Node-RED, MediaMTX, CloudTAK) for whatever is present. To add new *kinds* of checks (e.g. “Docker log size” or “run builder prune”), you’d add a new script and timer in the Guard Dog deploy logic.

## More

- [infra-TAK README](https://github.com/takwerx/infra-TAK) — Quick start, deployment order, backdoor access
- [DISK-AND-LOGS.md](DISK-AND-LOGS.md) — Disk full, container logs, Docker log limits, optional move to /mnt
