# UX-1 Task-First Shell & Home Handoff — 2026-09-14

## 1. Verified repository state
- Integration base: `feat/lodging-v5-2`
- Base SHA: `f0c4fab9b1df9e9825387d8ab8b0e91c00bb41fd`
- Feature branch: `feat/ux-1-task-first-shell-home`
- UX-1 initial implementation: `83e57e1`
- Initial handoff commit: `2d15a73`
- Independent-review corrective implementation: `2699214` (`fix(ux): simplify UX-1 home interaction density`)
- PR: `#22`, head `feat/ux-1-task-first-shell-home`, base `feat/lodging-v5-2`
- `.claude/handoffs/` and `.tmp/` remain unrelated/untracked and must not be staged, modified, cleaned, or deleted.
- No production deployment was performed.

## 2. Why a corrective pass was required
The first UX-1 implementation passed automated regression and overflow checks, but an independent real-browser review found that the actual usability goal was not met. At `360x845`, the Guest home still had about `4831px` of initial scroll height with too many competing links/actions.

The corrective pass therefore treated usability as a release gate rather than accepting “tests pass / no overflow” as sufficient.

## 3. Final UX-1 behavior
### Task-first shell
- Authenticated top-level navigation remains focused on everyday tasks: `หน้าแรก`, `จองห้อง`, `การจองของฉัน`, `จองห้องพัก`.
- Role-specific tools remain grouped under `งานปฏิบัติการ`; server-side permissions/routes were not changed.
- Reports remain secondary inside the operational grouping.
- Guest navigation remains minimal.

### Task-first home
- The dynamic `primary-task-banner` is the single main “next action” for the current user.
- Duplicate approval/usage/my-booking actions were removed from the status band.
- Remaining role responsibilities are shown as a compact secondary task strip rather than full repeated cards.
- The duplicate Guest booking/login banner was removed because the Guest hero already provides those actions.
- The large room-type cards were replaced by a compact `home-entry-strip`, while preserving the required discovery anchors and lodging course entry points.
- `home-entry-grid`, `#now-teaching`, `#now-meeting`, lodging cohort links and other compatibility hooks remain available.

### Progressive operational schedule
- Today Board and FullCalendar are now inside native `<details id="operational-calendar-section">` and are closed by default.
- The summary is a semantic keyboard-focusable control with a visible focus state.
- FullCalendar initializes lazily only when the disclosure is opened, avoiding hidden-container sizing problems and shortening the initial page.
- Hash targets for `#operational-calendar-section`, `#today-board`, `#calendar`, and `#operational-schedule-summary` automatically open the disclosure and preserve discoverability.
- On subsequent opens, FullCalendar calls `updateSize()`.
- Existing calendar event semantics, booking routes, lodging background reservations, filters, and selection behavior were not changed.

## 4. Accessibility and touch targets
- New/affected interactive targets use `max(44px, 2.75rem)` (or larger).
- Browser measurement reports approximately `43.99px` for a CSS 44px target because of sub-pixel/device scaling.
- The SIGROOM brand home link and lodging course links were also brought to the 44px target floor during independent review.
- `<summary>` remained focused and toggled open using the Enter key in real Chromium CDP QA.
- Reduced-motion support remains intact.

## 5. Automated verification
### Targeted UX-1
Command:
`uv run pytest bookings/tests_ux1.py -q`

Result:
- **16 passed, 2 warnings**

### UX-1 + legacy presentation compatibility
Command:
`uv run pytest bookings/tests_ux1.py bookings/tests_v6_a.py -q`

Result:
- **22 passed, 2 warnings**

### Full regression
Command:
`uv run pytest --tb=short -q`

Final result after all corrective fixes:
- **213 passed, 2 warnings**

The warnings are the existing local `DJANGO_SECURE=0` LAN-pilot warning and the upstream Django 6 URLField scheme deprecation warning.

### Framework/schema/diff gates
- `uv run manage.py check` → **0 issues**
- `uv run manage.py makemigrations --check --dry-run` → **No changes detected**
- `git diff --check` → **PASS / clean**

## 6. Real-browser QA
Local-only test server: `http://127.0.0.1:7357`.
No production URL or production infrastructure was used.

Personas exercised:
1. Guest
2. Normal authenticated user (`somchai` local test account)
3. Operational user / approver + custodian (`somsak` local test account)

Viewports exercised:
- `360`, `390`, `430`, `768`, `1280`, `1440` px

### Initial-page results with operational disclosure closed
Across all three personas and all six viewports:
- **0 horizontal overflow**
- `operational-calendar-section` closed by default
- Primary task visible in the first viewport for authenticated users
- UX touch targets measured at the 44px CSS floor (about 43.99px after sub-pixel scaling)

Representative initial scroll heights after the corrective pass:
- Guest, 360px: about **1865px** (down from about **4831px** before correction)
- Normal user, 360px: about **2235px**
- Operational user, 360px: about **2383px**

These are comfortably below the corrective acceptance ceilings of 3300px for Guest and 3600px for a normal authenticated user.

### Disclosure / Calendar behavior
At desktop width after opening the disclosure:
- disclosure state became open
- FullCalendar rendered children successfully
- calendar height was about 1127px
- no horizontal overflow
- no captured Runtime/Log console errors

Keyboard check:
- focus placed on `#operational-schedule-summary`
- Enter toggled the native details disclosure open
- focus remained on the summary

## 7. Files changed in the corrective pass
- `templates/bookings/calendar.html`
  - removes duplicate actions
  - adds compact task strip and compact room entry strip
  - converts operational calendar/Today Board to progressive disclosure
  - lazy-renders FullCalendar and handles hash targets
- `static/css/app.css`
  - compact task/entry styling
  - disclosure styling and focus state
  - touch target corrections
  - uses existing design tokens only (`var(--canvas)` rather than an undefined token)
- `bookings/tests_ux1.py`
  - verifies collapsed disclosure semantics
  - verifies duplicate Guest CTA removal
  - verifies compact room entry discovery anchors/lodging access
  - verifies primary-task de-duplication
- `docs/handoffs/2026-09-14-ux-1-task-first-shell-home.md`
  - this final independent-review record

## 8. Invariants confirmed unchanged
- No model/schema changes.
- No destructive migration.
- No booking conflict/business-rule changes.
- No approval/SLA/delegation logic changes.
- No usage rule changes.
- No lodging allocation/conflict/phone/bed rules changed.
- No server-side authorization or privacy boundary changed.
- No production deploy.

## 9. PR / merge policy
PR #22 must be checked again after the corrective commits are pushed for:
- exact head SHA
- base branch
- mergeability
- CI/status checks when present

**Do not merge PR #22 without explicit user instruction.** The earlier automatic-merge authorization covered UI-3, UI-4, and UI-5 only, not UX-1.

## 10. Recommended next phase after UX-1 is merged
`UX-2 — Express Booking / Task-First Booking Flow`

Goal: shorten the user journey from “I need a room” to a submitted request without changing booking business rules. Target flow: date/time → room → details + confirmation, with known values prefilled and optional fields moved out of the primary path.

Before UX-2, branch from the updated `feat/lodging-v5-2` only after PR #22 is explicitly approved and merged; do not stack UX-2 on PR #22.
