# SIGROOM UX-18 — Student Lodging Portal Mobile Clarity & Bed Selection Confidence

Status: IMPLEMENTED & VERIFIED - LOCAL QUALITY GATE PASS

## Verified base

- Base branch: `feat/lodging-v5-2`
- Base SHA: `7fa589854117c4f9a5f72ab188b5a6b57e9e74d2` (merge of PR #40 / UX-17)
- UX-18 branch: `feat/ux-18-student-portal-mobile`
- Isolated worktree: `C:\Users\RTA\Documents\ChatGPT-Antigravity\worktrees\sigroom-ux18-student-portal-mobile`

## Evidence / problem

The public student lodging portal is the highest-impact remaining lodging interaction because students use it to inspect rooms, choose a free bed, and submit personal booking data. Existing V6/UI5 work already preserves privacy, sorting, focus restoration, gallery controls, and the free-bed jump action, but the page has no dedicated UX phase for the current mobile standard (`< 768px`).

Source review found four presentation risks on 360–430px devices:

1. `.lodging-cohort-top` is a non-wrapping horizontal flex row, so the course badge and LINE share action can compete for width.
2. `.room-card-head` and `.bed-row` stay horizontal at all widths; the bed label/status and the 44px action button can become cramped on narrow devices or with long Thai text.
3. `.modal-form-actions` stays horizontal, reducing touch clarity in the booking dialog on narrow screens.
4. The fixed `.btn-jump-next-bed` uses centered absolute positioning and `white-space: nowrap`; it is not safe-area aware and can become an overlay risk on narrow/mobile browser chrome.

## Goal

Make the student portal easy and reassuring to use one-handed on 360–430px phones while preserving the exact lodging allocation, validation, privacy, and transaction behavior.

## Scope

### Template — `templates/lodging/student_portal.html`

- Add scoped CSS hooks only where needed.
- Give each free-bed action an explicit accessible label containing room code and bed number.
- Preserve current privacy wording and never expose occupant identity.
- Preserve current modal form fields and POST target unchanged.

### CSS — `static/css/app.css`

Add a scoped `/* UX-18 Student Lodging Portal Mobile Clarity */` block under `@media (max-width: 47.99rem)`:

- Stack the cohort badge/share action vertically and make the share action touch-friendly.
- Use a stable 2-column stats layout on phones, collapsing to 1 column only when necessary.
- Force `.rooms-grid` to one minmax-safe column.
- Stack room-card header content when needed.
- Stack bed status/action rows and make free-bed CTA full-width with >=44px touch target.
- Make booking modal actions full-width and easy to scan.
- Make the sticky jump CTA responsive, wrapping-safe, and `safe-area-inset-bottom` aware.
- Add enough mobile bottom space so the sticky CTA does not obscure the final room controls.
- Preserve desktop behavior at >=768px.

### Tests — `bookings/tests_ux18.py`

Add regression contracts for:

- portal remains public and does not render occupant PII;
- free-bed buttons include room+bed accessible labels;
- UX-18 CSS marker and `<47.99rem` scope exist;
- mobile one-column room grid, stacked bed rows, full-width bed CTA, modal actions, and safe-area sticky CTA are present;
- no lodging business/service/model/URL changes are introduced.

## Hard invariants

- `is_active` remains the portal open/closed control.
- `allocation_status` semantics are unchanged.
- No changes to conflict checks, booking transactions, bed validation, phone normalization, or authorization.
- Public portal must not expose roommate/student PII; occupied beds remain status-only.
- Existing gallery, focus restoration, error re-open, and reduced-motion behavior must remain intact.
- No migrations.

## Verification gates

1. Independent diff review.
2. `uv run pytest bookings/tests_ux18.py bookings/tests_v6_a.py bookings/tests_ui5.py -q`.
3. `uv run manage.py check`.
4. `uv run manage.py makemigrations --check --dry-run`.
5. `uv run pytest -q` full regression.
6. `git diff --check`.
7. Real Browser QA at 360, 390, 430, 768, 1280, 1440 px covering:
   - no horizontal scroll;
   - badge/share layout;
   - free/full room cards;
   - free-bed CTA and keyboard focus;
   - booking modal open/close/focus;
   - sticky jump visibility and overlap;
   - gallery open/next/prev/close;
   - no unexpected console/runtime/resource failures.
8. Commit/push, PR into `feat/lodging-v5-2`, re-review final PR diff, and wait for `SIGROOM PR Safety` CI.

## Merge rule

Per repository contract, UX-18 must stop at READY FOR MERGE after final CI. Merge requires a separate explicit user instruction naming the PR.
