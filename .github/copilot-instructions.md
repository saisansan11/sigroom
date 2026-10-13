# GitHub Copilot Instructions — SIGROOM

## 1. Governance & Execution Boundaries
- **Agent Roles**: Antigravity is the sole code implementer; ChatGPT is the QA/Gatekeeper reviewer; GitHub Copilot provides advisory suggestions only (not authority).
- **Preauthorized Operations**: Reversible, in-scope implementation, refactoring, and test execution are preauthorized. Do not pause for midflight human approvals on standard development tasks.
- **Mandatory Human Approvals**: Separate human (Agentic CEO) authorization is ALWAYS required for: (1) PR merges (`"merge PR #..."`), (2) production deployments, and (3) destructive, high-risk, or billing/financial mutations.
- **Production Release Branch (`feat/lodging-v5-2`)**: Current base branch. Pushes to `feat/lodging-v5-2` auto-trigger Cloud Build (`cloudbuild.yaml`) live deployment. **NEVER push directly or trigger unapproved deploys to `feat/lodging-v5-2`**. Work strictly in isolated feature branches/worktrees. Preserve all untracked and dirty files.

## 2. Core Architecture & Key Paths
- **Stack**: Python 3.12, Django 5.2 LTS, PostgreSQL 16 (`btree_gist` extension), `uv`. Server-rendered Django templates + HTMX (`django-htmx`) + FullCalendar. No React/SPA.
- **Key Modules**:
  - `config/`: `settings.py`, `urls.py`, `security.py` (reverse proxy trust, `__session` cookie, `DJANGO_SECURE`).
  - `accounts/`: `models.py` (`User`, `Unit`), `middleware.py` (`LodgingStudentScopeMiddleware`, `MustChangePasswordMiddleware`).
  - `resources/`: `models.py` (`Resource` [room/equipment], `ResourceRule`, `ResourceApprover`, `ResourcePhoto`).
  - `bookings/`: `models.py` (`Booking`, `BookingResource`, `BookingSeries`, `BookingAmendment`, `Preemption`), `lodging_models.py` (`CourseLodgingCohort`, `CourseStudentLodging`, `LodgingRate`, `LodgingMeterReading`, `PublicLodgingThrottle`), `services.py`.
  - `approvals/`, `audit/`, `notifications/`: Decision workflows (`Approval.Action.WITHDRAWN`), append-only audit trail, Web Push (`pywebpush`).
  - Pipelines: `.github/workflows/pr-safety-gate.yml` (CI gate), `cloudbuild.yaml` (Cloud Run build/migrate/deploy).

## 3. Concurrency, Database & Domain Invariants
- **Database Exclusion (Non-Negotiable)**: `bookings.BookingResource` MUST enforce PostgreSQL `ExclusionConstraint` with `GIST` on `(resource =, booking !=, hold &&)` where `released_at IS NULL` (SRS FR-09/35). Never replace database exclusion with application-only checks.
- **Lodging Cohorts & Beds**:
  - `allocation_status` (`allocated` vs. `released`) controls room holds; `is_active` controls self-service portal access. Released cohorts must never be active (`check_released_cohort_cannot_be_active`).
  - `CourseStudentLodging` enforces DB uniqueness on `(cohort, room, bed_number)`, `(cohort, phone)`, and `(cohort, user)`.
  - Cohorts conflict bidirectionally with regular bookings. Mutations require atomic transactions (`transaction.atomic`) and row locks (`select_for_update`).
- **Amendments & Preemption**: Enforce `base_revision` optimistic concurrency locking, atomic hold transitions, and `Approval.Action.WITHDRAWN` audit tracking.
- **Billing & Utilities**: `LodgingRate` prices must be non-negative; `LodgingMeterReading` requires air-conditioned rooms (`Resource.Cooling.AIR`), `meter_out >= meter_in`, valid stay dates, and audit logging.

## 4. Security, Privacy & Role Guardrails
- **Role Enforcement**: Server-side checks are mandatory. `LodgingStudentScopeMiddleware` restricts student accounts (`is_lodging_student`) from staff/booking routes. UI condition hiding is never security.
- **Privacy & PII**: Zero roommate PII exposure on student portals or digital passes. Use opaque UUID tokens (`CourseLodgingAccess`, `PublicLodgingAccess`). Public requests throttled via HMAC hashing (`PublicLodgingThrottle`).
- **Secrets & Proxy Security**: Zero hardcoded credentials (`.env` only). Never trust raw `X-Forwarded-For`; read client IP via `CLIENT_IP_HEADER` or `TRUSTED_PROXY_HOPS`. Production requires `SESSION_COOKIE_NAME="__session"`.
- **Database Migrations**: Expand/contract only. Pipeline order: **migrate before deploy** (`sigroom-migrate` Cloud Run job). Never change room inventory or schemas without explicit requirements.

## 5. Confirmed Executable Test & QA Commands
- All commands verified from repo files (`pyproject.toml`, `package.json`, `.github/workflows/pr-safety-gate.yml`). Never claim CI/tests passed without executing them.
```bash
# Django system check and migration drift check
uv run manage.py check
uv run manage.py makemigrations --check --dry-run

# Full automated test suite & critical regression suite
uv run pytest
uv run pytest -q config/tests.py accounts/tests_m6.py audit/tests.py approvals/tests.py bookings/tests.py bookings/tests_guest_and_lodging.py bookings/tests_lodging_v4.py bookings/tests_v7_b.py resources/tests.py

# Production deploy check & dependency security audit
uv run manage.py check --deploy
uvx --from pip-audit==2.10.1 pip-audit --requirement requirements.txt

# UI interactions (Node runner) & Playwright Axe accessibility gate (390px mobile & 1280px desktop)
npm run test:interaction
npm run test:a11y

# Git whitespace and hygiene check
git diff --check
```
- **PR Safety Gate**: GitHub Actions aggregate job in `.github/workflows/pr-safety-gate.yml` requires repository checks, critical regression, full regression, security audit, and a11y audit. Never weaken, bypass, or reduce safety gates.
