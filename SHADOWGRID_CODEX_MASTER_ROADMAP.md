SHADOWGRID – Codex Master-Roadmap

Version: 1.0Ziel: Eine vollständige, lokal spielbare Webversion von SHADOWGRID, die mit Codex schrittweise, testbar und ohne Architekturbruch umgesetzt wird.

0. Zielzustand

Nach Abschluss dieser Roadmap gilt:

Ein frischer Klon startet lokal mit einem einzigen Bootstrap-Befehl.

Frontend, Backend, PostgreSQL, Redis, Worker und Scheduler laufen über Docker Compose.

Der Spieler kann sich registrieren oder einen lokalen Demoaccount verwenden.

Der Spieler wählt Köln als Startstadt.

Er gründet ein Unternehmen, stellt Spezialisten ein, kauft Ausbauten und erhält Wirtschaftsberichte.

Mehrere lokale KI-Spieler konkurrieren im gleichen Markt.

Marktanteile, Nachfrage, Umsätze, Kosten, Gewinne und Unternehmenswerte verändern sich.

Unternehmen können an die Ingame-Börse gehen.

Spieler können Markt- und Limitaufträge erstellen, Aktien handeln und Dividenden erhalten.

Spieler können Kartelle gründen, Rollen vergeben, Kartellprojekte finanzieren und Bezirke beeinflussen.

Informationsberichte und abstrakte strategische PvP-Aktionen sind spielbar.

Weltereignisse wirken auf Städte und Branchen.

Eine Saison, Ranglisten und Hall of Fame funktionieren.

Alle Geld- und Aktienbewegungen sind über ein unveränderbares Ledger nachvollziehbar.

Kritische Spielaktionen sind transaktional, idempotent und gegen Doppelausführung geschützt.

Unit-, Integrations-, API- und End-to-End-Tests laufen lokal.

Das Spiel besitzt Seed-Daten, Demoaccounts und einen reproduzierbaren Demo-Spielstand.

Die Benutzeroberfläche folgt einem Cyber-/Shadow-/Gold-Design.

Es existieren Dokumentation, Datenbankschema, API-Dokumentation und Betriebsanleitung.

Diese Roadmap zielt auf eine robuste erste Vollversion. Kein Entwicklungsplan kann Fehlerfreiheit garantieren. Deshalb sind Tests, Reviews, Datenbanktransaktionen, Backups und feste Abnahmekriterien Bestandteil jeder Phase.

1. Verbindliche Architekturentscheidung

1.1 Gesamtarchitektur

Verwende einen modularen Monolithen.

React-Frontend
      |
      | REST + Socket.IO
      v
Flask API / Game Server
      |
      +---- PostgreSQL
      |
      +---- Redis
      |
      +---- Celery Worker
      |
      +---- Celery Beat Scheduler

Keine Microservices in Version 1.

1.2 Technologiestack

Backend

Python 3.13

Flask

Flask-SQLAlchemy

SQLAlchemy 2

Alembic / Flask-Migrate

Flask-JWT-Extended

Flask-SocketIO

Pydantic für Request- und Responsevalidierung

Celery

Redis

PostgreSQL

Gunicorn für späteren Produktivbetrieb

Frontend

React

TypeScript

Vite

React Router

TanStack Query

Zustand

Socket.IO Client

React Hook Form

Zod

Recharts

Tailwind CSS

Vitest

Playwright

Qualität

Ruff

Black

mypy

pytest

pytest-cov

ESLint

Prettier

TypeScript strict mode

pre-commit

GitHub Actions

Lokaler Betrieb

Windows mit WSL2

Docker Desktop

Docker Compose

VS Code mit WSL-Erweiterung

Codex CLI oder Codex in der ChatGPT-Desktop-App

2. Sicherheitsmaßnahme vor dem ersten Commit

Vor Beginn:

Alle jemals in Chats, Screenshots, Dokumenten oder Repositories offengelegten API-Schlüssel, GitHub-Tokens, Discord-Tokens, Webhooks und Client-Secrets widerrufen und neu erzeugen.

Keine echten Geheimnisse in .env.example, README.md, AGENTS.md, Prompts oder Seed-Dateien schreiben.

.env und alle lokalen Secret-Dateien in .gitignore aufnehmen.

Für lokale Entwicklung ausschließlich neue Development-Secrets verwenden.

Git-Historie auf bereits eingecheckte Secrets prüfen.

Automatischen Secret-Scan in CI aktivieren.

Codex niemals mit unbeschränktem Systemzugriff starten.

Destruktive Git-Befehle, Datenbanklöschungen und Secret-Zugriffe nur nach expliziter Freigabe zulassen.

3. Lokale Entwicklungsumgebung unter Windows

3.1 WSL2 installieren

PowerShell als Administrator:

wsl --install
wsl --update

Danach Windows neu starten und Ubuntu öffnen.

3.2 Grundwerkzeuge in WSL installieren

sudo apt update
sudo apt install -y git curl make ca-certificates build-essential

Docker Desktop installieren und die WSL-Integration für Ubuntu aktivieren.

3.3 Projekt immer im Linux-Dateisystem speichern

mkdir -p ~/code
cd ~/code
mkdir shadowgrid
cd shadowgrid
git init

Nicht unter /mnt/c/... entwickeln.

3.4 Codex installieren

curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex

Beim ersten Start mit dem ChatGPT-Konto anmelden.

3.5 Empfohlener Codex-Modus

codex --sandbox workspace-write --ask-for-approval on-request

Nicht verwenden:

codex --yolo
codex --dangerously-bypass-approvals-and-sandbox

4. Zielstruktur des Repositorys

shadowgrid/
├── AGENTS.md
├── README.md
├── LICENSE
├── Makefile
├── compose.yaml
├── .env.example
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── api/
│   │   └── factories/
│   └── src/
│       └── shadowgrid/
│           ├── __init__.py
│           ├── app.py
│           ├── config.py
│           ├── extensions.py
│           ├── errors.py
│           ├── logging.py
│           ├── auth/
│           ├── players/
│           ├── cities/
│           ├── companies/
│           ├── economy/
│           ├── specialists/
│           ├── exchange/
│           ├── cartels/
│           ├── influence/
│           ├── intelligence/
│           ├── events/
│           ├── seasons/
│           ├── ledger/
│           ├── notifications/
│           ├── admin/
│           ├── jobs/
│           └── cli/
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── playwright.config.ts
│   ├── tests/
│   └── src/
│       ├── app/
│       ├── api/
│       ├── components/
│       ├── features/
│       ├── layouts/
│       ├── pages/
│       ├── stores/
│       ├── styles/
│       ├── types/
│       └── test/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── game-design/
│   ├── operations/
│   ├── security/
│   └── adr/
│
├── scripts/
│   ├── bootstrap.sh
│   ├── dev.sh
│   ├── reset-local.sh
│   ├── test-all.sh
│   ├── seed-demo.sh
│   └── backup-local.sh
│
└── .github/
    └── workflows/
        ├── backend-ci.yml
        ├── frontend-ci.yml
        ├── e2e.yml
        └── security.yml

5. Root-AGENTS.md für Codex

Diese Datei wird vor der ersten Entwicklungsaufgabe angelegt.

# AGENTS.md – SHADOWGRID

## Mission

Baue SHADOWGRID als persistentes Multiplayer-Wirtschafts- und Strategiespiel.
Die erste Zielplattform ist eine lokal spielbare Webanwendung.
Die Architektur muss später ohne grundlegenden Umbau online deploybar sein.

## Source of truth

- `docs/game-design/SHADOWGRID_SPEC.md` ist die fachliche Quelle.
- `docs/architecture/ARCHITECTURE.md` ist die technische Quelle.
- Datenbankmigrationen sind die Quelle für das physische Datenbankschema.
- OpenAPI und Pydantic-Schemas sind die Quelle für API-Verträge.
- Bei Widersprüchen nicht raten: Widerspruch dokumentieren und die sicherste,
  kleinste konsistente Lösung wählen.

## Architekturregeln

