# SIGROOM Lodging Room Registry Sync — 2026-09-29

## Problem confirmed on Production

- Production floor plan exposes the authoritative lodging inventory on floors 4–5: 87 rooms / 234 beds.
- Production public room registry currently exposes only the pilot rows `DORM-101`–`DORM-104`.
- Production room-detail probes for plan numbers 401–460 and 501–530 resolved **0 mapped rooms** before this change.
- Result: the room popup can render safely, but cannot start a real booking from any plan room because no authoritative `Resource` row exists.

## Source of truth

Use `bookings/lodging_about_data.py` only. Do not invent room numbers or capacities.

- Floor 4: 57 lodging rooms / 114 beds / 2 beds per room.
  - Air: 401–407, 411–416, 449–460.
  - Fan: 417–448.
  - 408–410 are excluded service/non-lodging spaces.
- Floor 5: 501–530, 30 rooms / 120 beds / 4 beds per room, all air-conditioned.

## Implementation

Management command: `sync_lodging_room_registry`.

Safety contract:

1. **Preview by default.** Running without `--apply` performs no database writes.
2. `--apply` creates only missing authoritative rooms and missing `ResourceRule` rows.
3. Existing compatible room rows are preserved; names/buildings/owners/status are not silently rewritten.
4. Numeric aliases (`401`) and standard aliases (`DORM-401`) are both recognized. If both aliases exist for the same plan room, the command fails closed.
5. Wrong type/category/floor/capacity fails closed before any write.
6. Legacy pilot rooms `DORM-101`–`DORM-104` are reported but never retired, renamed, reallocated or modified by this command.
7. Inactive authoritative rooms remain inactive; the command does not auto-enable them.
8. No cohort allocation is changed automatically. Course-room allocation remains an explicit staff operation.

Public general-request behavior is backward compatible:

- Before the authoritative inventory is complete, the form keeps the current active lodging-room fallback.
- Only when all 87 plan rooms are present with exactly one alias per number does the public form switch to the authoritative inventory and hide pilot rooms from public selection.
- Course-specific portals continue to use each cohort's explicit room allocation.

## Local verification

- `python manage.py check` — PASS.
- `python manage.py makemigrations --check --dry-run` — PASS / no changes.
- Targeted room-registry + popup/accessibility regression — 120/120 PASS.
- Final full pytest regression — 674/674 PASS.
- Browser QA on isolated `test_ogn_room` after `--apply` — PASS:
  - room 425 popup resolves to `DORM-425`;
  - public-request CTA is visible;
  - request form has 87 authoritative rooms;
  - room 425 is preselected;
  - `DORM-101` is absent from the public selector.

## Production data gate

Do **not** run `--apply` on Production as part of code deployment without separate explicit approval.

Required sequence when approved:

1. Deploy/release the reviewed code SHA.
2. Run `python manage.py sync_lodging_room_registry` against Production in preview mode and capture the exact `PLAN`/conflict output.
3. If and only if conflicts are zero and the operator approves the preview, run `python manage.py sync_lodging_room_registry --apply`.
4. Verify `/lodging/rooms/425/` (and representative floor-4/floor-5 rooms) resolve to the expected authoritative resources.
5. Verify public `/lodging/request/` shows 87 rooms and no legacy pilot rows.
6. Do not retire `DORM-101`–`DORM-104` until dependencies (cohort allocations, occupants, bookings/history) are audited separately.

Production data sync and legacy retirement are separate approval gates.
