# SIGROOM UX-11 — Reports Dashboard Mobile Clarity

Status: LOCAL VERIFICATION PASS — READY FOR PR
Date: 2026-09-16

## Verified base

- Repository: `saisansan11/sigroom`
- Base branch: `feat/lodging-v5-2`
- Verified base commit: `69b15bee511740d96adae03cc972b8f72bbb4de5` (merge of PR #32 / UX-10)
- Post-merge CI run: `35052211010` SUCCESS
- UX-11 branch: `feat/ux-11-reports-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux11-reports-mobile`

## Evidence / problem

`templates/reports/dashboard.html` was the remaining report page with five generic `.table-scroll` tables. Shared table CSS enforced a wide minimum width, so on 360–430px phones a user could need horizontal scrolling to read each report. The filter form already stacked responsively and was preserved.

## Goal

Make all five monthly report sections readable and navigable on phones while preserving one canonical semantic table per report and preserving desktop tables at 768px and wider.

## Implemented scope

### Template

`templates/reports/dashboard.html`:
- preserves exactly five semantic report tables and the existing report loops/values;
- adds report-scoped wrapper/table/row hooks;
- adds visually hidden captions and `data-label` field labels for mobile cards;
- keeps filter names/values and GET behavior unchanged;
- keeps all five CSV query report keys and query parameters unchanged;
- keeps empty copy `ไม่มีข้อมูล` unchanged.

### CSS

`static/css/app.css` adds only `/* UX-11 Reports Dashboard Mobile Clarity */` under `@media (max-width: 47.99rem)`:
- resets generic table minimum width only for `.report-table`;
- rows become one-column cards below 768px;
- table headers are visually hidden using an accessibility-safe pattern;
- cells use `data-label` pseudo-labels;
- long Thai text and identifiers wrap safely;
- CSV download CTA is full-width on mobile with `min-height: 44px`;
- empty rows receive dashed, non-color-only presentation;
- exact 768px and wider retain the original desktop table behavior;
- no JavaScript and no `:has()`.

### Tests

Added `reports/tests_ux11.py` to protect:
- five semantic report tables and scoped hooks;
- report captions and mobile labels;
- five exact CSV report keys;
- unchanged reports permission/build/audit contracts in the view;
- report-scoped `47.99rem` CSS, min-width reset, wrapping and >=44px CTA;
- no `:has()`.

## Business/security invariants not changed

- `reports/views.py` and `reports/services.py` are untouched.
- login/permission boundary remains `can_access_reports`.
- report calculations, room scope, unit filters and month parsing are unchanged.
- CSV content, BOM, report keys and `reports.export` audit behavior are unchanged.
- no model, migration, URL, settings, booking or lodging rule changes.

## Implementation-agent outcome

Antigravity CLI was attempted after the plan was written. It remained blocked waiting on a baseline test/background task and produced no source changes. The agent process was cancelled, then the approved scoped lnwjud fallback implemented the plan in the isolated branch. Codex was not used.

## Automated verification

Environment for local Django gates: Python **3.12.10**, canonical local PostgreSQL environment loaded from `F:\ogn_ROOM\.env` without printing secrets, `DJANGO_DEBUG=1`, `DJANGO_SECURE=0`.

- First plain `uv run` attempt was classified as an environment failure: Python 3.14 was selected and PostgreSQL credentials were absent. No code/test weakening was done.
- `reports/tests_ux11.py reports/tests.py` → **9 passed, 4 warnings in 19.49s**.
- `manage.py check` → **System check identified no issues (0 silenced)**.
- `manage.py makemigrations --check --dry-run` → **No changes detected**.
- full regression → **262 passed, 125 warnings in 105.41s**.
- `git diff --check` → PASS.
- warnings are known local/framework warnings (isolated worktree has no collected `staticfiles/`, Django 6 URLField transition).

## Browser QA

QA used the real Django report template rendered via an authenticated disposable test-database custodian fixture, with representative rows for all five reports and deliberately long Thai strings. The test database was torn down after rendering. No production data was touched.

Viewports tested: **360 / 390 / 430 / 768 / 1280 / 1440 px**.

Observed:
- 360/390/430: media query active; five tables render as block/card rows; no page, wrapper, row, or long-cell horizontal overflow; five CSV buttons present; minimum CTA height ≈ **44.05px**.
- 768: media query inactive; tables return to `display: table`, rows to `table-row`, no overflow.
- 1280/1440: desktop tables preserved; no overflow.
- empty-state page at 390: five `ไม่มีข้อมูล` states render correctly with no page overflow.
- real keyboard Tab navigation reached the first CSV CTA after 9 tabs; focus outline `oklch(0.78 0.12 207) solid 2.72727px`, offset `2.72727px`; height ≈ **44.05px**.
- visual + DOM inspection confirmed all five sections, filter form, CSV CTAs and long Thai values are visible in the rendered page.
- runtime reload: **0 console errors, 0 runtime exceptions, 0 failed network loads**.
- changed/required assets (`pico.min.css`, `fonts.css`, `htmx.min.js`, `app.css`) loaded HTTP 200.
- only `manifest.webmanifest` returned 404 from the temporary static QA server; classified as QA-server baseline and unrelated to UX-11.

## QA artifacts — do not stage

Local untracked QA files include:
- `ux11_qa_render.py`
- `ux11_viewports.mjs`
- `ux11_focus.mjs`
- `ux11_runtime_check.mjs`
- `ux11-reports-qa.html`
- `ux11-reports-empty-qa.html`
- `ux11-reports-360.png`
- `ux11-reports-1440.png`

They must not be staged or committed.

## Remaining release steps

1. write the UX-11 handoff;
2. perform final complete diff review;
3. stage only the five scoped files;
4. commit/push `feat/ux-11-reports-mobile`;
5. open PR to `feat/lodging-v5-2` and re-review GitHub diff;
6. require aggregate GitHub `PR Safety Gate` SUCCESS on the final PR HEAD;
7. report **READY FOR MERGE — NOT MERGED** only after PR is `OPEN / MERGEABLE / CLEAN` and every required check is green.

## Merge rule

Do not merge the UX-11 PR without a new explicit user instruction.
