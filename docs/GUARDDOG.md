# Guard Dog — How it works

Guard Dog is TAK Server health monitoring and auto-recovery: eight monitors plus an HTTP health endpoint. It runs as systemd timers and a small health service.

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

## Health endpoint

Guard Dog runs a small HTTP service that answers on port 8888 (by default). The path `/health` returns 200 when TAK Server is considered healthy (port 8089 and processes). Use this URL in Uptime Robot or other outside-in monitoring.

## Alerts

Configure an alert email in the Guard Dog **Notifications** section. Alerts are sent via your Email Relay (e.g. Brevo SMTP) when configured. Optional SMS (Twilio or Brevo) can be set for critical alerts.

## Where to do things (VACUUM, retention, etc.)

| Task | Where | Notes |
|------|--------|------|
| **VACUUM** (reclaim CoT DB disk after retention deletes) | **infra-TAK console → TAK Server** → **Database maintenance (CoT)** | Use **Run VACUUM ANALYZE** (safe while TAK is running). Use **VACUUM FULL** only during a maintenance window (locks tables). |
| **Data retention** (how long to keep CoT data) | **TAK Server’s own web UI** (Core Config / Data Retention) | Set TTL and schedule; retention deletes rows but PostgreSQL does not free disk until you run VACUUM. |
| **tak-db-cleanup.service** (if present) | **CLI** | `systemctl status tak-db-cleanup.service`, `sudo journalctl -u tak-db-cleanup.service -f` to see deletion activity. |
| **VACUUM from CLI** | **CLI** | `sudo -u postgres psql -d cot -c 'VACUUM ANALYZE;'` (same as the console button). |
| **Guard Dog activity** (restarts, alerts) | **infra-TAK console → Guard Dog** → **Activity log** | Or on the server: `cat /var/log/takguard/restarts.log`. |

## Scope

Guard Dog monitors **TAK Server** (port 8089, processes, PostgreSQL, CoT DB size, OOM, disk, network, certificate). When those are installed, Guard Dog also monitors Authentik, MediaMTX, Node-RED, and CloudTAK (alert and restart on failure). For those, use each module’s page for status and the **health endpoint + Uptime Robot** for outside-in checks. Re-deploy Guard Dog to add monitors for services you install later. Optional monitors for other services (e.g. “if MediaMTX is installed, check its port or systemd unit”) could be added in a future release.

## More

- [infra-TAK README](https://github.com/takwerx/infra-TAK) — Quick start, deployment order, backdoor access
