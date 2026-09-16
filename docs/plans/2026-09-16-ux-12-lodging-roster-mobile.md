# SIGROOM UX-12 — Lodging Cohort Roster Mobile Clarity

Status: IMPLEMENTATION PLANNED
Date: 2026-09-16

## Verified base

- Repository: `saisansan11/sigroom`
- Base branch: `feat/lodging-v5-2`
- Base commit: `8e2e8b5c79708e3d16f73108f3ed952a01260e17` (merge of PR #33 / UX-11)
- Post-merge CI run: `35061140304` SUCCESS
- UX-12 branch: `feat/ux-12-lodging-roster-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux12-lodging-roster-mobile`

## Evidence / problem

The live source shows `templates/lodging/cohort_detail.html` still renders the internal student roster inside a generic `.table-responsive-container` with horizontal scrolling. The roster has seven columns (sequence, room/bed, rank/name, unit, phone, booked time, check-in status), which makes 360–430px supervisor workflows harder to scan even though the rest of SIGROOM has been progressively converted to mobile-readable cards.

The page is an internal management surface guarded by `can_manage_cohort`. It intentionally shows staff-facing student information, including phone numbers. UX-12 must improve presentation only and must not alter authorization, the data set, CSV export behavior, lodging allocation rules, public portal privacy, or check-in behavior.

## Goal

Make the cohort roster readable without horizontal scrolling on phones while preserving a single canonical semantic table and preserving desktop table behavior at 768px and wider.

## Scope

### Template

Update `templates/lodging/cohort_detail.html` only for presentation hooks around the roster/export area:

- preserve the existing `{% if students %}` condition and the exact student ordering/data fields;
- preserve all seven roster values, including room/bed, rank/name, unit, phone, booking timestamp and check-in details;
- add a table caption and roster-specific classes/hooks;
- add `data-label` values to cells for mobile card presentation;
- add a roster/export CTA hook without changing the existing export URL;
- preserve all existing share/LINE/QR/edit links and copy-link JavaScript unchanged;
- do not add a second mobile-only copy of the roster.

### CSS

Update `static/css/app.css` with a scoped `/* UX-12 Lodging Cohort Roster Mobile Clarity */` block under `@media (max-width: 47.99rem)`:

- reset horizontal-scroll/min-width behavior only for the cohort roster;
- render each roster row as a readable mobile card while retaining semantic table markup;
- hide the roster table header accessibly on mobile;
- show field labels from `data-label` attributes;
- safely wrap long Thai names, units, phone text, timestamps and check-in metadata;
- make the roster CSV/export action full-width and at least 44px tall on mobile;
- preserve desktop table/table-row/table-cell behavior at 768px and wider;
- no JavaScript and no `:has()`.

### Tests

Add `bookings/tests_ux12.py` to protect:

- one canonical roster table with all seven columns;
- roster classes/caption/mobile labels;
- unchanged `lodging_cohort_export_csv` target;
- `can_manage_cohort` permission boundary: owner/supervisor allowed, unrelated user forbidden;
- rendered student row still contains room/bed, name/rank, unit, phone, booked-at and check-in information;
- mobile CSS is roster-scoped and uses `47.99rem`;
- horizontal-scroll/min-width reset is scoped to the roster;
- long-content wrapping and export touch target >=44px;
- no `:has()`.

### Handoff

After verification add `docs/handoffs/2026-09-16-ux-12-lodging-roster-mobile.md` with observed evidence only.

## Business/security/privacy invariants

Must not change:

- `bookings/lodging_views.py` and `bookings/lodging_services.py` behavior;
- `can_manage_cohort` authorization;
- cohort/student query scope and ordering;
- internal staff roster fields;
- public student pass / portal privacy rules;
- CSV content, CSV endpoint, audit behavior;
- allocation status, room/bed rules, conflict protection, check-in logic;
- models, migrations, URLs, settings, booking rules.

## Out of scope

- changing who can see phone numbers;
- editing, moving or deleting students;
- check-in workflow redesign;
- public lodging portal redesign;
- room-card redesign;
- share/LINE/QR behavior changes;
- search/sort/filter/pagination;
- lodging business-rule changes.

## Verification gates

1. Antigravity implementation in the isolated UX-12 worktree;
2. independent diff review;
3. targeted UX-12 + existing lodging tests;
4. `uv run manage.py check`;
5. `uv run manage.py makemigrations --check --dry-run`;
6. full `uv run pytest -q`;
7. `git diff --check`;
8. real Browser QA at 360 / 390 / 430 / 768 / 1280 / 1440 as an authorized cohort supervisor with representative long Thai data, checking overflow, field readability, CSV CTA, keyboard focus and desktop preservation;
9. rerun relevant tests after any fix;
10. final complete diff review;
11. stage only scoped files, commit and push;
12. open PR to `feat/lodging-v5-2` and re-review GitHub diff;
13. require all `SIGROOM PR Safety` jobs and aggregate `PR Safety Gate` SUCCESS on final PR HEAD.

## Merge rule

Do not merge the UX-12 PR without a new explicit user instruction.
