# SIGROOM UX-10 — Usage Status Mobile Clarity

Status: PR #32 INITIAL CI PASS — FINAL DOCS CI PENDING

Verified base: `origin/feat/lodging-v5-2` @ `842b20dc806636b6365c1f1e1b617d6a070cab78` (PR #31 merged)
Post-merge CI: GitHub Actions run `35047943009` PASS, including aggregate `PR Safety Gate`
Open PRs at discovery: none
Implementation branch: `feat/ux-10-usage-status-mobile`

## Evidence / problem

`templates/usage/list.html` was a consequential custodian workflow that still used the shared generic `.table-scroll` layout. Shared CSS applies `.table-scroll table { min-width: 42rem; }`, so narrow phones had to horizontally scroll to reach the final `บันทึก` column containing the operational actions `ใช้งานแล้ว` and `ไม่มาใช้`.

This page was prioritized over read-only reporting tables because changing a usage status writes audit history and, for `no_show`, notifies the requester. The existing server-side behavior was already correct; UX-10 changes action visibility and scanability only.

## Objective

Make the custodian usage-status list readable and decision-ready on mobile without horizontal scrolling, while retaining one canonical semantic table and preserving desktop table behavior at 768px and wider.

### Mobile (< 768px)

- Present each usage row as a compact operational card using the same canonical table markup.
- Surface current status first, then time, room, and requester/unit context.
- Keep `ใช้งานแล้ว` / `ไม่มาใช้` actions visible without horizontal scrolling when the change window is open.
- Make action targets at least 44px high and easy to distinguish.
- Clearly show `พ้นกำหนดแก้ไข` when the server marks the row closed.
- Long Thai room/requester/unit content wraps without page or row overflow.

### Desktop (>= 768px)

- Preserve the semantic table and existing information density.
- Do not alter global `.table-scroll` behavior for reporting or unrelated pages.

## Business / security invariants preserved

- `usage_list` remains protected by `can_manage_usage`; non-custodians remain forbidden.
- `usage_update` remains `@require_POST`.
- update route remains `{% url 'usage:update' booking.pk %}` / `usage/<uuid:id>/status/`.
- every update form retains CSRF.
- submitted status values remain exactly `used` and `no_show`.
- existing disabled-state conditions remain tied to `booking.usage_status`.
- action visibility remains controlled by `booking.usage_change_open` as computed server-side.
- the editable window remains after the booking ends and through the use date + 3 days.
- only approved bookings and allowed usage states remain editable.
- displaced / room-unavailable records remain non-editable by service rules.
- audit and requester notification behavior remain in `usage/services.py` unchanged.
- no model/service/view/URL/settings/migration/business-rule changes.

## Implementation

1. `templates/usage/list.html`
   - added page-scoped wrapper/table/row/cell/form/button hooks;
   - retained exactly one semantic table, existing `<thead>`, caption, loop, conditionals, action URL, CSRF, button names/values/copy, disabled conditions, and empty state;
   - added only an editable-vs-closed row presentation hook.

2. `static/css/app.css`
   - added scoped `UX-10 Usage Status Mobile Clarity` rules under `@media (max-width: 47.99rem)`;
   - resets the shared 42rem table minimum width only for this usage table;
   - visually hides the header accessibly on mobile and renders rows as stacked operational cards;
   - adds mobile pseudo-labels for time, room and requester/unit;
   - keeps status prominent and actions in a two-column grid;
   - action targets have `min-height: 44px`; long Thai text wraps safely;
   - closed rows use a dashed/soft visual treatment;
   - no `:has()` and no JavaScript.

3. `usage/tests_ux10.py`
   - guards one-table semantics and UX-10 hooks;
   - guards the existing POST endpoint, CSRF, exact `used` / `no_show` values, copy and disabled-state behavior;
   - verifies custodian access and outsider denial;
   - verifies open vs closed rendering;
   - guards exact `47.99rem` breakpoint, scoped min-width reset, >=44px touch contract, wrap-safe CSS and absence of `:has()`.

## Implementation-agent note

Antigravity CLI was attempted first as required by the normal workflow. Headless execution stopped before editing because a `command` permission could not be prompted for and was auto-denied. No Antigravity source changes were produced. The phase then used the approved scoped lnwjud fallback on the isolated branch; Codex was not substituted.

## Automated verification — final code

Local CI-safe environment used PostgreSQL `ogn_room` on `127.0.0.1:5432`, Python 3.12, `DJANGO_DEBUG=1`, `DJANGO_SECURE=0`, and a local-only Django secret.

- Independent diff review: PASS; presentation-only scope confirmed; `usage/views.py` and `usage/services.py` untouched.
- Targeted `uv run pytest -q usage/tests_ux10.py usage/tests.py`: **8 passed, 4 warnings in 9.28s**.
- `uv run manage.py check`: **System check identified no issues (0 silenced)**.
- `uv run manage.py makemigrations --check --dry-run`: **No changes detected**.
- Full regression `uv run pytest -q`: **259 passed, 125 warnings in 74.18s**.
- `git diff --check`: **PASS** after final plan/handoff editing.
- Existing warnings are framework/environment debt only: Django 6 URLField transition and missing isolated-worktree `staticfiles/` directory.

## Browser QA — final code

Persona: disposable local **Custodian**. The real usage template was rendered through Django's authenticated test client using a disposable test-database fixture; no status-changing POST was submitted. Fixture contained:

- editable row currently `ใช้งานแล้ว` (`used` disabled, `no_show` enabled);
- editable row currently `ไม่มาใช้` (`no_show` disabled, `used` enabled);
- closed row showing `พ้นกำหนดแก้ไข` and no update form;
- deliberately long Thai room/requester/unit content.

Viewports tested: **360 / 390 / 430 / 768 / 1280 / 1440 px**.

Results:
- 360 / 390 / 430: mobile media query active; all 3 rows render as grid cards; no page/wrapper/row/room horizontal overflow; 2 action forms, 2 enabled buttons, 2 disabled buttons; closed row has no form; action height about **60.08px**; long Thai content wraps cleanly.
- exact 768 / 1280 / 1440: mobile query inactive; rows are `table-row`; desktop semantic table preserved; no page/wrapper/row overflow.
- Focus ring: an enabled `ไม่มาใช้` button was browser-focused with focus-visible semantics and computed outline `oklch(0.78 0.12 207) solid 2.72727px`, offset `2.72727px`.
- Remote raw-Tab dispatch did not advance focus in this debug transport, so it was not used as PASS evidence; native button focusability plus the browser-observed focus-visible outline were verified instead.
- Runtime: no JavaScript exceptions and no failed page assets; only `favicon.ico` returned 404 under the temporary `python -m http.server`, an expected QA-server artifact unrelated to UX-10.
- Visual inspection at 360px: status-first cards, readable labels, long Thai wrapping, two-button action grid, and visibly distinct closed row all render correctly without clipping.
- Visual inspection at 1440px: existing desktop table hierarchy and density remain intact.

### Browser-environment note

The first QA attempt targeted a temporary server that was no longer listening and returned `ERR_CONNECTION_REFUSED`; that attempt was classified as an environment failure and was not counted. The server was restarted on port 7365, verified HTTP 200, and all viewport/runtime checks above were rerun successfully.

## QA artifacts — intentionally not part of the PR

The isolated worktree contains local untracked QA artifacts such as rendered HTML/screenshots and a temporary render-test file. They must not be staged or committed.

## Out of scope

- changing `recent_bookings_for`, `usage_change_is_open`, `set_usage_status`, auto-used jobs, audit, notifications, permission rules, or the 3-day window;
- adding confirmation dialogs or client-side business validation;
- changing reports dashboard tables;
- changing lodging roster/table presentation;
- changing booking/home task counts;
- models, migrations, deployment or security policy.

## Initial GitHub PR verification

- PR: **#32** — `UX-10: Improve usage status actions on mobile`
- URL: `https://github.com/saisansan11/sigroom/pull/32`
- base: `feat/lodging-v5-2`
- implementation HEAD: `8b66052ea142c7858876f15ff12380b5075b42aa`
- GitHub Actions run: `35050506796`
- Repository checks: **SUCCESS**
- Critical regression: **SUCCESS**
- Full regression: **SUCCESS**
- Security audit: **SUCCESS**
- aggregate `PR Safety Gate`: **SUCCESS**
- PR state after implementation run: **OPEN / MERGEABLE / CLEAN**
- This documentation update creates a new final PR HEAD, so GitHub CI must pass again before READY FOR MERGE.

## Definition of Done

UX-10 is ready for merge only after the scoped files are committed/pushed, the PR diff is re-reviewed, and GitHub aggregate `PR Safety Gate` passes on the final PR HEAD. Merge requires a new explicit user instruction.
