# References

Canonical links used when working on infra-TAK. Keep these so tooling and docs always point to the right sources.

## TAK Server

- **TAK Server API (Redoc)**  
  https://docs.tak.gov/api/takserver  
  Official API reference for TAK Server (endpoints, request/response shapes). Use when implementing or debugging TAK Server integration (e.g. CoreConfig, Marti API, certificates, retention).

- **TAK Server Configuration Guide (PDF)**  
  [docs/TAK_Server_Configuration_Guide.pdf](TAK_Server_Configuration_Guide.pdf)  
  In-repo copy (v5.6, Dec 2025). Use when configuring or troubleshooting TAK Server. **Ch. 19 Data Retention Tool** points to the wiki (below) for retention behavior and settings.

- **Data Retention Tool (tak.gov wiki)**  
  https://wiki.tak.gov/display/TPC/Data+Retention+Tool  
  Official docs (Confluence; login may be required). Use when deciding retention policy or troubleshooting CoT database growth.

- **Data Retention Tool — in-repo notes**  
  [docs/TAK-Data-Retention-notes.md](TAK-Data-Retention-notes.md)  
  Summary from the official Data Retention Tool docs: policy types, TTL, **Retention service schedule** (default: never run), mission archiving. Use when configuring retention or debugging CoT DB growth.

- **Data Retention Tool (PDF export)**  
  [docs/TAK-Data-Retention-Tool.pdf](TAK-Data-Retention-Tool.pdf)  
  In-repo copy of the Confluence export for offline reference.

### CoT database filling up (reference for decisions)

- **From the Configuration Guide:** Retention is documented in Ch. 19 and delegated to the [Data Retention Tool](https://wiki.tak.gov/display/TPC/Data+Retention+Tool) wiki. The guide does not describe PostgreSQL disk reclaim (VACUUM) or `tak-db-cleanup.service`.
- **infra-TAK strategy (aligned with community):** Guard Dog monitors CoT DB size (alert at 25GB / 40GB); TAK Server page offers **VACUUM ANALYZE** and **VACUUM FULL** (PostgreSQL does not free disk until VACUUM). Alert text and [docs/GUARDDOG.md](GUARDDOG.md) mention: Data Retention in Web UI, retention process / `tak-db-cleanup.service`, and VACUUM. When making changes to monitoring or copy, prefer the wiki for retention behavior and the Configuration Guide for overall TAK Server config.

---

*Add more sections (Authentik, Caddy, etc.) as needed.*
