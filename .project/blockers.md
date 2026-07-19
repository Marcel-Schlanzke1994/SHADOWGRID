# Blockers

No implementation blocker is active.

Local environment limitations detected on 2026-07-19:

- Docker/Docker Compose are not installed. Compose files and container checks are implemented, while local verification uses native processes and SQLite where a container is not required.
- GNU Make is not installed. Every Make target has a PowerShell equivalent.
- Java and Android SDK/ADB are not installed. Expo web/config validation remains available; signed Android/iOS artifacts require the external SDKs and signing accounts described in the release documentation.

These limitations do not authorize external deployment or app-store submission.