- Modularer Monolith, keine Microservices.
- API-Route -> Application Service -> Domain -> Repository/Database.
- Keine Geschäftslogik in Flask-Routen oder React-Komponenten.
- Kein direktes Ändern von Geld, Aktien oder Eigentum ohne Ledger und Transaktion.
- Der Server ist autoritativ.
- Clients dürfen keine spielentscheidenden Werte berechnen.
- Externe Zustandsänderungen müssen idempotent sein.
- Zeitbasierte Verarbeitung muss mehrfach ausführbar sein, ohne doppelte Buchungen.
- Keine Floats für Geld, Aktienpreise, Prozentanteile oder Mengen.
- Geld in Integer-Cents oder Decimal speichern.
- UTC in der Datenbank; Darstellung in Europe/Berlin.
- IDs als UUID.
- Öffentliche APIs versionieren: `/api/v1/...`.

## Datenbankregeln

- PostgreSQL ist die primäre Datenbank.
- Jede Schemaänderung benötigt eine Migration.
- Fremdschlüssel, Unique Constraints und sinnvolle Check Constraints verwenden.
- Kritische Handels- und Finanzoperationen mit Transaktionen und Row Locks schützen.
- Keine Cascade-Löschung für Finanz- und Auditdaten.
- Ledger-, Trade- und Auditdatensätze sind unveränderbar.
- Soft Delete nur dort einsetzen, wo fachlich erforderlich.

## Security

- Niemals Secrets, Tokens, private Schlüssel oder Webhooks committen oder ausgeben.
- Keine Secrets aus der Umgebung in Logs schreiben.
- Eingaben serverseitig validieren.
- Authentisierung, Autorisierung und Ownership getrennt prüfen.
- Rate Limits für Auth-, Handels-, PvP- und Admin-Endpunkte.
- Sichere Passwort-Hashes verwenden.
- CORS restriktiv konfigurieren.
- Lokaler Demo-Modus muss in Production automatisch deaktiviert sein.
- Keine realen Hacking-, Sabotage- oder Gewaltanleitungen implementieren.
- Strategische Störungen bleiben abstrakte Spielaktionen.

## Coding standards

### Python

- Python strict typing.
- Ruff, Black und mypy müssen bestehen.
- Kleine Funktionen und explizite Rückgabetypen.
- Domainfehler als typisierte Exceptions.
- Keine `except Exception: pass`.
- Keine naive Datumszeit.
- Tests für jede neue Domainregel.

### TypeScript

- TypeScript strict mode.
- Keine `any`, außer mit dokumentierter Begründung.
- API-Typen zentral verwalten.
- Serverzustand mit TanStack Query.
- Nur UI-Zustand in Zustand.
- Formulare mit React Hook Form und Zod.
- Barrierearme Komponenten und Tastaturnavigation.

## Tests

Nach Backendänderungen mindestens:

- `make backend-lint`
- `make backend-typecheck`
- `make backend-test`

Nach Frontendänderungen mindestens:

- `make frontend-lint`
- `make frontend-typecheck`
- `make frontend-test`

Nach Full-Stack-Änderungen:

- `make test`
- relevante Playwright-Szenarien
- `/review` vor Abschluss

Kein Task ist fertig, solange Tests, Migrationen, Seeds, Dokumentation und
Akzeptanzkriterien nicht aktualisiert wurden.

## Git-Regeln

- Kleine, thematisch saubere Commits.
- Keine destruktiven Git-Befehle.
- Keine bestehenden Nutzeränderungen überschreiben.
- Vor Änderungen `git status` prüfen.
- Nach Änderungen Diff prüfen.
- Keine generierten Builddateien committen.
- Conventional Commits verwenden.

## Task-Ausführung

Vor jeder Implementierung:

1. Repository und relevante Dokumentation lesen.
2. Bestehende Architektur und Tests verstehen.
3. Kurzen Implementierungsplan erstellen.
4. Nur den angeforderten Scope umsetzen.
5. Tests ausführen.
6. Diff auf Fehler, Security und ungewollte Änderungen prüfen.
7. Ergebnis mit geänderten Dateien, Tests und offenen Punkten zusammenfassen.

## Definition of Done

Eine Funktion ist nur fertig, wenn:

- fachliche Regeln umgesetzt sind,
- serverseitige Validierung existiert,
- Berechtigungen geprüft werden,
- Datenbankconstraints vorhanden sind,
- Tests grün sind,
- Fehlerzustände sichtbar behandelt werden,
- UI Loading/Empty/Error/Success abdeckt,
- Dokumentation aktualisiert wurde,
- keine Secrets oder Debugreste vorhanden sind.

6. Grundlegende Datenregeln

6.1 Geld

Geld immer in Cent speichern:

80.000,00 € -> 8_000_000 Cent

Keine Gleitkommazahlen.

6.2 Prozentwerte

Basispunkte verwenden:

1,00 % = 100 Basispunkte
100,00 % = 10.000 Basispunkte

6.3 Aktien

Aktienanzahlen als Integer.

6.4 Zeit

Datenbank: UTC

Benutzeroberfläche: Europe/Berlin

Ticks besitzen eine eindeutige Tick-ID.

Jeder Tick hat Status pending, running, completed, failed.

Ein Tick darf dieselbe Periode nicht zweimal verbuchen.

6.5 Zufall

Zufallsereignisse serverseitig.

Für Tests und Demo-Seeds deterministische Seeds.

Jede zufallsbasierte Aktion speichert Seed oder Ergebnisparameter im Auditdatensatz.

7. Kerndomänen

7.1 Spieler

Account

Profil

Startstadt

Bargeld

legitimiertes Kapital

Informationen

Einfluss

Logistikkapazität

Personalkapazität

Reputation

Loyalität

Ermittlungsdruck

Portfolio

Unternehmensanteile

7.2 Unternehmen

Branchen:

Gastronomie

Eventmanagement

Logistik

Technologie

Immobilien

Medien

Bau

Sicherheitsdienstleistungen

Finanzdienstleistungen

Energie

Handel

Produktion

Für die erste spielbare Stufe:

Gastronomie

Logistik

Technologie

Unternehmenswerte:

Unternehmenswert

Kontostand

Umsatz

Kosten

Gewinn

Schulden

Mitarbeiter

Kapazität

Qualität

Marktanteil

Reputation

Compliance

Innovation

Risiko

Ermittlungsdruck

Eigentümerstruktur

Aktienstruktur

7.3 Städte und Bezirke

Erste Stadt: Köln

Erste strategische Bezirke:

Innenstadt

Hafenbezirk

Technologiepark

Gewerbering

Medienquartier

7.4 Märkte

Ein Markt wird definiert durch:

Saison + Stadt + Branche

Werte:

Gesamtnachfrage

Konjunktur

Wettbewerb

Lohnindex

Immobilienkostenindex

Risikofaktor

Ereignismodifikatoren

7.5 Börse

privates Unternehmen

private Beteiligungen

Börsengang

Aktie

Portfolio

Orderbuch

Marktorder

Limitorder

Trade

Dividende

Aktionärsrechte

Hauptaktionäre

feindliche Übernahme als abstrakte Kontrollmechanik

7.6 Kartelle

Kartell

Mitglied

Rolle

Einladung

Kartellkasse

Projekt

Vertrag

Abstimmung

Diplomatiebeziehung

Bezirkskontrolle

7.7 Informationen

öffentliche Information

analysierte Information

verdeckte Information

Vertrauensniveau

Genauigkeit

Aktualität

mögliche Falschinformation

Informationsbericht

Kauf und Verkauf von Berichten

7.8 Ermittlungsdruck

Auswirkungen:

Unternehmensumsatz

Aktienkurs

Kreditzinsen

Reputation

Geschäftspartner

Kartellstabilität

Spezialisten

Börsenzulassung

7.9 Weltereignisse

lokal oder global

Stadt

Bezirk

Branche

Start

Ende

Sichtbarkeit

Stärke

Modifikatoren

öffentliche Meldung

Tick-Auswirkungen

7.10 Saison

Start

Aufbauphase

Mittelphase

Endphase

Abschluss

Ranglisten

Hall of Fame

persistente Accountbelohnungen

saisonaler Reset

8. Vollständiger Tabellenkatalog

