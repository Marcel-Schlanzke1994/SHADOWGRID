# Store data-safety draft

- Account data: email and display name, collected for authentication/account management, not sold.
- App activity: game actions and organization membership, required for core functionality, not sold.
- Diagnostics: server request IDs and security audit events; no third-party advertising analytics in launch scope.
- Security: transport encryption is required in production; refresh credentials use platform secure storage.
- Deletion/export: exposed in Settings and backed by `/privacy/export` and `/privacy/account`.

This is an engineering draft. Legal/privacy owners must verify it against deployed processors and the final store questionnaire before submission.
