# R0 — Lodging visual unification and room popup

> **Historical R0 snapshot.** Sections through “Gate status / handoff” record the pre-implementation audit on 2026-09-28. They are intentionally retained for traceability and are superseded by the R1–R9 closeout at the end of this document.

Date: 2026-09-28. Status: current-state audit; implementation has not started.

## Verified baseline

- Remote HEAD and default branch `feat/lodging-v5-2`: `edbe58fc7a2b3513c4ae76f9c81c1175f94a34be` (git ls-remote).
- GitHub open PR list returned no open PRs. No dependency PR identified.
- Shared root remains at `9145a79`, with unrelated untracked handoffs, temporary directories, worktrees, plans and user documents. Nothing there was edited or cleaned.
- New managed worktree: `C:/Users/RTA/.codex/worktrees/lodging-room-popup/ogn_ROOM`.
- Branch: `codex/lodging-room-popup`; HEAD is the verified baseline above.
- Production revision/traffic and past acceptance results are handoff assertions, not reverified Cloud Run facts in this audit. No infrastructure or production data operation performed.
- Earlier closeout worktree and evidence preserved. Its clean/commit state was not independently audited in this phase.

## Architecture and surface inventory

| Surface / route | Template and presentation | Data and actions |
| --- | --- | --- |
| `/lodging/about/` | `templates/lodging/lodging_about.html`; `static/css/lodging_about.css`, `lodging_about_ux23.css`, `lodging_about_ux24.css`, `lodging_about_ux27.css`; `static/js/lodging_about_explorer.js` | `bookings/lodging_views.py::lodging_about`; rates from `lodging_about_data.py`; JS duplicates static room inventory. No live room/bed query. Current selected-room CTA leads to gallery. |
| `/lodging/` | `templates/lodging/lodging_index.html`; shared `static/css/app.css` | `lodging_index`: allocated, active cohorts filtered by `cohort_self_booking_status`. Links to cohort portals; no selected-room forwarding. |
| `/lodging/c/<slug>/` | `templates/lodging/student_portal.html`; `static/css/lodging_booking_ios27.css`; inline dialog JS | `_build_portal_context`: cohort rooms and CourseStudentLodging, generic occupied labels, cohort.beds_per_room. Existing native booking dialog. |
| `/lodging/c/<slug>/book/` | POST from booking dialog | `lodging_book_bed` -> `assign_lodging_bed`; room PK and bed_number; transactional locks and membership/status checks. Errors restore dialog values via session. |
| `/lodging/c/<slug>/reservation/<token>/` and `/pass/<student_id>/` | `templates/lodging/student_pass.html` | Existing self-service access/pass logic; cancellation, checkout and release remain unchanged. |
| `/lodging/request/` | `templates/lodging/general_request.html` | `bookings/lodging_operations.py::general_request`, GeneralRequestForm; ModelChoiceField room; dates and contact data -> `request_general_lodging` -> Booking Core. |
| `/lodging/request/status/<token>/` | `templates/lodging/general_request_status.html` | PublicLodgingAccess; private/no-store token status page. A request is not necessarily confirmed. |
| `/lodging/workspace/` | `templates/lodging/workspace.html`; `static/css/lodging_operations.css` | Staff-only operations in lodging_operations.py; existing bed-first assignment context. Only room-selection styling is a candidate, not a backoffice redesign. |
| Login / arrival | existing shared login shell and `templates/lodging/checkin.html` | Existing authentication/access policy; no new mandatory login for publicly available lodging journeys. |

Route owner: `bookings/urls.py`. Resource identity: database PK; code is a unique display/domain code, not necessarily the visible three-digit plan number. Mapping must be explicit and unambiguous and tested against existing seed/inventory conventions before implementation.

## Browser observation

Visited the production About page as guest, expanded the floor explorer, and selected room 423 using its room picker. The visible selection is room 423, floor 4, fan, capacity 2, middle zone. A floating translucent inspector appears; its CTA is “ดูบรรยากาศห้องพัก”, not booking. There is no live availability in this inspector. This verifies the present UI, not a completed booking journey.

