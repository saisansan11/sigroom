# Phase E — Online Teaching Rooms (3 rooms)

## Scope

Phase E adds a focused Teacher Self-Service workflow for exactly three online teaching rooms while reusing the existing SIGROOM Booking Core. It does **not** create a second booking engine and does **not** deploy anything by itself.

Initial room allowlist:

- `STU-ONLINE-1` — ห้องสอนออนไลน์ 1
- `STU-ONLINE-2` — ห้องสอนออนไลน์ 2
- `STU-ONLINE-3` — ห้องสอนออนไลน์ 3

The existing `Resource`, `ResourceRule`, `Booking`, `BookingResource`, blackout/outage and cancellation services remain authoritative.

## Authorization contract

Teacher authorization is represented by the Django group:

`signalschool-teacher`

This is intentionally a mapping seam, not a new account schema field. Future Signalschool SSO can map its teacher role into this group without changing Booking Core.

Backend enforcement exists at both the focused route and booking policy validation. Merely hiding UI is not considered authorization.

Superusers are allowed for administration/testing. Other authenticated users receive HTTP 403 when accessing the focused booking route. Anonymous users are redirected to login.

## Course Source of Truth adapter

The current repository has no dedicated generic Course model. `bookings.management.commands.seed_courses` already publishes configured course titles into:

`ReferenceValue(field="attendee_level")`

Phase E therefore treats active rows in that configured catalog as the current Course Source of Truth adapter. The online booking form renders these values as a strict `<select>` and rejects values that are missing or inactive. No free-text course title is accepted.

This avoids creating a second course table before a school-wide Course/Enrollment source is selected. A future external course service can replace the adapter without changing Booking Core.

Important: this Course Catalog is **not** the missing student-enrollment roster. The Phase D blocker `student ∈ course` for lodging remains unresolved.

## Teacher flow

1. Login with a Signalschool account that belongs to `signalschool-teacher`.
2. Open `/online/`.
3. See the three configured online rooms, capacity, service hours, equipment and near-term availability.
4. Choose a room.
5. Select date/start/end.
6. Select a course from the active Course Catalog dropdown.
7. Select purpose from the standard Booking purpose choices.
8. Use “ตรวจสอบช่วงเวลา” to run the same Booking Core availability policy used by other rooms.
9. Use “ยืนยันจองและอนุมัติอัตโนมัติ”.
10. The server sets requester, unit, responsible name and phone from the authenticated account; client POST values cannot override them.
11. When the room policy is AUTO and the slot is valid/free, Booking Core creates the hold and the booking becomes APPROVED.
12. The user is returned to “การจองของฉัน”.

## Fail-closed conditions

Booking is blocked when any of these are true:

- user is not in the teacher role;
- room code is outside the three-room allowlist;
- room is inactive;
- room has no rule or its rule is not AUTO;
- teacher account has no unit or phone;
- selected course is not an active catalog value;
- start/end violates 15-minute grid, service hours, min/max duration or max advance;
- blackout/outage applies;
- room or associated held resources conflict with another active booking.

Direct generic `/book/<code>/` POST cannot be used to bypass the focused workflow. Series booking is disabled through the generic endpoints for ONLINE rooms. Generic amendment is blocked; the user can cancel and create a fresh online booking. Post-submit edits are restricted to `online_meeting_url`, `attendees`, and `note`, leaving owner/unit/course immutable.

## Controlled setup command

Prepare configuration with:

```powershell
uv run manage.py seed_online_teaching --owner-unit EDU
```

Optionally assign existing users to the teacher role:

```powershell
uv run manage.py seed_online_teaching --owner-unit EDU --teacher <username> --teacher <username2>
```

The command is idempotent. It creates the teacher group if missing, verifies/creates exactly the three allowlisted online resources, ensures AUTO policy for newly created rooms, and publishes the existing `COURSES` list into the active course catalog.

Safety behavior:

- If one of the reserved room codes already exists but is not an ONLINE room, the command stops with `CommandError` instead of repurposing it.
- If an existing room has REQUIRED approval policy, the command stops instead of silently changing its operational policy.
- The command never creates bookings and never deploys the application.

## Production gate

Do **not** run the setup command on Production merely because Phase E is merged. Production remains behind the explicit deployment approval gate.

Before a Production rollout:

1. confirm actual room names/location/equipment with the responsible unit;
2. confirm the intended teacher usernames or SSO-to-group mapping;
3. review service hours, duration limits, advance limits and cancel cutoff for each room;
4. confirm the active course catalog;
5. backup database;
6. run migration/check gates (Phase E should introduce no schema migration);
7. deploy only after explicit approval;
8. smoke-test teacher login → three rooms → availability → booking → My Bookings → cancel;
9. verify non-teacher direct URL returns 403 and no conflicting booking can be created.

## Rollback

Phase E is application/configuration-only and introduces no new schema by design. Application rollback therefore consists of returning to the previous application revision. Any room/group/catalog records created by the setup command should normally be left in place and marked/configured through admin rather than deleted during emergency rollback; deleting configuration is a separate explicit operational action.
