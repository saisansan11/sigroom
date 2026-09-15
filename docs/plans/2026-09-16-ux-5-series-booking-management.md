# SIGROOM UX-5 Implementation Plan — Series Booking Management

## Status
`LOCAL VERIFICATION PASS — READY FOR PR`

## 1. Verified base
- Integration base: `origin/feat/lodging-v5-2`
- Base SHA: `b5daf47693d4b15ae63c752c874e6f099ffe4e2a`
- Branch: `feat/ux-5-series-management`
- UX-3 My Bookings and UX-4 Booking Detail are already merged into this base.

## 2. Evidence and problem
The requester-facing `templates/bookings/series_detail.html` still rendered its occurrence list inside the generic `.table-wrap` container. Shared CSS applies `.table-wrap table { min-width: 42rem; }`, so the series-detail page fell back to inner horizontal scrolling on narrow mobile screens.

This was inconsistent with the already-merged UX-3 treatment of My Bookings, where the same table-on-mobile friction was removed without duplicating business logic or mobile markup.

## 3. Goal
Make a booking series easy to scan and manage at 360–430 px while preserving the existing semantic desktop table at 768 px and above.

Mobile hierarchy:
1. occurrence number + current status
2. date/time
3. decision reason / skip note
4. allowed actions

Skipped dates remain clearly distinct from real booking occurrences.

## 4. Scope
- Add presentation-only semantic hooks to `series_detail.html`.
- Keep exactly one canonical occurrence table and the existing occurrence/skip loops.
- Add a scoped mobile treatment under `@media (max-width: 47.99rem)` so exact 768 px remains desktop/table behavior.
- Override the generic `42rem` minimum width only for the series-detail occurrence table.
- Make per-occurrence actions and the destructive series action usable with touch targets of at least 44 px.
- Keep summary status flags readable without horizontal page overflow.
- Preserve visible keyboard focus and desktop table semantics.
- Add UX-5 regression tests.

## 5. Explicit non-goals / invariants
Do not change:
- `bookings/views.py`, `bookings/services.py`, `bookings/series_services.py`, models, URLs, migrations, or settings;
- who may view a series;
- the `can_cancel` computation;
- the existing per-occurrence cancellation condition in the template;
- cancellation endpoints or confirmation wording;
- approval, conflict, hold, privacy, or recurring-series business rules.

SRS FR-13 remains authoritative: a booking series and its occurrences are separate entities, and an individual occurrence can be managed independently without changing other occurrences.

## 6. Automated acceptance — observed 2026-09-16
- `bookings/tests_ux5.py`: **5 passed**.
- UX-3 + UX-4 regression: **12 passed**.
- `manage.py check`: **System check identified no issues (0 silenced)**.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.
- Full `pytest --tb=short -q`: **237 passed**.
- `git diff --check`: **PASS**.
- Warnings observed are existing environment/framework warnings: pilot `DJANGO_SECURE=0`, Django 6 URL-field transition, and no collected `staticfiles/` directory in the isolated worktree.

## 7. Real browser QA — observed 2026-09-16
Authenticated requester route: `/series/<uuid>/`, using a dedicated local UX5 Browser QA fixture with two future occurrences and one skipped date.

Viewport results:
- **360 px**: mobile grid active; no page or inner-table horizontal overflow; summary flags 2-column; actions computed `min-height: 44px`; skipped row dashed/distinct.
- **390 px**: same mobile behavior; no overflow; `min-height: 44px` confirmed.
- **430 px**: same mobile behavior; no overflow; `min-height: 44px` confirmed.
- **768 px**: mobile media query is false; semantic `table` / `table-row` behavior restored; no overflow.
- **1280 px**: semantic desktop table; no overflow.
- **1440 px**: semantic desktop table; no overflow.

Interaction/accessibility checks:
- clicked the first occurrence `ดู` action and successfully navigated to the real booking detail route, then returned to series detail;
- single-occurrence and remaining-series cancel controls preserved their existing POST endpoints and confirmation text; destructive actions were intentionally not submitted during visual QA;
- keyboard Tab navigation produced a visible solid focus outline and focus shadow on the `ดู` action;
- no clipped/overlapping series content was observed in the tested matrix.

Live CDP console/network capture during reload found no UX-5 JavaScript exception or changed-resource failure. Two unrelated baseline shell issues remain and are intentionally deferred from this scoped PR:
1. deprecated `apple-mobile-web-app-capable` meta warning;
2. `/favicon.ico` returns 404.

## 8. PR contract
After local gates pass:
- commit and push only scoped UX-5 files;
- open a PR to `feat/lodging-v5-2`;
- re-review PR diff/base/head/mergeability/checks;
- write the final UX-5 handoff;
- stop at `READY FOR MERGE` until the user explicitly instructs merge.