The current About page includes cool white/blue shell styling and glass effects; the architectural plan has cream, teal and khaki. User instructions for restrained cream/teal/khaki take precedence over copying all existing About effects. CSS has accumulated override layers; changes must account for final cascade, not only the initial token block.

## Architectural conflicts to resolve before R1 implementation

1. Availability has no universal meaning without context. Student bed availability is cohort-specific; general room availability requires dates and must include Booking Core conflicts and cohort allocation. Never label a room free from capacity minus all historical occupants.
2. Plan data is static and has no authoritative database identifier. Unknown/ambiguous mappings must disable booking with an explicit explanation, never guess an ID from 423.
3. Existing general requests reserve room resources and follow approval policy; they do not select an individual student bed. Preserve separate actions and confirmation wording.
4. Public About currently has no cohort dependency. New live reads must expose only safe room and aggregate status information, retain a static informative fallback, and handle absent inventory/cohorts without breaking About.

Proposed resolution: open the dialog immediately with basic room information; ask for the existing cohort or stay dates before asserting availability. Course path keeps room PK through cohort choice and opens that room's bed choice directly. General path prefills the existing room ModelChoiceField and keeps date validation and request submission semantics. If the selected cohort does not contain the room, explain this and offer eligible cohorts rather than silently choosing another room. No schema/auth/permission rewrite is required.

## Proposed screen and scoped implementation

Dialog: “ห้อง 423” / floor and zone / status explicitly tied to selected cohort or dates / total, used and free beds when meaningful / existing journey choice / primary booking-entry CTA. Desktop centered native dialog; mobile bottom sheet, scrollable body, safe-area footer. Close button, Escape, backdrop, focus trap and focus return; no stacked dialogs. Keep floor-plan selection outline and readable labels. Use native dialog already present in student_portal as the implementation pattern.

Expected edits, subject to mapping verification:

- `bookings/lodging_views.py`: room read context, room forwarding and portal selection.
- `bookings/lodging_operations.py`: validated general-request prefill only.
- `bookings/urls.py`: read endpoint only if lazy loading is selected.
- `templates/lodging/lodging_about.html`, `lodging_index.html`, `student_portal.html`, `general_request.html`: selection, dialog and context forwarding.
- `static/js/lodging_about_explorer.js`: immediate dialog, loading/error/retry and focus handling; retain existing plan topology.
- `static/css/lodging_about_ux27.css`, `lodging_about.css`, `lodging_booking_ios27.css`: restrained palette and responsive dialog alignment; avoid another overlapping design system.
- `templates/lodging/student_pass.html`, `general_request_status.html`, `checkin.html` and scoped workspace CSS: visual alignment only after core flow passes.
- New focused `bookings/tests_lodging_room_popup.py`; update affected existing visual assertions to the user-approved behavior with explicit rationale.
- `tests/a11y/room-plan.spec.js`: dialog, keyboard and responsive coverage.

Service/model rules are reuse targets, not planned rewrites. Online Teaching, global admin, production configuration, migrations, auth and permissions are out of scope.

## Regression and QA plan

- Verify exact plan-number -> Resource mapping before exposing booking links.
- Test inactive/unmapped rooms, no cohorts, full and partial rooms, invalid/foreign room PK, closed/released cohorts, forged client state, stale availability and conflicts.
- Ensure no roommate PII in rendered HTML/JSON; count queries and avoid per-room database loops.
- Preserve transaction locks, booking exclusions, allocation_status/is_active meanings, checkout/release, phone normalization, student passes and public throttling.
- Target lodging, lifecycle, P2 checkout, staff operations, readiness, service gateway and visual journey tests; run Django system check, migration drift check, full pytest, then diff check.
- Browser QA on local synthetic data: guest, student and authorized staff; 320, 360, 375, 390, 430, 768, 1280, 1440 widths. Open/close, click/touch/keyboard, long content, text scaling, reduced motion, sticky CTA, browser Back, landscape and form keyboard.
- Reuse Playwright + axe infrastructure. Existing plan tests assert raised 3D behavior; revise only assertions that intentionally change, preserve geometry and accessible interaction coverage.
- Exclude screenshots, .qa files, temporary data and browser artifacts from commits. No deletion of old evidence.

