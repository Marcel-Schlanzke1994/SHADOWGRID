# Blockers

No implementation or Railway browser/API deployment blocker is active.

External provider inputs still required for optional release channels:

- Transactional registration, verification and password-reset delivery needs a real SMTP host, sender, username/password and TLS mode. The implementation and retrying outbox worker are live, but no provider credentials were supplied.
- Signed Android/iOS artifacts need EAS, Google Play and Apple signing accounts plus real-device validation. Java and Android SDK/ADB are not installed on this host.

Local Docker/Docker Compose and GNU Make are absent. Equivalent project scripts are available, and container behavior is verified by GitHub Actions and the successful Railway deployment.