Die konkrete Migration darf später erweitert werden, muss aber mindestens diese Tabellen enthalten.

Identity und Spieler

users

refresh_tokens

players

player_resources

player_settings

player_achievements

Welt

seasons

cities

districts

sectors

city_sector_markets

market_snapshots

Unternehmen

companies

company_locations

company_metrics

company_upgrades

company_specialists

specialists

specialist_types

company_ownership

company_reports

company_contracts

Finanzen

accounts

ledger_transactions

ledger_entries

loans

loan_installments

bonds

bond_holdings

Börse

stock_listings

stock_classes

stock_holdings

stock_orders

stock_trades

stock_price_snapshots

dividend_declarations

dividend_payments

shareholder_votes

shareholder_vote_options

shareholder_ballots

Kartelle und Einfluss

cartels

cartel_members

cartel_roles

cartel_invitations

cartel_projects

cartel_project_contributions

cartel_treasury_rules

district_influence

influence_actions

diplomatic_relations

cartel_treaties

Informationen und PvP

intelligence_reports

intelligence_operations

intelligence_report_sales

strategic_actions

strategic_action_results

cooldowns

Events und Jobs

world_events

world_event_effects

game_ticks

job_runs

notifications

audit_logs

idempotency_keys

Ranglisten

leaderboard_snapshots

season_results

hall_of_fame_entries

9. API-Oberfläche

Alle Endpunkte unter /api/v1.

Auth

POST   /auth/register
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout
GET    /auth/me

Spieler

GET    /players/me
PATCH  /players/me
POST   /players/me/select-city
GET    /players/me/resources
GET    /players/me/activity

Welt

GET    /world/seasons/current
GET    /world/cities
GET    /world/cities/{city_id}
GET    /world/cities/{city_id}/districts
GET    /world/cities/{city_id}/markets
GET    /world/events

Unternehmen

GET    /companies
POST   /companies
GET    /companies/{company_id}
PATCH  /companies/{company_id}
POST   /companies/{company_id}/investments
POST   /companies/{company_id}/upgrades
POST   /companies/{company_id}/locations
GET    /companies/{company_id}/reports
GET    /companies/{company_id}/ownership

Spezialisten

GET    /specialists/market
POST   /companies/{company_id}/specialists
PATCH  /companies/{company_id}/specialists/{specialist_id}
DELETE /companies/{company_id}/specialists/{specialist_id}

Börse

GET    /exchange/listings
GET    /exchange/listings/{listing_id}
GET    /exchange/listings/{listing_id}/order-book
GET    /exchange/listings/{listing_id}/trades
POST   /exchange/orders
DELETE /exchange/orders/{order_id}
GET    /exchange/orders/me
GET    /exchange/portfolio
POST   /companies/{company_id}/ipo
POST   /companies/{company_id}/dividends

Kartelle

GET    /cartels
POST   /cartels
GET    /cartels/{cartel_id}
POST   /cartels/{cartel_id}/invitations
POST   /cartels/{cartel_id}/join
POST   /cartels/{cartel_id}/leave
PATCH  /cartels/{cartel_id}/members/{player_id}
POST   /cartels/{cartel_id}/treasury/deposit
POST   /cartels/{cartel_id}/projects
POST   /cartels/{cartel_id}/projects/{project_id}/contribute

Informationen

POST   /intelligence/operations
GET    /intelligence/reports
GET    /intelligence/reports/{report_id}
POST   /intelligence/reports/{report_id}/sell
POST   /intelligence/reports/{report_id}/buy

Einfluss und PvP

GET    /influence/cities/{city_id}
POST   /influence/actions
POST   /strategic-actions
GET    /strategic-actions/me

Ranglisten

GET    /leaderboards/current
GET    /leaderboards/history
GET    /hall-of-fame

Admin

GET    /admin/health
GET    /admin/jobs
POST   /admin/ticks/run
POST   /admin/events
PATCH  /admin/events/{event_id}
POST   /admin/events/{event_id}/activate
POST   /admin/events/{event_id}/end
POST   /admin/demo/reset

10. Benutzeroberfläche

Öffentliche Seiten

Landingpage

Anmeldung

Registrierung

Spielregeln

Datenschutz/Impressum-Platzhalter für lokale Version

Spielseiten

Onboarding und Stadtwahl

Hauptdashboard

Unternehmen

Unternehmensdetail

Investitionen

Spezialisten

Stadtmarkt

Bezirkskarte

Börse

Aktienlisting

Orderbuch

Portfolio

Kartell

Kartellprojekte

Informationen

Ereignisse

Ranglisten

Profil

Benachrichtigungen

Adminseiten

Systemstatus

Ticksteuerung

Eventsteuerung

Demo-Reset

Jobfehler

Audit-Ansicht

Designsystem

Stil

dunkler Hintergrund

Anthrazit und Schwarz

Goldakzente

Neon-Cyan sparsam für technische Zustände

Rot nur für Gefahr, Verlust und Ermittlungsdruck

Karten mit subtilen Grid- und Scanline-Effekten

klare Lesbarkeit vor Dekoration

Komponenten

AppShell

Sidebar

Topbar

ResourceBar

MetricCard

CompanyCard

MarketChart

OrderBook

TradeTicket

InfluenceMap

EventBanner

RiskMeter

InvestigationMeter

ConfirmDialog

EmptyState

ErrorState

LoadingSkeleton

Toast

DataTable

11. Wirtschaftsmodell Version 1

11.1 Marktattraktivität

Alle Faktoren als Werte von 0 bis 10.000 Basispunkten.

Attraktivität =
  Qualität              × 25 %
+ Reputation            × 20 %
+ Preisattraktivität     × 20 %
+ Innovation             × 15 %
+ Bezirkseinfluss        × 10 %
+ Zuverlässigkeit        × 10 %

11.2 Theoretischer Marktanteil

Unternehmensattraktivität
-----------------------------------
Summe aller Attraktivitäten im Markt

11.3 Kapazitätsgrenze

effektiver Marktanteil =
Minimum(theoretischer Marktanteil, Kapazitätsanteil)

Nicht verteilte Nachfrage wird in einem zweiten Durchlauf an Unternehmen mit freier Kapazität verteilt.

11.4 Umsatz

Umsatz =
Marktnachfrage
× effektiver Marktanteil
× Konjunkturfaktor
× Ereignisfaktor
× Vertragsfaktor

11.5 Kosten

Kosten =
Fixkosten
+ Personalkosten
+ Standortkosten
+ Kapazitätskosten
+ Wartung
+ Zinsen
+ Compliancekosten
+ Ereigniskosten

11.6 Gewinn

Gewinn = Umsatz - Kosten

11.7 Unternehmenswert

Version 1:

Unternehmenswert =
max(
  Nettovermögen,
  normalisierter Durchschnittsgewinn × Branchenmultiplikator
)
× Risikomultiplikator
× Reputationsmultiplikator

Die Formel muss vollständig dokumentiert, deterministisch und mit Grenzwerten geschützt sein.

11.8 Ermittlungsdruck

Steigt durch:

zu schnelles Wachstum

schlechte Compliance

riskante strategische Aktionen

entdeckte Informationsoperationen

negative Weltereignisse

hohe Verschuldung bei schlechter Stabilität

Sinkt durch:

Zeit

Complianceinvestitionen

transparente Unternehmensführung

spezialisierte Mitarbeiter

erfolgreiche Prüfungen

12. Aktienmarkt Version 1

12.1 Ordertypen

Markt-Kauf

Markt-Verkauf

Limit-Kauf

Limit-Verkauf

12.2 Preis-Zeit-Priorität

Bester Preis zuerst.

Bei gleichem Preis ältester Auftrag zuerst.

12.3 Reservierungen

Beim Kaufauftrag:

Geld auf dem Spielerkonto sperren.

Nur freies Guthaben ist weiter nutzbar.

Beim Verkaufsauftrag:

Aktien sperren.

Gesperrte Aktien dürfen nicht erneut verkauft werden.

12.4 Transaktionsablauf

Eine Trade-Ausführung muss in einer Datenbanktransaktion:

passende Orders sperren,

Restmengen prüfen,

Geldreservierung prüfen,

