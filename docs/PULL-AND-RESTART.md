# Pull current branch and restart console

Run line 1, wait for it to finish, then run line 2.

```bash
cd /root/infra-TAK && git pull --ff-only
```

```bash
sudo systemctl restart takwerx-console
```

*(Repo not in /root/infra-TAK? Use your path in line 1.)*

---

**One-liner with 5s delay:** `cd /root/infra-TAK && git pull --ff-only && sleep 5 && sudo systemctl restart takwerx-console`

More: **docs/COMMANDS.md**
