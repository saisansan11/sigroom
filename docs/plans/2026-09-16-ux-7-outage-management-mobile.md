# SIGROOM UX-7 — Outage Management Mobile Clarity

## Status
`LOCAL VERIFICATION PASS — READY FOR PR`

## Verified base
- Protected integration branch: `feat/lodging-v5-2`
- Base SHA: `bca392d7e4e27699657a8cbc48097c2ca1e6952b` (`Merge pull request #28 ... UX-6`)
- Isolated branch: `feat/ux-7-outage-mobile`
- Canonical `F:\ogn_ROOM` contains unrelated stale UX-3 work and was not edited/reset/cleaned.

## Evidence / problem
`templates/resources/outage.html` was one of the remaining operator pages still using the shared generic `.table-wrap` without responsive page-specific hooks. Shared CSS enforces `min-width: 42rem`, so on 360–430 px screens the custodian had to horizontally scroll to inspect status/reason and reach the operational action `สิ้นสุดก่อนกำหนด`.

This is higher priority than cosmetic cleanup because ending an outage early restores room availability and is an active operational task.

## UX-7 objective
Make the existing-outage list fully usable on mobile while retaining one canonical semantic table and all existing outage rules/actions.

### Mobile (< 768 px)
- Present each outage row as a compact operational card using the same canonical table markup.
- Surface status immediately, then time window and reason.
- Keep the active action `สิ้นสุดก่อนกำหนด` visible without horizontal scrolling.
- Action target must be at least 44 px high.
- Long Thai outage reasons must wrap without page/row overflow.
- Visually distinguish ended-early rows without relying only on opacity/color.

### Desktop (>= 768 px)
- Preserve the existing semantic table presentation and information density.

## Implementation scope
1. `templates/resources/outage.html`
   - add semantic/scoped classes only around the existing list table/rows/cells/action.
   - preserve exactly one table.
   - preserve all existing template conditionals, CSRF, POST endpoint, and button copy.
2. `static/css/app.css`
   - add scoped `UX-7 Outage Management Mobile Clarity` rules under `@media (max-width: 47.99rem)`.
   - do not modify global table behavior.
3. `resources/tests_ux7.py`
   - guard one-table responsive hooks;
   - guard custodian permission and action endpoint/CSRF/button copy;
   - guard ended-early/no-action state;
   - guard exact 768 breakpoint and mobile CSS contract.

## Explicitly out of scope
- `create_outage()` / `end_outage_early()` service behavior.
- outage conflict semantics, booking usage status restoration, notifications, privacy, permissions.
- models, migrations, URLs, settings, transaction behavior.
- adding confirmation dialogs or changing destructive-action semantics.
- redesigning approvals delegation in the same PR.

## Local verification — final code
- Independent diff review: PASS; presentation-only scope confirmed.
- `git diff --check`: PASS after Browser QA fix.
- Targeted `resources/tests.py resources/tests_ux7.py`: **9 passed, 6 warnings**.
- `manage.py check`: **System check identified no issues (0 silenced)**.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.
- Full regression: **244 passed, 117 warnings in 72.94s**.
- Existing warnings are environment/framework debt: LAN `DJANGO_SECURE=0` warning, Django 6 URLField transition, and missing isolated-worktree `staticfiles/` directory.

## Browser QA — final code
Persona: disposable local custodian. The Django authenticated test client rendered the real outage page using a disposable local fixture containing one active outage, one ended-early outage, and a deliberately long Thai reason. Fixture database rows were deleted immediately after rendering. The resulting HTML was exercised in managed Chrome; the destructive POST action was not submitted.

Viewports tested: **360 / 390 / 430 / 768 / 1280 / 1440**.

Results:
- 360 / 390 / 430: mobile media query active, table `display:block`, `min-width:0`, rows are card grids, page/table/row/reason have no horizontal overflow, long Thai reason wraps, active action height ≈ **51 px**, ended row uses dashed border, ended action cell is `display:none`.
- Exact 768 / 1280 / 1440: mobile query inactive, semantic `table` / `table-row` presentation restored, no page/table overflow.
- Actual keyboard Tab focus reached `สิ้นสุดก่อนกำหนด`; visible cyan focus outline ≈ **2.7 px**.
- Changed resources loaded: `app.css` and HTMX present; no `Network.loadingFailed` events and no JavaScript exceptions.
- Static QA server emitted only expected `manifest.webmanifest` / favicon 404 console messages because those app routes do not exist on `python -m http.server`; these are not UX-7 resource failures.

### Browser finding and fix
First browser pass found the ended-early action cell still computed `display:block` on mobile because the initial hide selector had lower specificity than `.outage-table .outage-row > td { display:block }`. The change was sent back to Codex. It was corrected to the more-specific `.outage-table .outage-row-ended > .outage-action-cell { display:none; }`, and a focused regression guard was added. Browser QA and all relevant automated gates were rerun on the final code.

## Required release steps remaining
1. Commit and push only scoped files; do not stage local `ux7-outage-qa.html`.
2. Open PR into `feat/lodging-v5-2`.
3. Re-review PR diff.
4. Require GitHub `PR Safety Gate` green on the final PR HEAD.
5. Merge still requires explicit user instruction.

## Definition of Done
UX-7 is complete only when all required local gates and GitHub CI pass on the final PR HEAD. Merge still requires explicit user instruction.
