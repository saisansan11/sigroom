# SIGROOM UX-9 — Approver Queue Decision Clarity

Status: PR #31 INITIAL CI PASS — FINAL DOCS CI PENDING

Verified base: `origin/feat/lodging-v5-2` @ `b3d70bfa3a67c77bbdfb0381d4d65790b7aa337a` (PR #30 merged)
Post-merge CI: run `35041991844` PASS
Open PRs at discovery: none
Branch: `feat/ux-9-mobile-operator-clarity`

## Evidence

- `templates/approvals/queue.html` renders three decision-card variants: normal booking, amendment, and booking series.
- Normal booking and amendment cards separate content from consequential actions via `.approval-actions`.
- Series cards instead kept the entire decision form inside `.approval-card-main`; exclusion controls, `reason_excluded`, `reason_reject`, and both action buttons were visible in the content flow at once.
- Shared responsive CSS already stacks `.approval-card` below 50rem, but it did not normalize the decision hierarchy between normal/amendment and series cards.
- On narrow mobile this created excess scanning and made the primary decision point less obvious, even though permissions and business rules were correct.

## Objective

Make all approver queue cards follow a consistent decision hierarchy, especially on mobile: request context first, optional review details second, decision controls last. Preserve every approval endpoint, server-side rule, status/SLA behavior, CSRF token, form field name, and validation contract.

## Invariants

Preserve exactly:

- queue permission and primary/backup/SLA eligibility behavior;
- normal approve endpoint and reject endpoint;
- amendment approve/reject endpoints;
- series endpoint `{% url 'approvals:series_decide' booking.series_id %}`;
- all forms remain POST and retain CSRF;
- series field names `excluded`, `reason_excluded`, `reason_reject`, and submit `action=approve|reject`;
- server-side requirements for rejection/exclusion reasons;
- series occurrence IDs and checkbox values;
- normal/amendment rejection reason `required maxlength="500"` and rejection reason datalist;
- status/SLA/urgent flags and link destinations;
- no model/service/view/form/URL/settings/migration/business-rule changes.

## Implementation

1. `templates/approvals/queue.html`
   - added queue/card/action scoped hooks;
   - retained current semantic article/form/details structure;
   - wrapped the series form in a dedicated decision panel after request context without changing form ownership or endpoint;
   - kept occurrence exclusion under progressive-disclosure `<details>`;
   - grouped the two series reason inputs into a responsive reason grid;
   - kept approve/reject as the final action row;
   - preserved all exact form names, URLs, button values, conditions, and CSRF.
2. `static/css/app.css`
   - added scoped `UX-9 Approver Queue Decision Clarity` styles;
   - mobile refinements use `@media (max-width: 47.99rem)` while exact 768px and wider keep existing base behavior;
   - queue action blocks are full-width on mobile, action controls are >=44px, long Thai text wraps, and reason fields/details do not overflow;
   - context, optional review/exclusion controls, and final decision row are visually separated;
   - no `:has()`.
3. `approvals/tests_ux9.py`
   - guards normal/amendment/series URLs and POST+CSRF contracts;
   - guards exact series field names/action values and occurrence IDs;
   - verifies outsider/primary/backup queue access behavior;
   - guards queue-scoped hooks and mobile CSS contract.

## Verification evidence

Runtime pinned to Python **3.12.10**.

- Focused UX-9 + approvals regression: **18 passed, 8 warnings**.
- `uv run manage.py check`: **PASS — 0 issues**.
- `uv run manage.py makemigrations --check --dry-run`: **PASS — No changes detected**.
- Full regression: **255 passed, 124 warnings in 79.24s**.
- `git diff --check`: **PASS** after removing one trailing blank line from the CSS block.
- Browser QA as Approver at **360, 390, 430, 768, 1280, 1440 px: PASS**.
  - all sizes: no page/card/series-panel horizontal overflow;
  - 360/390/430: one-column reason fields and full-width actions;
  - 768: UX-9 mobile query inactive; existing responsive card behavior retained; reasons are two columns;
  - 1280/1440: desktop card row retained; reasons are two columns;
  - minimum measured decision-control height ~51.4px mobile / ~53.5px desktop;
  - occurrence `<details>` opens by click and does not overflow;
  - focused approve button has visible solid 2px outline;
  - long Thai title stress at 360px does not overflow;
  - visual review of 360/1440 and dedicated series screenshots passed;
  - app CSS/Pico/HTMX/fonts loaded 200; simple static QA server alone produced expected `manifest.webmanifest`/`favicon.ico` 404s.
- No destructive approve/reject action was submitted during Browser QA.

## Initial GitHub verification

- PR: **#31**
- implementation HEAD: `a661a3eacff7ffdb24e599e77047b6f78114f111`
- GitHub Actions run: `35046866327`
- Repository checks: PASS
- Critical regression: PASS
- Full regression: PASS
- Security audit: PASS
- aggregate `PR Safety Gate`: PASS
- PR state: `MERGEABLE / CLEAN`
- a docs-only final evidence update will trigger one final CI run.

## Implementation workflow note

Two Antigravity bridge attempts were made from the verified base, but both stalled before creating any source changes. The owned agent processes were stopped, and implementation was completed through a tightly scoped lnwjud fallback in the isolated UX-9 worktree. The canonical worktree was not modified.

## Out of scope

- changing approval rules or SLA logic;
- changing what constitutes approval/rejection/exclusion;
- auto-filling or conditionally requiring fields client-side;
- queue sorting/filtering/search;
- booking/series detail redesign;
- deployment/security policy changes.

## Definition of Done

Final PR HEAD must pass local gates, Browser QA, and GitHub aggregate `PR Safety Gate`. Merge still requires explicit user instruction.
