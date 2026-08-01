AGENTS.md – SHADOWGRID

Mission

Baue SHADOWGRID als persistentes Multiplayer-Wirtschafts- und Strategiespiel.Die erste Zielplattform ist eine lokal spielbare Webanwendung.Die Architektur muss später ohne grundlegenden Umbau online deploybar sein.

Source of truth

docs/game-design/SHADOWGRID_SPEC.md ist die fachliche Quelle.

docs/architecture/ARCHITECTURE.md ist die technische Quelle.

Datenbankmigrationen sind die Quelle für das physische Datenbankschema.

OpenAPI und Pydantic-Schemas sind die Quelle für API-Verträge.

Bei Widersprüchen nicht raten: Widerspruch dokumentieren und die sicherste,kleinste konsistente Lösung wählen.

Architekturregeln

Modularer Monolith, keine Microservices.

API-Route -> Application Service -> Domain -> Repository/Database.

Keine Geschäftslogik in Flask-Routen oder React-Komponenten.

Kein direktes Ändern von Geld, Aktien oder Eigentum ohne Ledger und Transaktion.

Der Server ist autoritativ.

Clients dürfen keine spielentscheidenden Werte berechnen.

Externe Zustandsänderungen müssen idempotent sein.

Zeitbasierte Verarbeitung muss mehrfach ausführbar sein, ohne doppelte Buchungen.

Keine Floats für Geld, Aktienpreise, Prozentanteile oder Mengen.

Geld in Integer-Cents oder Decimal speichern.

UTC in der Datenbank; Darstellung in Europe/Berlin.

IDs als UUID.

Öffentliche APIs versionieren: /api/v1/....

Datenbankregeln

PostgreSQL ist die primäre Datenbank.

Jede Schemaänderung benötigt eine Migration.

Fremdschlüssel, Unique Constraints und sinnvolle Check Constraints verwenden.

Kritische Handels- und Finanzoperationen mit Transaktionen und Row Locks schützen.

Keine Cascade-Löschung für Finanz- und Auditdaten.

Ledger-, Trade- und Auditdatensätze sind unveränderbar.

Soft Delete nur dort einsetzen, wo fachlich erforderlich.

Security

Niemals Secrets, Tokens, private Schlüssel oder Webhooks committen oder ausgeben.

Keine Secrets aus der Umgebung in Logs schreiben.

Eingaben serverseitig validieren.

Authentisierung, Autorisierung und Ownership getrennt prüfen.

Rate Limits für Auth-, Handels-, PvP- und Admin-Endpunkte.

Sichere Passwort-Hashes verwenden.

CORS restriktiv konfigurieren.

Lokaler Demo-Modus muss in Production automatisch deaktiviert sein.

Keine realen Hacking-, Sabotage- oder Gewaltanleitungen implementieren.

Strategische Störungen bleiben abstrakte Spielaktionen.

Coding standards

Python

Python strict typing.

Ruff, Black und mypy müssen bestehen.

Kleine Funktionen und explizite Rückgabetypen.

Domainfehler als typisierte Exceptions.

Keine except Exception: pass.

Keine naive Datumszeit.

Tests für jede neue Domainregel.

TypeScript

TypeScript strict mode.

Keine any, außer mit dokumentierter Begründung.

API-Typen zentral verwalten.

Serverzustand mit TanStack Query.

Nur UI-Zustand in Zustand.

Formulare mit React Hook Form und Zod.

Barrierearme Komponenten und Tastaturnavigation.

Tests

Nach Backendänderungen mindestens:

make backend-lint

make backend-typecheck

make backend-test

Nach Frontendänderungen mindestens:

make frontend-lint

make frontend-typecheck

make frontend-test

Nach Full-Stack-Änderungen:

make test

relevante Playwright-Szenarien

/review vor Abschluss

Kein Task ist fertig, solange Tests, Migrationen, Seeds, Dokumentation undAkzeptanzkriterien nicht aktualisiert wurden.

Git-Regeln

Kleine, thematisch saubere Commits.

Keine destruktiven Git-Befehle.

Keine bestehenden Nutzeränderungen überschreiben.

Vor Änderungen git status prüfen.

Nach Änderungen Diff prüfen.

Keine generierten Builddateien committen.

Conventional Commits verwenden.

Task-Ausführung

Vor jeder Implementierung:

Repository und relevante Dokumentation lesen.

Bestehende Architektur und Tests verstehen.

Kurzen Implementierungsplan erstellen.

Nur den angeforderten Scope umsetzen.

Tests ausführen.

Diff auf Fehler, Security und ungewollte Änderungen prüfen.

Ergebnis mit geänderten Dateien, Tests und offenen Punkten zusammenfassen.

Definition of Done

Eine Funktion ist nur fertig, wenn:

fachliche Regeln umgesetzt sind,

serverseitige Validierung existiert,

Berechtigungen geprüft werden,

Datenbankconstraints vorhanden sind,

Tests grün sind,

Fehlerzustände sichtbar behandelt werden,

UI Loading/Empty/Error/Success abdeckt,

Dokumentation aktualisiert wurde,

keine Secrets oder Debugreste vorhanden sind.