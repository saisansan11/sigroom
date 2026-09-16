# SIGROOM UX-8 Handoff — Approver Delegation Mobile Clarity

Date: 16 Sep 2026
Status: PR OPEN — INITIAL CI PASS; FINAL DOCS CI PENDING

## Verified base

- Repository: `saisansan11/sigroom`
- Protected integration branch: `feat/lodging-v5-2`
- Base commit: `b07a7e7b49ffac618f7b65cf583fdb7bf28e0bb6`
- Base includes merged PR #29 / UX-7.
- No open PR existed at UX-8 discovery.

## Implementation branch

`antigravity/sigroom-ux8-base/20260916-062957-e1d866`

Antigravity CLI performed implementation inside the bridge-owned isolated worktree. The bridge reported `SOURCE_UNCHANGED=True`; the canonical/source worktree was not modified by the agent.

## Scope

UX-8 makes `/approvals/delegation/` usable on narrow mobile without changing approval/delegation business behavior.

Changed source/test files:

- `templates/approvals/delegation.html`
- `static/css/app.css`
- `approvals/tests_ux8.py`
- `docs/plans/2026-09-16-ux-8-approver-delegation-mobile.md`
- this handoff

No models, services, views, forms, URLs, settings, migrations, deployment configuration, or business rules were changed.

## Design decisions

- Retain exactly one semantic table and `<thead>`.
- Below 768px only (`max-width: 47.99rem`), override the generic 42rem table minimum width for the delegation table and render rows as stacked cards.
- Keep exact 768px and wider as the existing desktop table.
- Keep status visually first on mobile, then delegate, date range, and action.
- Active/future cancel action becomes full-width with a >=44px touch target.
- Ended delegations are visually distinguished and their empty action cell is hidden on mobile.
- No `:has()` selector.

## Invariants verified

- page remains restricted to primary approvers;
- non-primary approvers remain denied;
- cancellation remains owner-scoped;
- delete remains POST-only;
- CSRF remains in the form;
- cancellation only renders when `item.end_date >= today`;
- delete URL is unchanged;
- confirm copy remains `ยืนยันยกเลิกการมอบหมายนี้ใช่หรือไม่`;
- button copy remains `ยกเลิก`;
- ended delegation cannot be deleted;
- existing status mapping/display text remains unchanged.

## Review findings and repairs

Independent review found two issues in the first Antigravity output:

1. UX-8 test fixture attempted to create two primary approvers for one resource, violating the real DB constraint `one_primary_approver_per_resource`.
2. `git diff --check` detected a blank line at EOF in `static/css/app.css`.

Both findings were returned to Antigravity. The repair creates a second resource for the second primary approver and removes the whitespace error. All relevant gates were then rerun.

## Verification

- Focused tests: `approvals/tests_ux8.py approvals/tests.py` → **16 passed, 11 warnings**.
- Django system check → **PASS, 0 issues**.
- Migration drift check → **PASS, No changes detected**.
- Full regression → **251 passed, 122 warnings in 69.16s**.
- `git diff --check` → **PASS** after repair.

Known warnings are existing Django 6 URLField transition warnings, missing isolated-worktree `staticfiles/` warning, and local pilot HTTP runtime warning. None were introduced by UX-8.

## Browser QA

Role: primary Approver, using local QA data only. The destructive cancel action was never submitted.

Viewports tested: **360, 390, 430, 768, 1280, 1440 px**.

Results:

- 360 / 390 / 430: no page, wrapper, row, delegate, or date overflow; delegation table min-width resolves to 0; rows use card grid layout; ended action cell is `display:none`; active/future rows retain cancel action.
- 768 / 1280 / 1440: media query is inactive; table remains `display: table` and rows remain `table-row`.
- mobile cancel button height measured about **51px**, above the 44px target.
- keyboard QA: Tab reaches the cancel button; visible focus outline measured as a solid ~2.7px outline.
- safe navigation: `กลับคิวอนุมัติ` successfully navigates to `/approvals/`; returning to `/approvals/delegation/` preserves state.
- runtime resources used by the page load successfully with HTTP 200. `favicon.ico` returns a baseline 404 unrelated to UX-8.

## Local QA data note

A local-only QA primary approver/resource/delegation fixture was created in the developer database to exercise all three display states (`กำลังใช้`, `รอถึงวัน`, `สิ้นสุด`) in a real browser session. It is not source-controlled and does not affect production.

## Release state

After the implementation commit and first GitHub verification:

- implementation commit: `73013c31f251c1e24cbc4c5e0c5e5709573ae2b2`
- PR: **#30 — UX-8: Improve approver delegation on mobile**
- initial GitHub run: `35039818608`
- Repository checks: PASS
- Critical regression: PASS
- Full regression: PASS
- Security audit: PASS
- aggregate `PR Safety Gate`: PASS
- PR state after initial run: `MERGEABLE / CLEAN`
- final docs-only handoff commit will trigger one final CI run before READY FOR MERGE.
- merge remains unauthorized until the user gives an explicit merge instruction.

## Next gate

Commit and push this docs-only handoff update, then require the protected-branch CI to pass again on the new final HEAD. Do not merge without an explicit user merge instruction.
