# SIGROOM UX-6 Handoff — Series Preview Mobile Clarity

## Status
`PR #28 IMPLEMENTATION HEAD GREEN — FINAL DOCS-ONLY CI RECHECK REQUIRED`

## 1. Repository / base
- Repository: `saisansan11/sigroom`
- Protected integration/default branch: `feat/lodging-v5-2`
- Verified base SHA at phase start: `947d762` (PR #27 CI Safety Gate merged)
- UX-6 branch: `feat/ux-6-series-preview-mobile`
- Implementation commit: `10d71c82b1205ae11ff6abf9d7c80e4f14c864fe`
- Open dependency PRs at phase start: none.
- Canonical `F:\ogn_ROOM` was not used for implementation because it contains unrelated stale local UX-3 work.

## 2. PR
- PR: #28
- URL: https://github.com/saisansan11/sigroom/pull/28
- Base: `feat/lodging-v5-2`
- Head: `feat/ux-6-series-preview-mobile`
- Implementation-head state observed after CI: `OPEN / MERGEABLE / CLEAN`
- GitHub Actions run: `35032472256`
- `Repository checks`: SUCCESS
- `Critical regression`: SUCCESS
- `Full regression`: SUCCESS
- `Security audit`: SUCCESS
- aggregate `PR Safety Gate`: SUCCESS

This handoff is intentionally a later docs-only commit, so the final branch tip must be rechecked through `PR Safety Gate` once more before reporting `READY FOR MERGE`.

## 3. Problem / decision
`templates/bookings/series_preview.html` (recurring-booking step 4, before final creation) still used the shared `.table-wrap` table behavior. Shared CSS sets a large table minimum width, so 360–430 px devices could be forced into horizontal scrolling precisely when the requester is reviewing which occurrences are free/conflicting/skipped.

UX-5 had already solved the same class of problem for the post-creation series-detail page. UX-6 applies the same one-canonical-table principle to the preview without copying business logic or creating separate mobile markup.

## 4. Files changed
### Presentation
- `templates/bookings/series_preview.html`
  - adds only semantic hooks: `series-preview-wrap`, `series-preview-row`, `series-preview-index`, `series-preview-date`, `series-preview-result`.
  - preserves one canonical table and all original conditionals/forms/hidden free-date inputs.
- `static/css/app.css`
  - adds scoped `/* UX-6 Series Preview Mobile Clarity */` rules under `@media (max-width: 47.99rem)`.
  - exact 768 px remains desktop semantic table behavior.

### Tests
- `bookings/tests_ux6.py`
  - guards one-table/create/free-date contracts;
  - guards exact status/reason branches;
  - guards mobile breakpoint/scoping/min-width/grid behavior.

### Documentation
- `docs/plans/2026-09-16-ux-6-series-preview-mobile.md`
- `docs/handoffs/2026-09-16-ux-6-series-preview-mobile.md`

A generated `ux6-preview-qa.html` exists only as an untracked local browser-QA artifact. It must never be staged or merged.

## 5. Preserved invariants
No changes to:
- `series_preview` / `series_create` views or services;
- recurrence generation;
- conflict / blackout evaluation;
- free-date hidden inputs or final create semantics;
- permission / privacy behavior;
- models, migrations, URLs, or settings;
- POST / CSRF behavior;
- exact 768 px and wider semantic table behavior.

## 6. Local automated verification
The first DB-backed targeted invocation in the isolated worktree stopped before tests because no `.env` was copied and PostgreSQL therefore received no password. No app/test code was weakened. It was rerun with explicit local CI-safe DB environment values.

Final observed results:
- `bookings/tests_ux6.py bookings/tests_m4.py bookings/tests_ux5.py`: **14 passed, 6 warnings**.
- `uv run manage.py check`: **System check identified no issues (0 silenced)**.
- `uv run manage.py makemigrations --check --dry-run`: **No changes detected**.
- full `uv run pytest --tb=short -q`: **240 passed, 114 warnings**.
- `git diff --check`: PASS.
- staged `git diff --cached --check`: PASS before implementation commit.

Known warnings are pre-existing framework/worktree warnings: Django 6 URLField transition and missing collected `staticfiles/` directory.

## 7. Real Browser QA
A real step-4 preview was rendered through Django's authenticated test client for local seeded requester `somchai`, room `B1-201`, four future weekly occurrences. The preview endpoint was exercised but the final create action was never submitted, so no recurring booking was created.

Managed Chrome / CDP exact viewport results:
- **360**: no page or inner-wrapper overflow; table `block`, min-width `0`; row `grid`; summary 2 columns; both actions ≥44 px.
- **390**: same mobile behavior; no overflow; actions ≥44 px.
- **430**: same mobile behavior; no overflow; actions ≥44 px.
- **768**: mobile query false; semantic `table` / `table-row`; no overflow.
- **1280**: desktop semantic table; no overflow.
- **1440**: desktop semantic table; no overflow.

Visual review:
- mobile cards are distinct and readable (`ครั้งที่` + status, then `วันที่`) with no clipping/overlap;
- desktop retains the existing summary/table hierarchy.

Additional stress/accessibility/runtime evidence:
- injecting a deliberately long Thai conflict reason at 360 px produced no page, row, or result-cell overflow;
- `ยกเลิกทั้งชุด` and the confirmation button both showed a visible solid cyan focus outline (~2.7 px);
- live CDP reload reported **0 loading failures, 0 JS exceptions, 0 console errors/warnings** for changed page resources.
- temporary static QA hosting naturally 404'd dynamic-only manifest/favicon paths; CSS/fonts/HTMX loaded and those QA-host artifacts are unrelated to this PR.

Both local QA servers were stopped after verification.

## 8. GitHub CI evidence
Implementation HEAD `10d71c8` triggered run `35032472256` on PR #28. All five checks passed, including the required aggregate `PR Safety Gate`. Branch protection correctly kept the PR blocked while checks were pending and GitHub reported `CLEAN` after success.

Because this handoff itself is a docs-only branch update, re-run/observe the gate on the new final HEAD before declaring ready.

## 9. Known / deferred items
- Existing Django URLField scheme warning remains framework transition debt.
- Existing staticfiles-directory warning is isolated-worktree environment noise.
- HSTS W005/W021 policy remains intentionally handled by the CI security allowlist from PR #27, not changed in UX-6.
- The local `ux6-preview-qa.html` QA artifact is untracked and must not be staged.

## 10. Next phase after UX-6 merge
Do not assume a preselected UX-7 target. Fetch the newly merged protected integration branch, verify open PRs and live source, then identify the next evidence-based operator/requester friction. Continue to preserve booking/lodging permissions, privacy, conflict and transaction invariants.

## 11. Ready-to-paste next-chat prompt
Continue SIGROOM from protected `feat/lodging-v5-2` after UX-6. Use `F:\ogn_ROOM` only as the canonical repo reference; do not disturb unrelated local stale UX-3 changes. Read `AGENTS.md`, `.agents/skills/sigroom-development-workflow/SKILL.md`, relevant profiles/checklists, SRS/build plan and latest handoff. Fetch/verify live GitHub state first. Confirm PR #28 merge if it has been authorized/merged, then create a new isolated worktree from the new integration HEAD. Identify the next UX friction from live code/evidence rather than guessing. Follow the mandatory full flow including targeted tests, Django/migration checks, full regression, real browser QA where user-facing, independent diff review, PR, and required GitHub `PR Safety Gate`. Never merge without explicit user approval.