Aktienreservierung prüfen,

Geld übertragen,

Aktien übertragen,

Ledger schreiben,

Trade schreiben,

Orders aktualisieren,

Kurs aktualisieren,

Benachrichtigungen erzeugen.

Schlägt ein Schritt fehl, wird alles zurückgerollt.

12.5 Schutzmechanismen

kein Handel mit sich selbst

keine negative Ordermenge

kein Verkauf nicht verfügbarer Aktien

kein Kauf ohne reservierbares Guthaben

begrenzte Preisabweichung

idempotente Ordererstellung

Rate Limit

Audit Log

DB-Constraints

atomare Stornierung

Tests für konkurrierende Trades

13. Tick-System

Tickarten

Market Tick

Orders matchen

Trades ausführen

Kurs-Snapshots speichern

abgelaufene Orders stornieren

Reservierungen freigeben

Economy Tick

Marktnachfrage berechnen

Attraktivität berechnen

Marktanteile verteilen

Umsätze berechnen

Kosten buchen

Gewinne berechnen

Unternehmenswerte aktualisieren

Spezialisteneffekte anwenden

Ermittlungsdruck aktualisieren

Daily Tick

Kreditzahlungen

Dividenden

Tagesberichte

Cooldowns

Loyalität

Ereignisfortschritt

Ranglistensnapshot

Season Tick

Phasenwechsel

Saisonziele

Endwertung

Belohnungen

Hall of Fame

Resetvorbereitung

Idempotenz

Jede Ausführung erhält:

tick_type
period_start
period_end
unique_key
status
started_at
completed_at
checksum

Unique Constraint:

UNIQUE(tick_type, period_start, period_end)

14. Codex-Arbeitsprinzip

Niemals das gesamte Spiel in einem einzigen Auftrag erzeugen lassen.

Jede Phase:

Plan

kleine vertikale Änderung

Migration

Backend

Frontend

Tests

Seed

Dokumentation

manueller Smoke-Test

Codex /review

Commit

Codex-Start für jede Phase:

git status
codex --sandbox workspace-write --ask-for-approval on-request

Am Ende:

/review

Dann:

make test
git diff --check
git status

15. Phase 0 – Repository und ausführbares Fundament

Ziel

Ein leerer, aber vollständig startbarer Full-Stack-Stack.

Lieferumfang

Monorepo

Compose

Backend-Health-Endpunkt

Frontend-Startseite

PostgreSQL

Redis

Celery Worker

Celery Beat

Reverse-Proxy optional erst später

Makefile

Bootstrapskript

.env.example

CI-Grundgerüst

AGENTS.md

README

Codex-Prompt 0

Du arbeitest im neuen Repository SHADOWGRID.

Lies zuerst AGENTS.md vollständig. Erstelle danach Phase 0 des Projekts als
sauberes Full-Stack-Monorepo.

Verbindlicher Stack:
- Flask, SQLAlchemy 2, Alembic/Flask-Migrate, PostgreSQL
- Redis, Celery Worker, Celery Beat
- React, TypeScript strict, Vite, Tailwind
- Docker Compose
- pytest, Ruff, Black, mypy
- Vitest, ESLint, Prettier
- Playwright-Grundkonfiguration

Anforderungen:
1. `docker compose up --build` muss alle Dienste starten.
2. Backend stellt `/api/v1/health` bereit.
3. Frontend zeigt den Backendstatus.
4. PostgreSQL- und Redis-Healthchecks einbauen.
5. Keine Secrets committen.
6. `.env.example` mit sicheren Platzhaltern erstellen.
7. Root-Makefile mit bootstrap, up, down, logs, migrate, seed, lint, test.
8. Ein idempotentes `scripts/bootstrap.sh` erstellen.
9. README mit exakten WSL2- und Startbefehlen erstellen.
10. GitHub-Actions-Grundworkflows erstellen.
11. Tests für Health-Endpunkt und Frontendstatus erstellen.
12. Vor Abschluss alle verfügbaren Lints, Typprüfungen und Tests ausführen.
13. Keine Fachfeatures aus späteren Phasen vorwegnehmen.

Erstelle zuerst einen knappen Plan. Implementiere danach. Berichte abschließend:
- geänderte Dateien,
- ausgeführte Befehle,
- Testergebnisse,
- verbleibende Risiken.

Definition of Done

cp .env.example .env
docker compose up --build
curl http://localhost:8000/api/v1/health

Browser:

http://localhost:3000

Erwartung:

Frontend erreichbar

Backendstatus healthy

PostgreSQL verbunden

Redis verbunden

Worker erreichbar

alle Tests grün

16. Phase 1 – Auth, Spielerprofil und Onboarding

Ziel

Ein Benutzer kann ein Konto anlegen, sich anmelden, Köln wählen und das Dashboard betreten.

Lieferumfang

Usermodell

Passwort-Hashing

JWT Access und Refresh

Refresh-Token-Rotation

Spielerprofil

Ressourcen

Stadtwahl

Demoaccount nur lokal

Auth-UI

Onboarding

geschützte Routen

Logout

Seed Köln und Bezirke

Codex-Prompt 1

Implementiere Phase 1: Authentisierung, Spielerprofil und Stadt-Onboarding.

Lies AGENTS.md und die bestehenden Architekturunterlagen.

Fachlicher Ablauf:
1. Benutzer registriert sich.
2. Benutzer meldet sich an.
3. Das System erzeugt genau ein Spielerprofil.
4. Der Spieler wählt Köln.
5. Der Spieler erhält lokal konfigurierbares Startkapital von 80.000,00 €.
6. Danach gelangt er auf das geschützte Dashboard.

Anforderungen:
- sichere Passwort-Hashes
- Access- und Refresh-Token
- serverseitige Validierung
- eindeutige E-Mail und eindeutiger Nutzername
- Geld als Integer-Cents
- Startkapital über Ledger buchen, nicht direkt setzen
- Stadtwahl nur einmal, außer durch Adminreset
- Demoaccount ausschließlich bei `LOCAL_DEMO_MODE=true`
- Production-Konfiguration muss Demoaccount verweigern
- Rate Limits für Register und Login
- CSRF-/Tokenstrategie dokumentieren
- Loading-, Error- und Success-Zustände im Frontend
- Seed für Köln und fünf strategische Bezirke
- Unit-, API-, Integrations- und Playwright-Tests
- Migration und Dokumentation

Akzeptanz:
- Registrierung funktioniert.
- Login funktioniert.
- falsches Passwort wird sauber abgelehnt.
- doppelte Registrierung wird abgelehnt.
- Köln kann gewählt werden.
- Ledger enthält die Startkapitalbuchung.
- nicht authentisierte Nutzer sehen keine Spielseiten.
- Demoaccount funktioniert nur lokal.

Führe alle Tests aus und nutze danach `/review`.

Manuelle Abnahme

registrieren

anmelden

Köln auswählen

Dashboard öffnen

80.000,00 € sehen

Ledgerbuchung im Admin-/Debug-Endpunkt prüfen

abmelden

geschützte Seite aufrufen und Redirect erhalten

17. Phase 2 – Unternehmen und erste spielbare Schleife

Ziel

Der Spieler gründet ein Unternehmen und kann investieren.

Lieferumfang

Branchen

Unternehmensgründung

Unternehmensdetail

Geschäftskonto

Gründungsbuchung

erstes Investment

Unternehmenskennzahlen

Besitzstruktur

Unternehmensliste

Codex-Prompt 2

Implementiere Phase 2: Unternehmensgründung und Investments.

Erste Branchen:
- Gastronomie
- Logistik
- Technologie

Ablauf:
1. Spieler wählt Name, Branche und Bezirk.
2. Gründung kostet einen konfigurierbaren Betrag.
3. Geld wird atomar vom Spielerkonto auf das Geschäftskonto übertragen.
4. Unternehmen startet zu 100 % im Besitz des Gründers.
5. Spieler kann in Kapazität, Qualität, Innovation und Compliance investieren.
6. Jede Investition verändert nachvollziehbar die Unternehmenswerte.