## Gate status / handoff

R0 source and live public UI inspected. No application code changed. This document is the only new file. No implementation commit, push or PR. No tests, migration checks, full regression or role/mobile acceptance run in this audit; no PASS claim for R1-R9. CI not run because no PR exists. Production untouched by this task.

Next: implement R1-R4 after resolving the context-dependent availability design above, then scoped R5 and complete R6-R9. The phase boundary is retained because the supplied handoff requests R0 first and a report before implementation when an architectural conflict is found.

Continuation prompt:

Read this R0 audit and the SIGROOM workflow skill. Reverify Git/GitHub and worktree status. Use codex/lodging-room-popup at C:/Users/RTA/.codex/worktrees/lodging-room-popup/ogn_ROOM, baseline edbe58fc7a2b3513c4ae76f9c81c1175f94a34be. Implement a restrained cream/teal/khaki room popup and booking entry using the proposed cohort/date-context resolution, authoritative Resource PKs and existing services. Verify mapping before coding; preserve existing public access and all booking/bed/release invariants. Complete R1-R9 and required local test/browser gates before commit/push/PR. Do not merge, deploy, alter production data or remove previous evidence. No implementation or test PASS exists yet.

## R1–R9 closeout — 2026-09-29

Status: local implementation and QA complete; ready for review/PR gate. No commit, push, PR, merge or Production deploy has been performed in this worktree.

- Room identity is authoritative and conservative: floor-plan numbers map only to a unique active lodging `Resource` with matching code/floor. Unknown, ambiguous, inactive or mismatched rooms remain non-bookable; no guessed Production mapping is introduced.
- The About popup loads safe live room metadata and aggregate course availability only. It does not expose guest names, phone numbers or roommate PII. Full/closed/unavailable states suppress the course-booking CTA and explain the state.
- Availability is tied to the selected active allocated course and reuses the existing `CourseStudentLodging`/`beds_per_room` meaning instead of inventing a context-free room vacancy count.
- The selected authoritative room PK is preserved into the course portal and the general lodging-request form. Both paths validate the room again server-side rather than trusting query-string state.
- Dialog behavior covers loading/error/retry, stale-response protection, Escape/backdrop close, focus trap/restore, reduced motion and mobile layouts. Shared lodging theme alignment is scoped to lodging/login-arrival surfaces.
- One WCAG AA defect was found during Browser Gate: `.lodging-capacity-text` inherited `#7d8998` on the cream surface (3.49:1). The lodging theme now overrides `--dim` with `#536764`; the affected mobile route and the complete browser suite pass afterward.
- Real-flow browser QA used only the isolated `test_ogn_room` database. Synthetic `DORM-425` / `หลักสูตร Browser QA` data verified popup → preserved room → bed 2 → successful reservation/pass, and the general-request path preselected the same room. No Production data was created or changed.
- The shared/root local database was observed to have an older schema and was deliberately left untouched. Browser QA instead used a migrated test database.

Final local gates:

- `python manage.py check` — PASS, 0 issues.
- `python manage.py makemigrations --check --dry-run` — PASS, no changes detected.
- Focused popup/accessibility/showcase/isometric pytest — **108/108 PASS** after clean recreation of the isolated test DB.
- Full pytest regression — **662/662 PASS**.
- Playwright + axe desktop/mobile Browser/A11y Gate — **54/54 PASS** after the contrast fix.
- Mobile public-route rerun for the contrast defect — **11/11 PASS**.
- Real browser booking flow `DORM-425` → bed 2 and general-request room prefill — PASS on isolated test data.
- `git diff --check` — **PASS** after closeout documentation update.

Next gate: review the final exact diff and intended-file list, then commit/push/open a PR only after approval. Merge and Production deploy remain separate approvals.
