# SIGROOM UX-10 — Usage Status Mobile Clarity — Handoff

Status: LOCAL VERIFICATION PASS — READY FOR PR
Date: 2026-09-16

## Verified repository state

- Repository: `saisansan11/sigroom`
- Protected integration branch: `feat/lodging-v5-2`
- Verified base: `842b20dc806636b6365c1f1e1b617d6a070cab78` — merge of PR #31 / UX-9
- Post-merge CI on that base: run `35047943009` PASS including aggregate `PR Safety Gate`
- Open PRs at UX-10 discovery: none
- UX-10 branch: `feat/ux-10-usage-status-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux10-discovery`
- Canonical `F:\ogn_ROOM` unrelated dirty work was not edited/reset/cleaned/staged.

## Problem selected from live source

`templates/usage/list.html` was a remaining consequential operator table still inheriting shared `.table-scroll table { min-width: 42rem; }`. On narrow phones a custodian could need horizontal scrolling to reach the final `บันทึก` column with `ใช้งานแล้ว` / `ไม่มาใช้` POST actions.

This was selected over read-only reporting tables because usage-status changes are operational writes: they create audit history and `no_show` notifies the requester.

## Scope implemented

### `templates/usage/list.html`
- keeps exactly one semantic table and original caption/header/loop;
- adds scoped responsive classes for wrapper/table/rows/cells/forms/buttons;
- status is surfaced first in mobile card order;
- original URL, CSRF token, button names/values/copy and disabled conditions remain unchanged;
- row action visibility remains controlled only by server-calculated `booking.usage_change_open`;
- closed rows retain `พ้นกำหนดแก้ไข` with no action form.

### `static/css/app.css`
- adds only `/* UX-10 Usage Status Mobile Clarity */` under `@media (max-width: 47.99rem)`;
- resets the generic 42rem minimum width only for `.usage-table`;
- mobile rows become status-first card grids with labels for time/room/requester;
- long Thai text wraps using scoped overflow rules;
- actions use a two-column full-width grid with `min-height: 44px` buttons;
- closed rows use dashed/soft styling;
- exact 768px and wider remain desktop table;
- no `:has()` and no JavaScript.

### `usage/tests_ux10.py`
Guards:
- one semantic table and page-scoped hooks;
- custodian access and outsider denial;
- update remains POST-only;
- CSRF and exact endpoint/action contracts;
- exact `used` / `no_show` values and disabled states;
- open vs closed row rendering;
- `47.99rem` breakpoint, scoped `min-width: 0`, >=44px touch target, wrap-safe CSS, no `:has()`.

### `docs/plans/2026-09-16-ux-10-usage-status-mobile.md`
Records evidence, invariants, implementation and verification.

## Business/security invariants not changed

- `usage_list` server permission boundary remains `can_manage_usage`.
- `usage_update` remains `@require_POST`.
- edit window remains booking end through use date + 3 days.
- approved/allowed usage-state rules unchanged.
- displaced / room-unavailable restrictions unchanged.
- `usage/services.py`, audit behavior and requester notification behavior unchanged.
- no model, migration, URL, settings, service or view changes.

## Implementation-agent outcome

Antigravity CLI was attempted first. Headless execution was auto-denied before editing because a required `command` permission could not be prompted for. It produced no source changes. The phase then used the approved scoped lnwjud fallback in the isolated branch. Codex was not substituted.

## Automated verification

Environment: local PostgreSQL `ogn_room` at `127.0.0.1:5432`, Python 3.12, local-only Django secret, `DJANGO_DEBUG=1`, `DJANGO_SECURE=0`.

- Independent diff review: PASS; presentation-only scope; `usage/views.py` and `usage/services.py` untouched.
- `uv run pytest -q usage/tests_ux10.py usage/tests.py` → **8 passed, 4 warnings in 9.28s**.
- `uv run manage.py check` → **System check identified no issues (0 silenced)**.
- `uv run manage.py makemigrations --check --dry-run` → **No changes detected**.
- `uv run pytest -q` → **259 passed, 125 warnings in 74.18s**.
- `git diff --check`: **PASS** after final plan/handoff editing.
- Warnings are known framework/environment warnings: Django 6 URLField transition and absent isolated-worktree `staticfiles/` directory.