Regeln:
- Namen validieren und pro Saison eindeutig machen.
- Ownership in Basispunkten.
- Keine direkte Geldmutation.
- Ledger mit doppelter Buchung.
- Transaktion und Row Locks verwenden.
- Idempotency-Key für Gründung und Investments.
- serverseitige Ownership- und Berechtigungsprüfung.
- alle Preise in Cent.
- Investmenteffekte datengetrieben konfigurieren.
- UI zeigt Kosten vor Bestätigung.
- ConfirmDialog vor Buchung.
- Unternehmensdetail zeigt Kennzahlen und Verlauf.
- Seedwerte für Branchen und Upgrades.
- Migration, Tests, Dokumentation.

Akzeptanz:
- Spieler kann ein Unternehmen gründen.
- Gründung kann nicht doppelt ausgeführt werden.
- zu wenig Geld wird abgelehnt.
- Eigentum beträgt exakt 100,00 %.
- Ledger ist ausgeglichen.
- Investment verändert nur vorgesehene Werte.
- fremde Spieler dürfen nicht investieren.
- UI aktualisiert sich nach erfolgreicher Aktion.

Spielbar nach Phase 2

Der Spieler kann:

Konto erstellen

Köln wählen

Unternehmen gründen

Unternehmenswerte ansehen

Investitionen tätigen

Noch fehlen echte Markt- und Gewinnberechnungen.

18. Phase 3 – Ledger, Wirtschaftstick und Marktanteile

Ziel

Das Spiel erzeugt automatisch wirtschaftliche Ergebnisse.

Lieferumfang

vollständiges Kontenmodell

Double-Entry-Ledger

City-Sector-Market

Nachfrage

Attraktivität

Kapazitätsverteilung

Umsatz

Kosten

Gewinn

Unternehmenswert

Wirtschaftstick

Berichte

Charts

Codex-Prompt 3

Implementiere Phase 3: autoritative Wirtschaftssimulation.

Die Berechnungen müssen deterministisch, getestet und dokumentiert sein.

Erstelle:
- Konten und Double-Entry-Ledger
- Märkte pro Saison, Stadt und Branche
- Marktattraktivitätsberechnung
- Marktanteilsverteilung mit Kapazitätsgrenze
- zweiten Verteilungsdurchlauf für Restnachfrage
- Umsatz- und Kostenberechnung
- Unternehmensgewinn
- Unternehmenswert Version 1
- Economy Tick mit Idempotenz
- Unternehmens- und Marktberichte
- Zeitreihen-Snapshots
- Dashboardcharts
- lokales Admin-Kommando zum manuellen Tick

Wichtige Regeln:
- kein Float für Geld oder Prozentwerte
- deterministisches Runden
- Summe der Marktanteile darf 100,00 % nicht überschreiten
- Überläufe und negative Werte verhindern
- Tick darf dieselbe Periode nicht doppelt buchen
- fehlgeschlagener Tick darf keine Teilbuchungen hinterlassen
- Tick in Datenbanktransaktion
- isolierte Domainfunktionen ohne Flask-Kontext
- Property-/Invariant-Tests für Marktverteilung
- Concurrency-Test für doppelte Tickauslösung
- Berichte enthalten Input, Modifikatoren und Ergebnis
- UI zeigt letzten Tick und nächsten geplanten Tick

Erzeuge Fixtures mit mehreren Unternehmen und prüfe:
- fairer Markt bei gleichen Werten
- bessere Qualität erhöht den Anteil
- Kapazitätsgrenze begrenzt den Anteil
- Restnachfrage wird korrekt verteilt
- negatives Ergebnis reduziert das Geschäftskonto
- Tick bleibt bei Wiederholung idempotent

Führe alle Tests und `/review` aus.

Invarianten

Ledgertransaktion ist immer ausgeglichen.

Marktanteile liegen zwischen 0 und 100 %.

Aktien- und Geldmengen werden nie negativ.

derselbe Tick erzeugt keine Doppelbuchung.

jede Unternehmenskennzahl ist aus einem Bericht nachvollziehbar.

19. Phase 4 – Spezialisten, Upgrades und lokale KI-Konkurrenz

Ziel

SHADOWGRID ist jetzt lokal als echtes Einzelspieler-Spiel in einer Multiplayerwelt spielbar.

Lieferumfang

Spezialistenmarkt

Spezialistentypen

Lohn

Level

Loyalität

Energie

Unternehmenseffekte

KI-Spieler

KI-Unternehmen

KI-Entscheidungen

reproduzierbarer Demo-Spielstand

Codex-Prompt 4

Implementiere Phase 4: Spezialisten und lokale KI-Konkurrenten.

Spezialistentypen:
- Finanzleitung
- Technologieexpertise
- Marktanalyse
- Compliance
- Logistik
- Diplomatie

Jeder Spezialist besitzt:
- Level
- Gehalt
- Loyalität
- Energie
- Fähigkeiten
- Arbeitgeber
- Cooldowns

Erstelle außerdem lokale KI-Spieler, damit das Spiel ohne weitere Menschen
sofort spielbar ist.

KI-Anforderungen:
- ausschließlich serverseitig
- regelbasiert, keine externe KI-API erforderlich
- deterministische Entscheidungsseeds im Demo-Modus
- unterschiedliche Strategien:
  - Wachstum
  - Effizienz
  - Innovation
  - aggressiver Marktanteil
  - konservative Stabilität
- KI gründet Unternehmen, investiert und reagiert auf Marktberichte
- KI darf keine Sonderrechte besitzen
- KI-Aktionen nutzen dieselben Services, Validierungen und Ledgerpfade wie Spieler
- KI-Tick ist idempotent
- Admin kann KI pausieren
- Demo-Seed erzeugt mindestens fünf KI-Spieler und neun Konkurrenzunternehmen

Frontend:
- Spezialistenmarkt
- Einstellen, Zuweisen, Entlassen
- Effekte transparent anzeigen
- KI-Spieler klar als lokale Simulation markieren

Tests:
- Spezialisteneffekte
- Gehaltsbuchungen
- Loyalitätsänderungen
- KI nutzt keine verbotenen Direktzugriffe
- KI erzeugt gültige, bezahlbare Aktionen
- reproduzierbarer Seed

Nach Seed und mehreren Ticks muss ein neuer Spieler einen dynamischen Markt sehen.

Erster vollständiger lokaler Spielzustand

Nach Phase 4:

make reset-local
make seed-demo
make up

Der Spieler sieht:

Köln

fünf Bezirke

drei Branchen

mehrere KI-Unternehmen

dynamische Marktanteile

Wirtschaftsberichte

Spezialisten

Gewinne und Verluste

Charts

Damit ist die erste echte spielbare Version erreicht.

20. Phase 5 – Börsengang und Aktienhandel

Ziel

Private Unternehmen können an die Ingame-Börse gehen und Aktien werden gehandelt.

Lieferumfang

IPO-Prüfung

Listings

Aktienklassen Version 1

Holdings

Orderbuch

Marktorder

Limitorder

Matching Engine

Trades

Kursverlauf

Portfolio

Dividenden

Hauptaktionäre

Codex-Prompt 5

Implementiere Phase 5: Ingame-Börse.

Zuerst die Domain und Tests, danach API und UI.

IPO-Voraussetzungen:
- konfigurierbarer Mindestunternehmenswert
- mehrere profitable Perioden
- Mindest-Compliance
- Mindestmitarbeiterzahl
- kontrollierter Ermittlungsdruck
- Börsengebühr
- geprüfte Unternehmensberichte

Beim IPO:
- Gesamtaktien als Integer
- Startpreis aus Unternehmenswert / Gesamtaktien
- Gründer legt angebotene Aktien fest
- Besitz- und Stimmrechte müssen exakt aufgehen
- keine Aktien aus dem Nichts nach Abschluss

Matching Engine:
- Preis-Zeit-Priorität
- Teilfüllungen
- atomare Trades
- Geld- und Aktienreservierungen
- keine Selbsttrades
- stornierbare offene Orders
- Ablaufzeit
- Markt- und Limitorders
- Kurs-Snapshots
- Idempotency-Key

Dividenden:
- Deklaration durch berechtigte Unternehmensführung
- Snapshot-Date für berechtigte Holdings
- atomare Auszahlungen
- Ledgerbuchungen
- keine doppelte Auszahlung

