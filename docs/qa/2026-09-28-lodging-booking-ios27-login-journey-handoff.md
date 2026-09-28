# SIGROOM — Lodging booking iOS 27 + login arrival journey handoff

Date: 2026-09-28
Branch: `feat/lodging-booking-ios27-login-journey-20260928`
Stacked on: `codex/p2-lodging-checkout` / PR #69 → PR #68 → `feat/lodging-v5-2`
Production: **unchanged**

## Scope completed

### 1. Lodging booking visual convergence

- Student lodging portal now uses the same bright hospitality / iOS-style visual language as `/lodging/about/`:
  - light canvas and translucent navigation
  - deep navy text
  - cyan/teal actions
  - rounded white/soft surfaces
  - restrained depth/shadows
- Existing public privacy behavior and booking POST contract are unchanged.
- Emoji-style privacy/photo affordances were replaced with the existing SIGROOM SVG icon system.

### 2. Room / bed selection popup

- Existing `#bookingModal` remains the single booking flow.
- Modal now uses a dark navy/purple glass focus layer inspired by the supplied reference image.
- Added selected room/bed context, lodging icon, accessible dialog heading/description, and a blue→purple confirmation CTA.
- Mobile action row keeps **Cancel + Confirm visible together**.
- Native dialog `close` event restores focus to the initiating bed button; normal booking field names and target URL are unchanged.

### 3. Login arrival journey

- Replaced radar-only login presentation with an inline SVG scene:
  1. Signal School soldier arrives while wheeling a suitcase.
  2. Suitcase settles/drops.
  3. Lid opens.
  4. Login card rises into view.
- Animation is progressive enhancement only.
- Plays once per tab session via `sessionStorage`.
- Validation-error reloads skip the animation.
- `prefers-reduced-motion` disables the motion and presents the usable login form immediately.
- No emoji/cartoon asset dependency; vector scene is local and deterministic.

## Verification completed

### Automated

- Targeted UX/auth regression (earlier final-content run): PASS.
- Final full regression after scoped portal-JS review/restoration: **651 passed, 287 warnings**.
- `manage.py check`: **PASS — 0 issues**.
- `manage.py makemigrations --check --dry-run`: **PASS — No changes detected**.
- `git diff --check`: **PASS**.

The warnings are existing test/runtime warnings; there was no test failure.

### Browser / visual QA

Desktop and mobile-breakpoint QA was performed in Chrome using the real template/CSS/JS where possible.

- `/lodging/about/` visual baseline: checked, horizontal overflow = 0.
- Login page on local Django server:
  - first-arrival soldier/suitcase stage checked visually
  - final login card checked visually
  - desktop overflow = 0
  - 500 px mobile-breakpoint overflow = 0
  - username focus behavior confirmed
- Student portal:
  - direct local DB route could not be used because the developer DB is schema-stale (`bookings_courselodgingcohort.course_run_id` missing)
  - **no migration was applied to the developer DB**
  - instead, the actual `student_portal.html` was rendered with Django against a DB-free deterministic QA context and served with the real static assets
  - desktop and 500 px mobile-breakpoint layouts checked visually; horizontal overflow = 0
  - actual template button opened the actual booking dialog JS
  - selected room/bed title and hint synchronized correctly
  - first field focus = `id_rank`
  - dialog close event restored focus to the originating `.bed-select-btn`

The stale developer DB is an environment drift issue, not a code/test failure: the isolated Django test database completed the full 651-test suite successfully.

## Scope integrity

No change to:

- lodging booking service/model rules
- checkout semantics from PR #69
- authorization / roles
- migration files
- Production database or Production Cloud Run/Firebase
- PR #68 / PR #69 merge state
- 100-run Production campaign count

## Release / acceptance state

- UX implementation: **local quality gate PASS**.
- Production P2 acceptance: **still paused / not certified**.
- 100-run real-user simulation: **remains 1/100** until the UX branch is reviewed, merged and separately deployed with explicit approval.
- Next gate: commit/push/open a stacked PR → CI → explicit merge/deploy approval → deploy → rerun P2 Production Lodging E2E → continue 100-run campaign.
