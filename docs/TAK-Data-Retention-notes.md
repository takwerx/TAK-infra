# TAK Server Data Retention Tool — notes from official docs

Summary from the Data Retention Tool wiki/PDF for reference when configuring retention or troubleshooting CoT database growth. Canonical source: [Data Retention Tool](https://wiki.tak.gov/display/TPC/Data+Retention+Tool) (Confluence, login may be required).

## Data Retention Policy (Administrative → Data Retention)

- **Data types** with configurable **time-to-live (TTL)**:
  - **CoT (non-chat)** — position/SA and other non-chat CoT
  - **GeoChat** — chat CoT messages
  - **Missions** (structure, tracks, files)
  - **Mission Packages**
  - **Files** — all enterprise sync data that is not mission data
- TTL can be set in **hours, days, weeks, months, years**. Data expires after it exceeds the TTL relative to **creation time**.

## Retention service (when deletes actually run)

- **Deletion is performed by the Retention service**, which runs on a schedule.
- The Retention service can be scheduled at a **fixed date and time** (e.g. once a month at midnight on the 1st).
- **By default: no policies are defined and the Retention service is set to never run.**
- The TAK Server administrator must **define a schedule** so the service runs at a frequency sufficient to meet the minimum TTL in the policies (e.g. if TTL is 1 day, run at least daily or hourly).

So if the CoT database keeps growing, check:

1. **Policies** — TTL is set for the data types you care about (e.g. CoT).
2. **Schedule** — The Retention service is not “never run”; it runs often enough (e.g. hourly for 1-day TTL).

## Auto-expiration (Missions, Mission Packages, Files)

- Optional **expiration** can be set per Mission (Mission Manager → Mission Editor) or per Mission Package/file (Enterprise Sync).
- Expiration is a specific date/time; when reached, data is automatically expired.

## Mission archiving

- Missions can be **archived to disk** after a period of **inactivity** (last content adds, last subscriptions, or both).
- Archived missions are **removed from the database**; they can be **deleted from disk** after an archive-expiration threshold.
- A **cron expression** controls how often the mission-archiving check runs.
- Archived missions can be **restored** from the Mission Archive Entry view.

---

*For PostgreSQL reclaiming disk after deletes (VACUUM), see the TAK Server page in infra-TAK (Database maintenance) and [GUARDDOG.md](GUARDDOG.md) (CoT database size monitor).*