Frontend:
- Börsenübersicht
- Listingdetail
- Unternehmensberichte
- Orderbuch
- Kauf-/Verkaufsticket
- eigene Orders
- Portfolio
- Kurschart
- Dividendenhistorie
- Hauptaktionäre

Tests:
- Vollfüllung
- Teilfüllung
- konkurrierende Käufer
- konkurrierende Verkäufer
- Orderstornierung
- unzureichendes Guthaben
- unzureichende Aktien
- Selbsttrade
- Rundung
- doppelte Anfrage
- Rollback bei Fehler
- Dividenden-Snapshot
- Summe aller Aktien bleibt invariant

Nutze Datenbank-Row-Locks und führe Concurrency-Tests aus.

21. Phase 6 – Kartelle, Rollen und Bezirkseinfluss

Ziel

Spieler organisieren sich und konkurrieren gemeinsam.

Lieferumfang

Kartellgründung

Einladungen

Mitgliedschaft

Rollen

Berechtigungen

Kartellkasse

Einzahlungen

Ausgabenfreigaben

Projekte

Beiträge

Bezirkseinfluss

Kontrollpunkte

Kartellrangliste

Codex-Prompt 6

Implementiere Phase 6: Kartelle und Bezirkseinfluss.

Rollen:
- Leader
- Finanzleitung
- Diplomat
- Stratege
- Intelligence Officer
- Mitglied

Anforderungen:
- genau ein aktives Kartell pro Spieler
- Einladungsworkflow
- Rollenbasierte Berechtigungen
- Kartellkasse als eigenes Ledgerkonto
- Einzahlungen atomar
- Ausgaben nur mit passender Rolle
- konfigurierbare Ausgabenlimits
- Kartellprojekte mit Ziel, Kosten, Laufzeit und Fortschritt
- Beiträge von Geld, Einfluss oder Informationen
- Bezirkseinfluss pro Kartell und Bezirk
- Kontrollstatus aus Einflusswerten
- saisonale Rangliste

Projektbeispiele:
- Logistikknoten
- Technologiezentrum
- Medienkampagne
- Compliance-Netzwerk
- Handelszentrum

Sicherheit:
- keine doppelte Mitgliedschaft
- keine Selbstgenehmigung bei genehmigungspflichtigen Großausgaben
- Auditlog für Rollen- und Finanzänderungen
- Leaderwechsel transaktional
- Kartellauflösung nur mit Schutzregeln
- Mitgliederaustritt darf historische Ledgerdaten nicht löschen

Frontend:
- Kartellübersicht
- Mitglieder und Rollen
- Kartellkasse
- Projekte
- Bezirkskarte
- Einladungen
- Aktivitätslog

Tests für Autorisierung, konkurrierende Beiträge und Einflussinvarianten.

22. Phase 7 – Informationen und abstraktes PvP

Ziel

Informationsstrategen und strategische Konflikte werden spielbar.

Lieferumfang

Informationsoperation

Informationsberichte

Vertrauen

Genauigkeit

Aktualität

Berichtshandel

Schutzmaßnahmen

abstrakte strategische Aktionen

Entdeckungsrisiko

Cooldowns

Ermittlungsdruck

Codex-Prompt 7

Implementiere Phase 7: Informationssystem und abstraktes PvP.

Informationsarten:
- öffentlich
- analysiert
- verdeckt

Berichte können:
- korrekt
- unvollständig
- veraltet
- absichtlich irreführend

Jeder Bericht zeigt:
- Ziel
- Kategorie
- Aussage
- Vertrauensniveau
- Alter
- Quelle als abstrakte Ingame-Kategorie
- Ablaufdatum

Informationsoperation:
- Kosten in Informationen und/oder Geld
- Spezialistenfähigkeit
- Zielschutz
- Kartellbonus
- Zufallsanteil mit gespeichertem Ergebnis
- Erfolgsgrad
- Entdeckungswahrscheinlichkeit
- Ermittlungsdruck
- Cooldown

Strategische Aktionen bleiben vollständig abstrakt:
- Projekt verzögern
- Reputation schwächen
- Betriebskosten temporär erhöhen
- gegnerische Information unzuverlässiger machen
- Spezialisten temporär belasten

Es dürfen keine realen Hacking-, Sabotage-, Gewalt- oder Umgehungsmethoden
beschrieben oder simuliert werden.

Anforderungen:
- serverautoritativ
- keine Aktion ohne bekannte Ziel-ID
- Kosten vor Ausführung reservieren
- Ergebnis atomar speichern
- idempotente Ausführung
- Schutz vor Spam
- Rate Limits
- Cooldowns
- Audit Log
- Opfer erhält nur fachlich erlaubte Informationen
- Admin kann Aktionen nachvollziehen
- Berichte können zwischen Spielern gehandelt werden
- Berichtskäufer erhält eine unveränderbare Kopie

Tests:
- Erfolg, Teilerfolg und Scheitern
- Entdeckung
- falscher Bericht
- abgelaufener Bericht
- doppelte Ausführung
- Cooldown
- unzureichende Ressourcen
- unberechtigter Zugriff

23. Phase 8 – Weltereignisse und Adminsteuerung

Ziel

Die Welt verändert sich dynamisch und kann lokal gesteuert werden.

Lieferumfang

Eventdefinitionen

Eventeffekte

globale/lokale Events

Start/Ende

Vorschau

Aktivierung

automatisches Auslaufen

Eventmeldungen

Admin-Dashboard

Eventaudit

Codex-Prompt 8

Implementiere Phase 8: Weltereignisse und Adminsteuerung.

Erste Ereignisse:
- Hafenstreik
- Technologieboom
- Immobilienkrise
- Datenleck
- Finanzprüfung

Event kann wirken auf:
- globale Welt
- Stadt
- Bezirk
- Branche
- Unternehmen

Effekte:
- Umsatzmultiplikator
- Kostenmultiplikator
- Nachfrage
- Spezialistengehälter
- Immobilienkosten
- Reputation
- Ermittlungsdruck
- Aktienrisiko
- Vertragswahrscheinlichkeit

Anforderungen:
- Effekte datengetrieben
- Start und Ende
- Vorschau ohne Aktivierung
- keine Änderung historischer Eventversionen
- aktive Eventinstanz speichert ihre konkrete Konfiguration
- sich überlappende Effekte mit dokumentierter Reihenfolge
- harte Ober- und Untergrenzen
- Admin-RBAC
- Audit Log
- Event kann sicher beendet werden
- Eventauswirkung erscheint in Unternehmensberichten
- Socket.IO-Benachrichtigung
- UI-Banner und Eventfeed

Tests:
- Start
- Auslaufen
- Überlappung
- Grenzwerte
- deaktiviertes Event
- wiederholter Schedulerlauf
- fehlende Adminberechtigung

24. Phase 9 – Saison, Ranglisten und Reset

Ziel

Das Spiel besitzt einen vollständigen langfristigen Zyklus.

Lieferumfang

Saisonphasen

Saisonziele

Wertung

Ranglisten

Abschluss

Belohnungen

Hall of Fame

kontrollierter Reset

Archivierung

Codex-Prompt 9

Implementiere Phase 9: Saisonzyklus.

Saisonphasen:
- setup
- early
- mid
- late
- scoring
- archived

Ranglistenkategorien:
- reichster Spieler
- wertvollstes Portfolio
- erfolgreichster Unternehmer
- größtes Unternehmen
- stärkstes Kartell
- größte Börsengesellschaft
- beste Dividendenrendite
- höchste Bezirkskontrolle
- beste Diplomatie
- größtes Informationsnetzwerk
- höchste Stabilität
- beste Erholung nach einer Krise

Anforderungen:
- Bewertung aus unveränderbaren Snapshots
- Gleichstände nachvollziehbar behandeln
- Saisonabschluss idempotent
- Hall of Fame unveränderbar
- Account, Erfolge, Titel und kosmetische Belohnungen bleiben
- saisonale Unternehmen, Aktien, Marktanteile und Kartellwerte werden archiviert
- Reset löscht keine Finanzhistorie
- neue Saison kann aus Templates erzeugt werden
- lokaler Admin kann Saison verkürzen und simulieren
- UI zeigt Phase, Restzeit, Ziele und Wertung