## Browser QA

Persona: disposable local Custodian. Real template rendered through Django authenticated test client with disposable test-database records. No status-changing POST was submitted.

Fixture states:
1. editable `USED`: `ใช้งานแล้ว` disabled, `ไม่มาใช้` enabled;
2. editable `NO_SHOW`: `ไม่มาใช้` disabled, `ใช้งานแล้ว` enabled;
3. closed old row: `พ้นกำหนดแก้ไข`, no update form;
4. deliberately long Thai room/requester/unit strings.

Viewports: **360 / 390 / 430 / 768 / 1280 / 1440 px**.

Observed final results:
- 360/390/430: media query active; all rows `grid`; no page/wrapper/row/room horizontal overflow; 2 action forms; 2 enabled + 2 disabled buttons; closed row has no form; action height ≈ **60.08px**; Thai strings wrap without clipping.
- 768/1280/1440: media query inactive; rows `table-row`; desktop table retained; no page/wrapper/row overflow.
- Focus-visible check on enabled `ไม่มาใช้`: computed outline `oklch(0.78 0.12 207) solid 2.72727px`, offset `2.72727px`.
- Raw remote-debug Tab dispatch did not advance focus, so it was classified as an automation-transport limitation rather than UI evidence; native button focusability and focus-visible styling were verified in the browser.
- No JavaScript exceptions or failed changed-page assets.
- Only expected static-QA-server `favicon.ico` 404.
- Visual inspection at 360px and 1440px PASS.

First Browser QA attempt on a dead temporary port returned `ERR_CONNECTION_REFUSED`; it was not counted. The server was restarted on port 7365, HTTP 200 verified, and the full matrix above rerun.

## Local QA artifacts — do not stage

Leave these untracked unless explicitly cleaning later:
- `ux10-usage-qa.html`
- `ux10-usage-360.png`
- `ux10-usage-1440.png`
- `ux10_qa_render_test.py`

Do not delete unrelated or QA files merely to make `git status` clean.

## Remaining release steps

1. final full diff review complete;
2. stage only the five scoped files:
   - `static/css/app.css`
   - `templates/usage/list.html`
   - `usage/tests_ux10.py`
   - `docs/plans/2026-09-16-ux-10-usage-status-mobile.md`
   - `docs/handoffs/2026-09-16-ux-10-usage-status-mobile.md`
3. commit and push `feat/ux-10-usage-status-mobile`;
4. open PR into `feat/lodging-v5-2`;
5. re-review PR diff;
6. require aggregate GitHub `PR Safety Gate` PASS on the final PR HEAD;
7. report READY FOR MERGE only after final HEAD is `MERGEABLE / CLEAN` and all required checks are green;
8. do **not** merge without a new explicit user instruction.

## Suggested PR

Title: `UX-10: Improve usage status actions on mobile`

## Next-chat prompt

Continue SIGROOM UX-10 from branch `feat/ux-10-usage-status-mobile`. Read `AGENTS.md`, `.agents/skills/sigroom-development-workflow/SKILL.md`, UI profile/checklists, `docs/plans/2026-09-16-ux-10-usage-status-mobile.md`, and this handoff. Verify live Git/GitHub state first. Local code gates already passed: targeted 8/8, Django check, no migration drift, full regression 259/259, Browser QA 360/390/430/768/1280/1440 PASS. Rerun `git diff --check`, final-review the complete diff, stage only scoped files, commit/push, open PR to `feat/lodging-v5-2`, re-review PR diff, and wait for aggregate `PR Safety Gate` on final HEAD. Do not stage local QA artifacts and do not merge without explicit user approval.
