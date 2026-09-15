# SIGROOM UX-6 — Series Preview Mobile Clarity

## Status
`LOCAL VERIFICATION PASS — READY FOR PR`

## Verified base
- Integration branch: `origin/feat/lodging-v5-2`
- Base SHA: `947d762` (PR #27 CI Safety Gate merged)
- Branch: `feat/ux-6-series-preview-mobile`
- Open PRs at start: none.

## Evidence
`templates/bookings/series_preview.html` still wrapped `.series-preview-table` in the generic `.table-wrap`; shared CSS applies `.table-wrap table { min-width: 42rem; }`. Unlike the already-fixed UX-5 series-detail page, this step-4 preview had no mobile override, so narrow phones were forced into inner horizontal scrolling while the requester was deciding which recurring occurrences would actually be created.

## Goal
Make the recurring-booking preview readable and decision-ready at 360–430 px without horizontal table scrolling, while retaining one semantic table and exact desktop table behavior at 768 px and above.

## Scope implemented
- Added presentation-only hooks to the existing single preview table.
- Under `@media (max-width: 47.99rem)`, each preview row becomes a compact stacked card with occurrence/status first and date beneath it.
- Kept the three summary pills readable as a 2-column mobile grid, with the final pill spanning the row.
- Preserved the existing submit/cancel controls and 44 px touch behavior.
- Added UX-6 regression tests.

## Invariants / non-goals
No changes were made to:
- `series_preview` / `series_create` views or services;
- recurrence generation, conflict/blackout checks, privacy masking, free-date hidden fields, or create semantics;
- endpoints, POST method, CSRF behavior, booking permissions, models, migrations, or settings;
- exact 768 px and wider semantic table behavior.

## Automated verification — observed 2026-09-16
The first DB-backed targeted attempt in the isolated worktree failed before tests because the worktree intentionally had no copied `.env`, so PostgreSQL received no password. This was an environment/setup failure, not an application regression. The suite was rerun with explicit local CI-safe DB settings.

Observed final results:
- `bookings/tests_ux6.py + bookings/tests_m4.py + bookings/tests_ux5.py`: **14 passed, 6 warnings**.
- `uv run manage.py check`: **System check identified no issues (0 silenced)**.
- `uv run manage.py makemigrations --check --dry-run`: **No changes detected**.
- full `uv run pytest --tb=short -q`: **240 passed, 114 warnings**.
- `git diff --check`: **PASS**.
- Existing warnings only: Django 6 URLField transition and missing collected `staticfiles/` directory in the isolated worktree.

## Real Browser QA — observed 2026-09-16
A real step-4 preview was rendered through Django's authenticated test client for local seeded requester `somchai`, room `B1-201`, four future weekly occurrences. The preview operation was read-only; no series was submitted or created. The rendered page was opened in managed Chrome and measured with exact CDP viewport overrides.

Viewport matrix:
- **360 px**: mobile media active; no page overflow; no preview-wrapper overflow; table `display:block`, `min-width:0`; rows use the expected two-row grid; summary uses 2 columns; both actions have computed `min-height:44px`.
- **390 px**: same mobile behavior; no page/wrapper overflow; actions 44 px.
- **430 px**: same mobile behavior; no page/wrapper overflow; actions 44 px.
- **768 px**: mobile media false; semantic `table` / `table-row` restored; no page/wrapper overflow.
- **1280 px**: desktop semantic table; no overflow.
- **1440 px**: desktop semantic table; no overflow.

Visual review:
- 360-class mobile view shows each occurrence as a distinct readable card with `ครั้งที่`, status, and `วันที่`; no clipped or overlapping content observed.
- 1440 desktop view preserves the existing summary + semantic table hierarchy and action placement.

Accessibility/runtime checks:
- focus on `ยกเลิกทั้งชุด` and the confirm button produced a visible solid cyan outline (~2.7 px).
- live CDP reload captured **0 network loading failures, 0 JavaScript exceptions, 0 console errors/warnings** for the changed page resources.
- the temporary static QA server naturally returned 404 for dynamic-only `/manifest.webmanifest` and favicon requests in its own access log; CSS, fonts, and HTMX loaded successfully. These QA-server artifacts are unrelated to UX-6 and are not part of the PR.

## PR contract
- Stage only UX-6 implementation/tests/docs; do not stage the generated local QA HTML artifact.
- Commit and push `feat/ux-6-series-preview-mobile`.
- Open PR to protected `feat/lodging-v5-2`.
- Require GitHub **PR Safety Gate** to pass on the final PR HEAD.
- Stop at `READY FOR MERGE` until the user explicitly authorizes UX-6 merge.