Tests:
- Endwertung
- Gleichstand
- doppelte Endwertung
- Archivierung
- Persistenz von Erfolgen
- Resetgrenzen
- neue Saison

25. Phase 10 – Verträge, Kredite, Anleihen und Immobilien

Ziel

Die im Grundkonzept vorgesehenen erweiterten Märkte werden ergänzt.

Teil A: Verträge

Lieferverträge

Dienstleistungsverträge

Ausschreibungen

Laufzeit

Preis

Kapazitätsbindung

Vertragsbruch als abstrakter Spielstatus

Reputationseffekt

Teil B: Kredite

Kreditantrag

Zinssatz

Laufzeit

Rate

Ausfall

Sicherheiten als abstrakte Ingamewerte

Ermittlungs- und Reputationswirkung

Teil C: Anleihen

Emission

Nennwert

Zinssatz

Laufzeit

Holdings

Zinszahlung

Rückzahlung

Ausfall

Teil D: Immobilien

Grundstück

Gebäude

Gewerbefläche

Hauptquartier

Miete

Kauf

Verkauf

Stadt-/Bezirkspreisindex

Nutzung durch Unternehmen

Codex-Prompt 10

Implementiere Phase 10 in vier getrennten Unterphasen:
A Verträge, B Kredite, C Anleihen, D Immobilien.

Beginne nur mit Unterphase A. Nach vollständiger Abnahme und Review darf die
nächste Unterphase begonnen werden.

Für jede Unterphase:
- Domainmodell
- Invarianten
- Datenbankmigrationen
- Services
- API
- UI
- Ledger
- Scheduler
- Audit
- Tests
- Dokumentation

Keine Unterphase darf Geld oder Eigentum außerhalb der bestehenden
transaktionalen Ledger- und Ownership-Services verändern.

26. Phase 11 – Echtzeit, Benachrichtigungen und UX

Ziel

Das Spiel fühlt sich lebendig und verständlich an.

Lieferumfang

Socket.IO-Kanäle

In-App-Benachrichtigungen

ungelesen/gelesen

Eventfeed

Orderupdates

Tickupdates

Kartelleinladungen

Unternehmenswarnungen

optimistische UI nur bei ungefährlichen Aktionen

Accessibility

responsive Layout

Eventnamen

player.resources.updated
company.metrics.updated
market.snapshot.created
exchange.order.updated
exchange.trade.executed
cartel.invitation.created
cartel.project.updated
world.event.started
world.event.ended
notification.created
season.phase.changed

Anforderungen

Authentisierte Socket-Verbindung

Räume pro Spieler, Kartell und Stadt

keine vertraulichen Daten in falsche Räume

Reconnect

Eventversion

Payloadvalidierung

REST bleibt Source of Truth

Socket-Events lösen Query-Invalidierung aus

kein alleiniger Zustandsbesitz im Socketclient

27. Phase 12 – Härtung, Performance und Release-Kandidat

Ziel

Ein reproduzierbarer lokaler Release-Kandidat.

Security

Authz-Matrix prüfen

Rate Limits

Secret Scan

Dependency Scan

CORS

Security Header

Inputgrößen

Dateiuploads zunächst deaktiviert

Admintrennung

Audit

Session-/Tokenwiderruf

Passwortregeln

keine sensiblen Logs

Fehlerantworten ohne Stacktrace

Demo-Modus production-safe

Datenintegrität

Ledger-Invarianten

Aktienmengen

Ownershipsumme

Marktanteile

Idempotenz

Foreign Keys

Unique Constraints

Check Constraints

Concurrency-Tests

Backup und Restore

Performance

DB-Indizes

N+1-Abfragen

Pagination

Query Limits

Snapshotaggregation

Cache nur für ableitbare Daten

Lasttest für Tick und Order Matching

100 lokale simulierte Spieler

500 Unternehmen

10.000 offene Orders als Testziel

Betrieb

strukturierte Logs

Correlation IDs

Health

Readiness

Jobstatus

Fehlerqueue

lokales Backup

lokaler Restore

Seedversion

Migrationscheck

Release Notes

Codex-Prompt 12

Führe Phase 12 als Release-Candidate-Härtung durch.

Keine neuen Gameplayfeatures.

Arbeite in dieser Reihenfolge:
1. Architektur- und Security-Review
2. Datenbankinvarianten
3. Concurrency und Idempotenz
4. Backendtests
5. Frontendtests
6. Playwright-End-to-End
7. Lasttests
8. Backup/Restore
9. Dokumentation
10. finaler `/review`

Erstelle zuerst einen Findings-Bericht nach Kritikalität.
Behebe danach nur reproduzierbare oder klar belegte Probleme.
Für jede Behebung Regressionstest hinzufügen.

Release-Kriterien:
- alle Lints und Typprüfungen grün
- alle Unit-, Integrations-, API- und E2E-Tests grün
- keine Critical/High Findings
- keine Secrets
- frischer Bootstrap funktioniert
- Demo-Seed funktioniert
- Backup und Restore funktionieren
- `make verify-release` besteht

28. Vollständige Makefile-Schnittstelle

Das Repository soll mindestens diese Befehle anbieten:

make help
make bootstrap
make up
make down
make restart
make logs
make ps
make clean
make reset-local
make seed
make seed-demo
make migrate
make migration
make shell-backend
make shell-db
make shell-redis
make backend-lint
make backend-format
make backend-typecheck
make backend-test
make frontend-lint
make frontend-format
make frontend-typecheck
make frontend-test
make e2e
make test
make review-ready
make backup-local
make restore-local
make verify-release

29. .env.example

Nur Platzhalter:

APP_ENV=local
FLASK_DEBUG=false
LOCAL_DEMO_MODE=true
TIMEZONE=Europe/Berlin

BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_DB=shadowgrid
POSTGRES_USER=shadowgrid
POSTGRES_PASSWORD=replace-local-password
DATABASE_URL=postgresql+psycopg://shadowgrid:replace-local-password@postgres:5432/shadowgrid

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

JWT_SECRET_KEY=replace-with-long-random-local-secret
SECRET_KEY=replace-with-long-random-local-secret

CORS_ORIGINS=http://localhost:3000
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_SOCKET_URL=http://localhost:8000

SEED_VERSION=1
DEMO_RANDOM_SEED=28001
STARTING_CASH_CENTS=8000000

Bootstrap muss sichere lokale Werte erzeugen, falls .env fehlt.

30. Seed-Konzept

Basis-Seed

Saison

Köln

fünf Bezirke

drei Branchen

Upgradearten

Spezialistentypen

Eventtemplates

Marktparameter

Demo-Seed

Demoaccount

fünf KI-Spieler

neun KI-Unternehmen

erste Marktberichte

mehrere Spezialisten

ein lokales Kartell

ein börsenfähiges Beispielunternehmen

historische Kursdaten

ein geplantes Weltereignis

Seed-Regeln

idempotent

versioniert

deterministisch

keine echten persönlichen Daten

keine produktiven Passwörter

lokale Demo-Credentials klar kennzeichnen

Production verweigert Demo-Seed

31. Testpyramide

Unit-Tests

Formeln

Rundung

Invarianten

Berechtigungsregeln

Zustandsübergänge

Spezialisteneffekte

Ereigniskombinationen

Saisonwertung

Integrationstests

PostgreSQL

Ledger

Tick

Order Matching

Dividenden

Kartellkasse

Scheduler

Concurrency

API-Tests

Auth

Validierung

Statuscodes

Pagination

Ownership

RBAC

Rate Limits

Idempotency-Key

Frontendtests

Komponenten

Formulare

Fehlerzustände

Queryinvalidierung

Zugriffssteuerung

Zahlenformat de-DE

responsive Navigation

E2E-Szenarien

E2E 1: Neuer Spieler

registrieren

anmelden

Köln wählen

Unternehmen gründen

investieren

Tick ausführen

Bericht öffnen

E2E 2: Spezialist

Spezialistenmarkt öffnen

