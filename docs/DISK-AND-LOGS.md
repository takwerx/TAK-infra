# Disk full / container logs (Node-RED, Authentik, etc.)

If your infra-TAK server runs out of disk space (root 100% full), the cause is often **unbounded Docker container logs**, especially Node-RED and Authentik LDAP. This doc explains what’s going on and how to fix it and prevent it.

---

## Why the disk fills

- **Root filesystem** (e.g. 30 GB) gets to **100%** → apps (and databases) can’t write, things break.
- **Main cause:** a single container’s log file grows to many GB. Common culprits:
  - **Node-RED** — can reach **8+ GB** if left unchecked.
  - **Authentik LDAP** — can reach hundreds of MB.
- **Other contributors:** Docker images, build cache, systemd journal, APT cache. After fixing logs, these are optional cleanups.

---

## 1. Free space immediately (truncate the big log)

Find the largest container log and truncate it. Containers keep running.

```bash
# Find the biggest container log
sudo du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -hr | head -5

# Truncate the biggest one (replace CONTAINER_ID with the long hex dir name from the path)
sudo truncate -s 0 /var/lib/docker/containers/CONTAINER_ID/CONTAINER_ID-json.log
```

Example: if Node-RED’s log is at  
`/var/lib/docker/containers/9bbf1ff4bae6.../9bbf1ff4bae6...-json.log`:

```bash
sudo truncate -s 0 /var/lib/docker/containers/9bbf1ff4bae6e1a6a0120f8b74b5638b23b0554d68555cb5a8b3567e1863d871/9bbf1ff4bae6e1a6a0120f8b74b5638b23b0554d68555cb5a8b3567e1863d871-json.log
```

Check space:

```bash
df -h /
```

---

## 2. Prevent logs from growing again (Docker log limits)

Set a **max size and rotation** for all container logs so no single log can fill the disk.

**Option A — use the script (recommended):**

```bash
cd /path/to/infra-TAK
sudo ./scripts/set-docker-log-limits.sh
```

Then restart Docker (containers will restart):

```bash
sudo systemctl restart docker
```

**Option B — do it manually:**

Create or edit `/etc/docker/daemon.json` (merge with existing keys if the file already exists):

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
```

Then:

```bash
sudo systemctl restart docker
```

Effect: each container keeps at most **3 × 50 MB = 150 MB** of logs. Existing huge logs are not shrunk until you truncate them (step 1); new growth is capped.

---

## 3. Optional: more one-time cleanup

- **Systemd journal** (can be hundreds of MB):
  ```bash
  sudo journalctl --vacuum-size=100M
  ```
  To cap it permanently: create `/etc/systemd/journald.conf.d/size-limit.conf` with:
  ```ini
  [Journal]
  SystemMaxUse=100M
  SystemMaxFileSize=20M
  ```
  Then `sudo systemctl restart systemd-journald`.

- **Docker build cache:**
  ```bash
  sudo docker builder prune -f
  ```

- **Unused images/containers** (only if you’re OK re-pulling images later):
  ```bash
  sudo docker system prune -a
  ```

---

## 4. Longer-term: use a bigger disk (e.g. /mnt)

If you have a separate disk at `/mnt` (e.g. 63 GB) and root is small, you can move Docker’s data root there so images, containers, and logs use the larger disk.

1. Stop Docker: `sudo systemctl stop docker`
2. Move data: `sudo mv /var/lib/docker /mnt/docker`
3. Symlink: `sudo ln -s /mnt/docker /var/lib/docker`
4. Or set `"data-root": "/mnt/docker"` in `/etc/docker/daemon.json` and remove the symlink.
5. Start Docker: `sudo systemctl start docker`

Containers will need to be started again (e.g. Authentik: `cd ~/authentik && docker compose up -d`). Do this in a maintenance window.

---

## Summary

| Problem              | Action                                              |
|----------------------|-----------------------------------------------------|
| Disk 100% full       | Truncate the largest container log (step 1)         |
| Logs growing again   | Set Docker log limits (step 2), restart Docker      |
| Need more space      | Optional: journal vacuum, docker prune (step 3)     |
| Root disk too small  | Optional: move Docker data-root to /mnt (step 4)    |

**Automatic in infra-TAK:** When you deploy any **Docker-based** module from the console (**Authentik**, **Node-RED**, **TAK Portal**, **CloudTAK**), the app ensures Docker log limits are set (and restarts Docker once if needed). So every container is capped from the first run. MediaMTX is systemd, not Docker, so it doesn’t use Docker logs. If you already had Docker running before this behaviour existed, run `scripts/set-docker-log-limits.sh` and restart Docker once to apply limits to existing containers.
