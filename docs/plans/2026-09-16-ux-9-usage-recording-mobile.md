# SIGROOM UX-9 — Usage Recording Mobile Clarity

Status: IMPLEMENTATION PLAN

Verified base: `origin/feat/lodging-v5-2` @ `b3d70bfa3a67c77bbdfb0381d4d65790b7aa337a` (PR #30 merged; post-merge CI run `35041991844` PASS 5/5)
Open PRs at discovery: none
Planning branch: `feat/ux-9-usage-mobile`

## Evidence

- `templates/usage/list.html` is an operational Custodian page for recording whether a completed booking was actually used or became a no-show.
- It still uses generic `.table-scroll`, whose shared CSS enforces `min-width: 42rem`, so narrow mobile requires horizontal scrolling.
- Each editable row contains two consequential POST actions: `ใช้งานแล้ว` and `ไม่มาใช้`.
- This is higher operational priority than read-only report tables because staff may need to update usage status immediately after room use from a phone.

## Objective

Make the usage-recording list mobile-first below 768px while preserving all usage rules and POST semantics. Keep one semantic table and retain the current desktop table at exactly 768px and wider.

## Invariants

Preserve exactly:

- access remains limited by `can_manage_usage` (Custodian/Superuser behavior unchanged);
- dataset remains `recent_bookings_for`: approved bookings ending today through 3 days back;
- editability remains controlled by `usage_change_is_open` and the existing 3-day rule;
- update endpoint remains `usage:update` / `/<uuid:id>/status/`;
- update remains POST-only;
- CSRF remains present;
- action values remain `used` and `no_show`;
- button copy remains `ใช้งานแล้ว` and `ไม่มาใช้`;
- the button for the current status remains disabled;
- closed rows still show `พ้นกำหนดแก้ไข` and no update form;
- current status badge uses existing `status status-{{ booking.usage_status }}` and display text;
- no changes to services, models, views, URLs, permissions, audit, notifications, migrations, settings, deployment, or business rules.

## Implementation

1. `templates/usage/list.html`
   - add page-scoped hooks to wrapper/table/rows/cells/action form/buttons;
   - keep exactly one semantic `<table>`, caption, `<thead>`, headers, existing Django branches, POST form, CSRF, values, disabled rules, and closed-state copy;
   - add a row hook distinguishing editable vs closed rows using existing `booking.usage_change_open` only.
2. `static/css/app.css`
   - add scoped `UX-9 Usage Recording Mobile Clarity` rules under `@media (max-width: 47.99rem)`;
   - override the generic 42rem min-width only for this table;
   - render each booking row as a readable card ordered: status → date/time → room → requester/unit → action;
   - add compact labels for date/time, room, and requester/unit;
   - allow Thai/long text wrapping without horizontal overflow;
   - make both status actions full-width touch targets >=44px on narrow mobile;
   - visually distinguish closed rows and keep `พ้นกำหนดแก้ไข` clear;
   - no `:has()`; exact 768px and above must remain the current desktop table.
3. `usage/tests_ux9.py`
   - guard one semantic table/caption/thead and UX-9 hooks;
   - verify Custodian page access and outsider denial remain unchanged;
   - verify editable row renders a POST form with CSRF, exact endpoint, exact `used`/`no_show` values, button copy, and current-status disabled behavior;
   - verify update endpoint remains POST-only;
   - verify closed row renders `พ้นกำหนดแก้ไข` and no update form;
   - guard exact breakpoint, table-scoped min-width override, card layout, >=44px actions, closed-row styling, long-text wrapping, and absence of `:has()`.

## Verification

- independent diff review;
- focused `usage/tests_ux9.py usage/tests.py`;
- `uv run manage.py check`;
- `uv run manage.py makemigrations --check --dry-run`;
- full `uv run pytest`;
- `git diff --check`;
- real Browser QA as Custodian at 360, 390, 430, 768, 1280, 1440;
- verify no horizontal overflow, Thai wrapping, editable/current/closed states, >=44px actions, keyboard focus, and safe navigation;
- do not submit state-changing usage actions during Browser QA;
- commit/push/open PR against `feat/lodging-v5-2`, then require aggregate `PR Safety Gate` PASS on final PR HEAD.

## Out of scope

- usage business rules or 3-day window;
- automatic `UPCOMING -> USED` job behavior;
- notifications/audit behavior;
- report dashboard redesign;
- lodging roster redesign;
- unrelated global table refactors.

## Definition of Done

Final PR HEAD passes all local verification gates, real Browser QA, and GitHub aggregate `PR Safety Gate`. Merge still requires explicit user instruction.