Spezialist einstellen

Unternehmen zuweisen

Tick ausführen

Effekt im Bericht prüfen

E2E 3: Börse

Unternehmen listen

zweiter Spieler kauft

Order matcht

Portfolio aktualisiert

Ledger prüfen

E2E 4: Kartell

Kartell gründen

Spieler einladen

beitreten

Geld einzahlen

Projekt finanzieren

Einfluss prüfen

E2E 5: Event

Admin erstellt Hafenstreik

Vorschau

aktivieren

Tick

Logistikbericht zeigt Effekt

Event endet

E2E 6: Saison

Saison verkürzen

Abschluss ausführen

Rangliste prüfen

Hall of Fame prüfen

neue Saison erzeugen

32. Release-Abnahmematrix

Lokaler Start

frischer Klon

.env automatisch oder dokumentiert erzeugt

make bootstrap

make up

Migrationen automatisch

Basis-Seed automatisch

Demo-Seed optional

Browser erreichbar

Gameplay

Registrierung

Login

Stadtwahl

Unternehmen

Investments

Spezialisten

Wirtschaftstick

KI-Konkurrenz

Börse

Kartell

Informationen

PvP abstrakt

Weltereignisse

Saison

Ranglisten

Integrität

Ledger ausgeglichen

keine negativen Geldbestände

keine negativen Aktienbestände

Aktiengesamtmenge invariant

Ownership gültig

Marktanteile gültig

Ticks idempotent

Trades atomar

Dividenden einmalig

Reset archiviert statt zerstört

Qualität

Ruff

Black

mypy

pytest

Coverageziel

ESLint

Prettier

TypeScript

Vitest

Playwright

Secret Scan

Dependency Scan

Codex /review

33. Lokaler Ein-Befehl-Start

Der finale Benutzerablauf soll so aussehen:

git clone <repository>
cd shadowgrid
make bootstrap
make up

Dann:

Spiel:      http://localhost:3000
Backend:    http://localhost:8000
API Health: http://localhost:8000/api/v1/health

Demo-Spielstand:

make seed-demo

Vollständiger lokaler Reset:

make reset-local
make seed-demo

Alle Tests:

make test

Releaseprüfung:

make verify-release

34. Codex-Prompt für einen neuen Arbeitsabschnitt

Lies AGENTS.md und alle für diese Aufgabe relevanten Dateien.

Aufgabe:
[GENAU EINE KLEINE AUFGABE EINTRAGEN]

Vorgehen:
1. Prüfe den aktuellen Repositoryzustand.
2. Identifiziere bestehende Architektur, Tests und Datenbankregeln.
3. Erstelle einen knappen Implementierungsplan.
4. Setze nur den angeforderten Scope um.
5. Ergänze Migrationen, Tests, Seeds und Dokumentation.
6. Führe relevante Lints, Typprüfungen und Tests aus.
7. Prüfe den Diff auf Security, Datenintegrität und unbeabsichtigte Änderungen.
8. Nutze `/review`.
9. Berichte:
   - geänderte Dateien,
   - fachliches Verhalten,
   - Tests und Ergebnisse,
   - offene Risiken.

Nicht erlaubt:
- Secrets ausgeben oder committen
- bestehende Nutzeränderungen überschreiben
- Geschäftslogik in Routen oder UI verstecken
- Geld, Aktien oder Eigentum ohne Ledger verändern
- Tests entfernen, nur damit der Build grün wird
- destruktive Git- oder Datenbankbefehle ohne Freigabe

35. Codex-Prompt zur Fehlerbehebung

Analysiere den gemeldeten Fehler reproduzierbar.

Fehler:
[FEHLER EINFÜGEN]

Arbeite in dieser Reihenfolge:
1. Reproduktion mit minimalen Schritten.
2. Betroffene Schicht und Ursache bestimmen.
3. Bestehende Tests prüfen.
4. Einen fehlschlagenden Regressionstest hinzufügen.
5. Kleinste sichere Korrektur implementieren.
6. Relevante und vollständige Tests ausführen.
7. Diff auf Seiteneffekte prüfen.
8. Keine allgemeine Refaktorierung außerhalb des Fehlers.
9. Ergebnis mit Ursache, Fix, Testnachweis und verbleibendem Risiko berichten.

36. Codex-Prompt zum Security-Review

Führe ein autorisiertes Security-Review dieses lokalen SHADOWGRID-Repositories
durch. Verändere zunächst nichts.

Prüfschwerpunkte:
- Secrets und unsichere Konfiguration
- Authentisierung und Tokenrotation
- Autorisierung, Ownership und Kartellrollen
- IDOR
- Injection
- XSS
- CSRF-Strategie
- CORS
- Rate Limits
- Adminendpunkte
- Datenlecks in Socket.IO
- Ledgermanipulation
- Race Conditions im Aktienhandel
- doppelte Tickausführung
- Replay und fehlende Idempotenz
- unsichere Demo-Modi
- sensible Logs
- Dependencyrisiken

Erstelle Findings mit:
- Kritikalität
- Datei und Stelle
- konkrete Auswirkung
- Reproduktion oder Beleg
- kleinste sichere Behebung
- Regressionstest

Behebe erst nach dem Findings-Bericht bestätigte Probleme.
Keine Secrets anzeigen.

37. Codex-Prompt zum finalen Release-Review

Prüfe SHADOWGRID als lokalen Release-Kandidaten.

Erwarteter Start:
- `make bootstrap`
- `make up`
- `make seed-demo`
- `make test`
- `make verify-release`

Prüfe:
1. frischer Aufbau
2. Datenbankmigrationen
3. Demo-Seed
4. alle Kern-E2E-Flows
5. Ledgerintegrität
6. Aktieninvarianten
7. Tickidempotenz
8. Auth und RBAC
9. Socket-Datentrennung
10. Backup und Restore
11. Production-Sicherheitsflags
12. Dokumentation

Erstelle eine Go/No-Go-Entscheidung.
Ein Go ist nur erlaubt, wenn keine Critical/High-Probleme bestehen und alle
verbindlichen Tests grün sind.

38. Empfohlene Commitfolge

chore: initialize monorepo and local compose stack
feat(auth): add authentication and player onboarding
feat(world): seed cologne and initial districts
feat(companies): add company creation and investments
feat(ledger): add double-entry accounting
feat(economy): add deterministic economy ticks
feat(specialists): add specialist management
feat(ai): add local simulated competitors
feat(exchange): add ipo and stock order book
feat(cartels): add cartel roles and treasury
feat(influence): add district influence projects
feat(intelligence): add reports and abstract strategic actions
feat(events): add world event engine and admin controls
feat(seasons): add scoring and hall of fame
feat(finance): add contracts loans and bonds
feat(real-estate): add property market
feat(realtime): add socket notifications
test(e2e): cover complete player journeys
security: harden release candidate
docs: finalize local operations and game rules

39. Die verbindliche Reihenfolge

Nicht überspringen:

0 Fundament
1 Auth und Spieler
2 Unternehmen
3 Wirtschaft und Ledger
4 Spezialisten und KI
5 Börse
6 Kartelle und Einfluss
7 Informationen und PvP
8 Weltereignisse
9 Saison
10 erweiterte Märkte
11 Echtzeit und UX
12 Härtung

Die Börse darf nicht vor einem stabilen Ledger entstehen.Kartellfinanzen dürfen nicht vor Rollen und Audit entstehen.PvP darf nicht vor Cooldowns, Idempotenz und Ermittlungsdruck entstehen.Saisonreset darf nicht vor Archivierung und Snapshots entstehen.

40. Der erste konkrete Startauftrag

Lege AGENTS.md aus Abschnitt 5 an.

Speichere die Grundidee als docs/game-design/SHADOWGRID_SPEC.md.

Starte Codex im Repository.

Sende ausschließlich Codex-Prompt 0.

Prüfe und starte Phase 0 lokal.

Nutze /review.

Committe erst bei grünen Tests.

Fahre mit Prompt 1 fort.

Der schnellste sichere Weg ist nicht ein gigantischer Einmal-Prompt, sondern eine Kette vollständig abgenommener, sofort lauffähiger vertikaler Schritte.