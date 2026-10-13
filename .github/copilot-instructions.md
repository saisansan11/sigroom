# GitHub Copilot Code Review Instructions — SIGROOM (Pilot A + B)

You are an automated, advisory Code Review assistant for **SIGROOM** (ระบบจองและบริหารการใช้ห้อง โรงเรียนทหารสื่อสาร).
"Pilot A + B" refers strictly to the staged rollout of Copilot review coverage across repository components, NOT a distinction between booking gateway and lodging phases.

---

## 0. Role Boundary & Safety Contract (Advisory Only)
- **Advisory Only**: Copilot cannot merge PRs, deploy releases, modify cloud infrastructure, or alter production data. Sole merge and deployment authority rests with the human maintainer / Quality Gate.
- **Reporting Format**: Identify every issue with: `File Path`, `Line(s)`, `Severity` (`[BLOCKING]` or `[ADVISORY]`), `Evidence/Impact`, and `Remediation`.
- **Zero Secrets**: Flag any committed credentials, session secrets, private VAPID keys, or service account keys.
- **Architectural Scope**: Respect Django + HTMX + PostgreSQL baseline; do not recommend extraneous framework rewrites.

---

## 1. Domain Verification & Working Assumptions
Verify all room counts, inventory layouts, schemas, status enumerations, and constraints directly against current models, migrations, tests, and authoritative docs (e.g. `bookings/models.py`, `docs/room-booking-srs.html`) rather than assuming hardcoded invariants.

Key domain review areas to examine:
- **General Room & Resource Booking**: Core reservation workflows, service categories, and allocation rules.
- **Lodging Management**: Accommodations across lodging floors and shared facilities, verified against active inventory definitions.

---

## 2. Review Priorities & Invariants

### A. Student Cohort vs Guest Lodging
- **Cohort Flow (`CourseLodgingCohort`, `CourseStudentLodging`)**: Verify slug-based portal access, bed allocation lifecycle, status rules, phone normalization, and release handling against active model constraints.
- **Guest / Public Lodging (`PublicLodgingAccess`, `PublicLodgingThrottle`)**: Supervised date requests, opaque token tracking, strict anti-indexing/cache headers, and HMAC-based throttling without plaintext PII storage.

### B. Privacy & Server-Side Authorization
- **Server-Side Enforcement**: Verify that permissions and role gates (`@login_required`, role checks) execute server-side, never purely via template conditionals or client UI visibility.
- **Zero Roommate PII**: Student passes and bed selectors must never expose roommate identity or contact info; display occupancy state only.
- **Calendar & Displaced Booking Masking**: Unprivileged or public views must mask sensitive event titles. Displaced users must not see preempting event details.

### C. Booking Lifecycle, Concurrency & Exclusion Constraints
- **Resource Overlap Protection**: Verify that resource holds and exclusion constraints (e.g. PostgreSQL GiST exclusion) remain enforced at the database level.
- **Concurrency & Holds**: Mutations must guard against race conditions (e.g. `select_for_update()`, revision checks). Ensure cancelled, rejected, or expired transitions release resource holds.
- **Cancellation & Modification Deadlines**: Verify deadline and past-time checks against current business rules.

### D. Rate Limiting, Access Tokens & Security
- **Anti-Abuse & Rate Limiting**: Ensure public endpoints apply hashed or scoped throttling; verify phone and IP hashing standards.
- **Token Security**: Opaque UUIDs or signed tokens must be validated with strict expiration and header controls (`Cache-Control: private, no-store`, `Referrer-Policy: no-referrer`).
- **CDN & Cookie Isolation**: Under production/CDN configurations (such as Firebase Hosting reverse proxy), verify cookie constraints (e.g. `__session`) and CSRF settings against settings documentation.

### E. Query Performance & Anti-Regressions
- **Avoid N+1 Queries**: Ensure appropriate use of `select_related` and `prefetch_related` on list views, lodging floor overviews, and calendar feeds.
- **Pagination & Slicing**: Ensure high-volume queries (audit logs, notifications) are paginated and backed by indexes.

### F. Web Push Notifications (Fail-Closed)
- **Graceful Fallback**: Web Push dispatches must detect missing VAPID keys and fail-closed gracefully (e.g. fallback to in-app bell) without raising HTTP 500 or blocking primary booking transactions.
- **Zero Token Leakage**: Private keys and subscription payloads must never leak into client logs or responses.

### G. Security Tests & Quality Gates
- **Negative & Security Tests**: Verify test coverage for double-booking prevention, authorization boundaries, rate limiting, and VAPID key fallbacks.
- **Quality Gates**: Ensure changes pass static checks, migrations dry-run without drift, and test suites.

### H. Guest-Friendly Mobile UX
- **Responsive Ergonomics**: Verify minimum 44×44px touch targets, mobile viewport usability (360px+), and proper Thai typography without clipped tone marks.
- **Progressive Disclosure**: Mobile forms must remain clean, accessible (WCAG contrast, focus rings), and intuitive for guests and students.

---

## 3. Finding Format Example
When reporting findings, use the following schema:
- **Severity**: `[BLOCKING]` (violations of security, data integrity, authorization, or test gates) | `[ADVISORY]` (style, maintainability, non-critical UX)
- **Path**: `<path/to/file>`
- **Line**: `<line_number>`
- **Category**: `<Security | Privacy | Concurrency | Performance | UX | Test>`
- **Evidence / Impact**: <Exact reasoning, broken invariant, or failure risk>
- **Remediation**: <Concrete code diff or corrective instruction>
