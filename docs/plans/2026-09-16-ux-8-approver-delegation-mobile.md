# SIGROOM UX-8 — Approver Delegation Mobile Clarity

Status: LOCAL VERIFICATION PASS — READY FOR PR

Verified base: `origin/feat/lodging-v5-2` @ `b07a7e7b49ffac618f7b65cf583fdb7bf28e0bb6` (PR #29 merged)
Open PRs at discovery: none
Implementation branch: `antigravity/sigroom-ux8-base/20260916-062957-e1d866`

## Evidence

- `templates/approvals/delegation.html` was the remaining generic `.table-wrap` operational table on the newly merged integration base.
- Shared CSS enforces `.table-wrap table { min-width: 42rem; }`, so the delegation list could require horizontal scrolling on narrow mobile.
- The page contains the consequential POST action `ยกเลิก` for non-ended delegations, making action visibility and touch usability important.

## Objective

Make the approver delegation list mobile-first without changing approval/delegation semantics. Below 768px, keep one semantic table but present rows as readable stacked cards. At exactly 768px and above, preserve the existing desktop table.

## Invariants preserved

- only primary approvers can reach delegation management;
- creation form/service behavior unchanged;
- owner-scoped delete lookup unchanged;
- delete endpoint remains POST-only;
- CSRF retained;
- template cancellation condition remains `item.end_date >= today`;
- status mapping/display text unchanged;
- delete endpoint remains `{% url 'approvals:delegation_delete' item.id %}`;
- confirm text remains `ยืนยันยกเลิกการมอบหมายนี้ใช่หรือไม่`;
- button copy remains `ยกเลิก`;
- no model/service/view/form/URL/settings/migration/business-rule changes.

## Implementation

1. `templates/approvals/delegation.html`
   - added page-scoped responsive hooks only;
   - retained one semantic table and `<thead>`;
   - added row/cell classes for delegate, date range, status, action, ended state, and empty state;
   - preserved all existing Django conditions/actions/copy.
2. `static/css/app.css`
   - added scoped `UX-8 Approver Delegation Mobile Clarity` rules under `@media (max-width: 47.99rem)`;
   - overrides generic 42rem min-width only for this table;
   - stacks rows as cards with clear labels and prominent status;
   - full-width cancellation action with at least 44px touch target;
   - visually distinguishes ended rows and suppresses the empty action cell on mobile;
   - no `:has()`; exact 768px and wider remain desktop table.
3. `approvals/tests_ux8.py`
   - guards one semantic table and responsive hooks;
   - verifies primary/non-primary access contract;
   - verifies own active/future delegation retains POST cancel form, CSRF, exact endpoint/copy/confirm;
   - verifies ended delegation has no cancel action;
   - verifies owner scope, POST-only behavior, exact mobile breakpoint/scoped CSS and hidden empty action specificity.

## Verification evidence

- Antigravity implementation reviewed independently; first review found two issues: invalid test fixture violating `one_primary_approver_per_resource` and a trailing blank line detected by `git diff --check`; both were repaired by Antigravity and re-reviewed.
- Focused UX-8 + approvals regression: **16 passed**.
- `uv run manage.py check`: **PASS — 0 issues**.
- `uv run manage.py makemigrations --check --dry-run`: **PASS — No changes detected**.
- Full regression: **251 passed, 122 warnings**.
- `git diff --check`: **PASS** after repair.
- Browser QA as Approver at 360, 390, 430, 768, 1280, 1440 px: **PASS**.
  - 360/390/430: no page/table/row overflow, table min-width overridden to 0, rows render as cards, ended action cell hidden.
  - exact 768 and wider: desktop table preserved.
  - cancel button measured ~51px high on mobile.
  - keyboard Tab reached cancel button with visible focus outline; destructive cancel action was not submitted.
  - safe navigation `กลับคิวอนุมัติ` reaches `/approvals/` and delegation page can be revisited without state change.
  - changed-page resources return 200; baseline `favicon.ico` returns 404 and is unrelated to UX-8.

## Out of scope

- approval queue redesign;
- delegation service/model/form rules;
- editing existing delegation dates or delegate;
- deployment/infra/security policy changes;
- unrelated baseline favicon/browser warnings.

## Definition of Done

Final PR HEAD must pass GitHub aggregate `PR Safety Gate`. Merge still requires explicit user instruction.
