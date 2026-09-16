# SIGROOM UX-11 — Reports Dashboard Mobile Clarity — Handoff

Status: LOCAL VERIFICATION PASS — READY FOR PR
Date: 2026-09-16

## Verified state

- Repository: `saisansan11/sigroom`
- Base branch: `feat/lodging-v5-2`
- Base commit: `69b15bee511740d96adae03cc972b8f72bbb4de5` (PR #32 / UX-10 merged)
- Post-merge CI on base: run `35052211010` SUCCESS
- Branch: `feat/ux-11-reports-mobile`
- Worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux11-reports-mobile`
- Canonical `F:\ogn_ROOM` unrelated dirty work was not reset/cleaned/staged.

## Why UX-11

Live source showed `templates/reports/dashboard.html` was the remaining reporting page with five generic `.table-scroll` tables. The shared table minimum width made report reading on 360–430px devices depend on horizontal scrolling. Filters already behaved responsively, so UX-11 changes only report presentation/readability.

## Files in scope

1. `templates/reports/dashboard.html`
   - preserves five semantic tables and exact report loops/values;
   - adds report-scoped hooks, captions and `data-label` mobile labels;
   - preserves filter GET contracts and exact CSV query report keys.
2. `static/css/app.css`
   - adds scoped UX-11 mobile rules only below `47.99rem`;
   - mobile card rows, wrap-safe cells, full-width >=44px CSV actions, empty-state presentation;
   - desktop 768px+ stays as normal tables.
3. `reports/tests_ux11.py`
   - protects semantic table count, scoped hooks, CSV keys, view/audit contracts, breakpoint and CSS behavior.
4. `docs/plans/2026-09-16-ux-11-reports-mobile.md`
5. this handoff.

## Invariants preserved

- `reports/views.py` untouched.
- `reports/services.py` untouched.
- `can_access_reports` permission boundary unchanged.
- calculations, accessible-room scope, unit/month filters unchanged.
- CSV content/BOM/report keys and `reports.export` audit path unchanged.
- no model/migration/URL/settings/booking/lodging changes.

## Agent execution

Antigravity CLI was attempted first after plan creation. It stalled waiting on baseline/background tests and produced no source edits. The assistant cancelled only that owned process and used the approved scoped lnwjud fallback in the isolated worktree. Codex was not used.

## Automated verification

Python **3.12.10** with canonical local DB environment loaded without exposing secrets.

- Initial plain `uv run` failure: environment-only (Python 3.14 selected; PostgreSQL password absent). No application change resulted from that failure.
- Targeted `reports/tests_ux11.py reports/tests.py`: **9 passed, 4 warnings in 19.49s**.
- Django check: **PASS — 0 issues**.
- Migration drift: **No changes detected**.
- Full regression: **262 passed, 125 warnings in 105.41s**.
- `git diff --check`: **PASS**.

## Browser QA

Real report template rendered using a disposable authenticated Custodian fixture in Django's test database. Representative data covered room usage, cancellation/no-show, approval, preemption and equipment; long Thai values were deliberately included. A second render covered all five empty states. Test DB was torn down.

Tested viewports: **360 / 390 / 430 / 768 / 1280 / 1440**.

Results:
- mobile 360/390/430: all five report tables become card rows; no page/wrapper/row/long-cell horizontal overflow; CTA minimum height ≈ 44.05px;
- 768/1280/1440: media query off; semantic desktop table/table-row display retained; no overflow;
- 390 empty state: five `ไม่มีข้อมูล` rows/cells, no page overflow;
- keyboard: real Tab navigation reached CSV link after 9 tabs with visible 2.72727px focus outline and ≈44.05px height;
- visual/DOM inspection confirmed filter form, all five report sections, five CSV actions and long Thai report values;
- runtime: **0 console errors, 0 exceptions, 0 failed network loads**;
- required assets loaded 200 (`pico.min.css`, `fonts.css`, `htmx.min.js`, `app.css`);
- `manifest.webmanifest` 404 occurs only in the temporary static QA server and is unrelated to changed code.

## Local QA artifacts — never stage

- `ux11_qa_render.py`
- `ux11_viewports.mjs`
- `ux11_focus.mjs`
- `ux11_runtime_check.mjs`
- `ux11-reports-qa.html`
- `ux11-reports-empty-qa.html`
- `ux11-reports-360.png`
- `ux11-reports-1440.png`

## Release pending

- final complete diff review;
- stage only five scoped files;
- commit/push;
- open PR to `feat/lodging-v5-2`;
- verify PR file list/diff;
- require all GitHub `SIGROOM PR Safety` jobs and aggregate `PR Safety Gate` to pass on final HEAD;
- report READY FOR MERGE only after GitHub says `OPEN / MERGEABLE / CLEAN`.

Do not merge UX-11 without a new explicit user instruction.

## Suggested PR

Title: `UX-11: Improve reports dashboard on mobile`

## Next-chat prompt

Continue SIGROOM UX-11 from `feat/ux-11-reports-mobile`. Verify live Git/GitHub state first. Local evidence already observed: targeted 9/9, Django check PASS, no migration drift, full regression 262/262, diff-check PASS, Browser QA at 360/390/430/768/1280/1440 PASS including empty state, keyboard focus, overflow and runtime/network checks. Review complete diff, stage only the five scoped files, commit/push, open PR into `feat/lodging-v5-2`, verify PR diff, wait for final aggregate `PR Safety Gate`. Do not stage QA artifacts and do not merge without explicit approval.
