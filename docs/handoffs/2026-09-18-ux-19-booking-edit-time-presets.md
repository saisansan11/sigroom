# SIGROOM UX-19 — Booking Edit Time Preset Parity — Handoff

## Status

LOCAL QUALITY GATE PASS — READY FOR COMMIT / PR

## Verified base

- Base branch: `feat/lodging-v5-2`
- Base SHA: `456069ab0b1cabbc28c722eb8527827a36fa1655` (merge of PR #41 / UX-18)
- UX-18 commit `2ed5814cfb7f7ff442302243d95c83b50cbe40a0` is present in the base history.
- UX-19 branch: `feat/ux-19-booking-edit-time-presets`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux19-discovery`
- No model, schema, migration, permission, conflict, transaction, or deployment changes.

## Why UX-19

`docs/v7-notes.md` documented a real remaining V7 issue: Draft Booking Edit still allowed date/time edits but did not show the existing Time Preset buttons because `booking_edit` did not pass `time_presets` into the shared form template context.

Source inspection confirmed that:

- Booking Edit reuses `templates/bookings/partials/booking_fields.html`.
- The shared field partial already knows how to render `partials/time_presets.html`.
- Search/create flows already provide `time_presets()`.
- Draft bookings include `date`, `start_time`, and `end_time` in `editable_fields()`.
- Post-submit bookings use `POST_SUBMIT_EDITABLE_FIELDS`, which intentionally excludes date/time.

Therefore UX-19 is a narrow context-parity fix rather than a form redesign or business-rule change.

## Implemented scope

### `bookings/views.py`

`booking_edit` now passes `time_presets()` into the template context. The existing shared preset component and JavaScript are reused unchanged.

### `bookings/tests_ux19.py`

Added four regression contracts:

1. Draft owner sees Time Presets and editable date/start/end fields.
2. Post-submit owner does not see Time Presets or date/start/end fields, and Amendment guidance remains present.
3. A non-owner is still denied access to Booking Edit.
4. Injected post-submit date/time values are ignored while permitted editable fields can still update.

### `docs/v7-notes.md`

The previous Known Issue is retained as history but marked fixed in UX-19, explicitly preserving the post-submit lock and Amendment path.

## Automated verification

Observed on the final local source before commit:

- `uv run pytest bookings/tests_ux19.py bookings/tests_v7_c.py bookings/tests_m2.py -q` → **27 passed, 17 warnings**
- `uv run manage.py check` → **0 issues**
- `uv run manage.py makemigrations --check --dry-run` → **No changes detected**
- `uv run pytest -q` → **453 passed, 174 warnings**
- `git diff --check` → **PASS**
- `review_changes` → scope reviewed; no unexpected tracked files found

The first targeted-test attempt failed before entering any test body because the isolated worktree lacked the local PostgreSQL password. The existing ignored SIGROOM `.env` was copied from `F:\ogn_ROOM\.env` into the isolated worktree without displaying its contents, after which the same targeted suite passed 27/27. This was an environment setup issue, not a code regression.

Warnings are existing local-environment / Django transition warnings: pilot HTTP security warning, Django 6 URLField transition, and missing isolated-worktree `staticfiles/` warning.

## Real Browser QA

Live local Django server only; no deploy. A temporary Browser-QA user, unit, room, Draft booking, and Approved booking were created in the local development database and deleted after QA.

### 390px viewport

Draft Booking Edit:

- exact CDP viewport width confirmed at 390px
- 3 preset buttons rendered
- no horizontal overflow
- existing button CSS produced an effective ~44px touch height
- clicking `คาบเช้า 08:00–12:00` changed start/end controls from the booking values to `08:00` / `12:00`

Approved Booking Edit:

- no preset buttons rendered
- no `date`, `start_time`, or `end_time` controls rendered
- Amendment (`คำขอแก้ไข`) guidance/link remained present
- no horizontal overflow

### 1280px viewport

Draft Booking Edit:

- exact CDP viewport width confirmed at 1280px
- 3 preset buttons rendered
- no horizontal overflow
- clicking `คาบบ่าย 13:00–16:00` changed start/end controls to `13:00` / `16:00`

Approved Booking Edit:

- no preset buttons rendered
- no date/time controls rendered
- Amendment guidance remained present
- no horizontal overflow

### Browser runtime / network evidence

A CDP reload check recorded:

- Runtime exceptions: 0
- Network loading failures: 0
- One browser console error associated with one HTTP 404 for `http://127.0.0.1:8019/favicon.ico`

The favicon request is unrelated asset noise; there were no application runtime exceptions or UX-19 request failures.

## Invariants preserved

- Draft date/time editing policy is unchanged.
- Post-submit date/time remains locked by `POST_SUBMIT_EDITABLE_FIELDS`.
- Approved time changes still use the Amendment flow.
- Non-owner authorization behavior is unchanged.
- No conflict, hold, race, validation, model, schema, or migration logic changed.
- No new CSS or JavaScript was added.
- No deploy was performed.

## QA cleanup

- Temporary UX-19 Browser-QA bookings deleted from the local development database.
- Temporary UX-19 Browser-QA room/user/unit deleted.
- Local QA Django server stopped.
- QA Chrome tab closed.
- CDP device metrics override cleared.
- No QA-only source artifact is part of the intended commit.

## Files in scope

- `bookings/views.py`
- `bookings/tests_ux19.py`
- `docs/v7-notes.md`
- `docs/plans/2026-09-18-ux-19-booking-edit-time-presets.md`
- `docs/handoffs/2026-09-18-ux-19-booking-edit-time-presets.md`

## Release steps

1. Final `git status` / diff review.
2. Stage only the five UX-19 files above.
3. Commit: `fix(ux-19): restore booking edit time presets`.
4. Push `feat/ux-19-booking-edit-time-presets`.
5. Open PR into `feat/lodging-v5-2`.
6. Re-read PR diff and verify final head SHA/base SHA.
7. Wait for aggregate `SIGROOM PR Safety` / `PR Safety Gate` and all required CI checks.
8. Stop at **READY FOR MERGE**. Merge requires a separate explicit user instruction naming the PR.

## Next phase

After UX-19 is explicitly approved and merged, fetch the updated protected integration branch and discover UX-20 from the then-current roadmap/source/handoff evidence rather than assuming a target.
