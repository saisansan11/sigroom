# SIGROOM UX-2 Implementation Plan — Express Booking

## Status
`IN PROGRESS`

## Goal
Reduce interaction and scrolling in the regular room-booking journey while preserving the proven UI-3 five-step contract and every existing booking rule.

Target journey remains:
**เวลา → ห้อง → รายละเอียด → ตรวจสอบ → ยืนยัน**

UX-2 optimizes the high-frequency path so a requester who already selected a room/time and has a complete profile can finish the booking with only the activity essentials visible, while still allowing full control when needed.

## Verified Base
- Integration base: `feat/lodging-v5-2`
- Base SHA after UX-1 merge: `f136858603168d27f54c407b8bb52148eb9467b9`
- Working branch: `feat/ux-2-express-booking`
- UX-1 PR #22 merged before this branch was created.
- Preserve unrelated/untracked `.claude/handoffs/` and `.tmp/` files.

## Scope

### 1. Express booking form hierarchy
Files:
- `templates/bookings/book_form.html`
- `templates/bookings/partials/booking_fields.html`
- `static/css/app.css`

Changes:
- Keep selected room/time as a compact persistent summary rather than a large introductory block.
- Put high-frequency required activity fields first: title, purpose, attendees, and online link only when applicable.
- Convert responsible-person fields into an accessible progressive-disclosure section when user/unit/name/phone are already prefilled and valid.
- Automatically keep the responsible section open when required data is missing, bound values contain errors, or the user needs to edit it.
- Keep additional options/equipment/series under the existing progressive disclosure.
- Make the Step 4 review panel faster to scan and place it close to the submit controls.
- On wider screens, allow review/submit to use available horizontal space without increasing page complexity; on mobile remain a single clear column.

### 2. Preserve user control and error recovery
- Required fields must never become unreachable.
- Any error in a collapsed group must force that group open and show inline errors.
- The server remains authoritative; no client-side bypass of validation or business rules.
- Shift-next-slot recovery, draft save, series preview, and rebook behavior remain intact.

### 3. Search/result continuity
Files:
- `templates/bookings/book_search.html`
- `templates/bookings/partials/room_list.html`

Only make bounded UX changes if needed to preserve query continuity and reduce unnecessary re-entry:
- Keep search values in room-selection links.
- Keep clear “change time/room” navigation back to the populated search state.
- Do not add a new booking API or alter availability rules.

### 4. Presentation helper state
File:
- `bookings/forms.py`

Allowed change:
- Add presentation-only form properties/helpers needed to decide whether a progressive-disclosure section should start open.
- No validation semantics, queryset permissions, model fields, or service behavior may change.

### 5. Automated UX-2 contracts
File:
- `bookings/tests_ux2.py`

Tests should prove:
- complete requester profile => responsible section is collapsed by default but fields remain present in the form;
- incomplete profile => responsible section opens;
- bound responsible-field error => responsible section opens and error remains visible;
- selected room/time and activity essentials remain visible;
- draft/submit/series actions remain available where applicable;
- search query continuity survives room selection/change-room navigation;
- no permission or schema changes.

## Non-Goals / Invariants
- No database schema or migration.
- No change to `submit_booking`, conflict checks, 15-minute slots, service windows, blackouts, outages, buffers, exclusion constraints, approval policy, lodging conflict semantics, or permissions.
- No change to sensitive/public visibility behavior.
- No removal of draft, series, amendment, preemption, rebook, or approval workflows.
- No production deployment.
- Do not redesign unrelated homepage/lodging/admin pages.

## Implementation Risks
1. **Collapsed required fields** — mitigated by opening the section whenever prefill is incomplete or errors exist.
2. **Template hiding an error** — add explicit tests for bound error state and Browser QA with invalid input.
3. **Query continuity regression** — preserve current GET query string and test change-room round trip.
4. **Mobile sticky/compact layout overlap** — test 360/390/430 and keyboard focus, avoid fixed overlays that cover fields.
5. **Series/draft action regression** — run existing UI-3 and booking regression suites unchanged.

## Verification Gates

### Targeted tests
At minimum:
```powershell
uv run pytest bookings/tests_ux2.py bookings/tests_ui3.py bookings/tests_m2.py bookings/tests_m4.py bookings/tests_m5.py bookings/tests_m6b.py bookings/tests_trial_round1.py -q
```

### Required repository gates
```powershell
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest --tb=short -q
git diff --check
```

### Real Browser QA
Viewports: **360, 390, 430, 768, 1280, 1440 px**.

Requester flows:
1. `/book/` search → choose room → express form → submit → booking detail.
2. Direct homepage room CTA → express form with time prefilled.
3. Complete profile: responsible section collapsed by default; open/edit via keyboard and pointer.
4. Incomplete/invalid responsible data: section opens automatically with visible error/focus recovery.
5. Draft save.
6. Series toggle/preview for a room that allows series when available.
7. Change time/room returns to populated search state.

Approver regression:
- Pending booking detail still exposes approve/reject only to authorized approver.

Quality checks:
- no page-level horizontal overflow;
- touch targets approximately >=44px;
- visible keyboard focus;
- no content hidden under sticky controls;
- no console/runtime errors;
- reduced-motion behavior preserved.

## Completion Contract
UX-2 is ready only after independent diff review, targeted/full tests, Django/migration gates, real Browser QA, scoped commit/push, PR re-review, CI/status check (or explicit absence), and handoff documentation.
