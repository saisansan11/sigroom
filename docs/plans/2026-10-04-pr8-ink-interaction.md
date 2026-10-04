# PR-8 Implementation Plan — Ink Interaction

## Goal
Add a lightweight ink-bleed interaction layer to the public SIGROOM gateway and online-teaching booking surfaces only, without changing booking logic, permissions, data, or staff/operator pages.

## Scope
- New shared library: `static/js/ink_bleed.js`, `static/css/ink_bleed.css`.
- Add a default-empty body attribute block in `templates/base.html`.
- Enable `data-ink="on"` and load the library only in:
  - `templates/lodging/lodging_about.html`
  - `templates/bookings/online_teaching_home.html`
  - `templates/bookings/online_teaching_book.html`
- Add focused pytest/template guards and Node VM interaction tests.

## Interaction contract
1. Mouse-only ambient canvas trail. Ignore touch/pen. `pointer-events:none`, `position:fixed`, `mix-blend-mode:multiply`.
2. Droplets 6–10px; occasional soft blot 28–40px; alpha never above 0.10; at most 60 particles; DPR capped at 1.5.
3. RAF runs only while particles exist and stops on idle/hidden; visibility changes must not leak RAF work.
4. Click/pointer activation on interactive controls may create 3–4 short ink rings, 600–800ms, without `preventDefault`, navigation delay, or HTMX interference.
5. Selected states (`aria-current`, `aria-pressed`, checked controls where applicable) may show a static stain <= 0.18 opacity.
6. `prefers-reduced-motion: reduce`: no canvas trail and no transient ring animation; selected static state remains allowed.
7. Event delegation attaches to `document` so HTMX-swapped online results still work.
8. No ink assets or `data-ink="on"` on staff/dashboard/approval/admin surfaces.

## Accessibility / safety
- Preserve text/background contrast; overlay uses low-opacity multiply and never captures pointer/focus.
- Decorative canvas/rings are `aria-hidden`/non-semantic.
- No change to keyboard navigation, form submission, booking writes, routes, permissions, or business services.
- No user data is read or emitted by the effect.

## Verification
- `npm run test:interaction` including new ink tests.
- Focused pytest proving enabled surfaces and staff/dashboard exclusion.
- `uv run python manage.py check`.
- `uv run python manage.py makemigrations --check --dry-run`.
- Full `uv run pytest`.
- `git diff --check`.
- Browser QA: gateway + online page at desktop and 390px, mouse trail/click, touch ignored, HTMX swap, reduced-motion, no overflow, console exception, or failed network request.

## Out of scope
No redesign, no color/theme replacement, no canvas on staff/operator pages, no booking-flow changes, no database/migration changes, no production configuration changes.
