# UX-16: Student Digital Key-Card Mobile Clarity & Accessibility — Plan

## Context & Objectives
- Target: `templates/lodging/student_pass.html`, `static/css/app.css`, `bookings/tests_ux16.py`
- Objective: Enhance the Student Digital Key-Card to ensure high mobile clarity, eliminate text clipping/cropping on narrow screens (360px-430px), enforce touch targets >= 44px, add visible focus rings, and provide content-safe dynamic grid sizing for long Thai student names and cohort titles.

## Problem Statement
1. Fixed aspect ratio (`aspect-ratio: 1.586 / 1` on desktop, or rigid portrait heights) and `overflow: hidden` on `.keycard-face` caused vertical overflow (~61px at 360px, ~10px at 390px, ~15px on desktop) when student names or cohort titles were long.
2. Floating 3D animation (`rotateZ(-6deg)` tilt) caused touch jitter and distraction on mobile viewports.
3. Mobile action buttons were not full-width and touch targets needed strict enforcement (>= 44px).

## Technical Approach: Content-Safe Dynamic Grid
1. Use CSS Grid with `grid-template-areas: "card"` on `.keycard-flip` so both front and back faces occupy the same grid area.
2. Allow `.keycard` and `.keycard-face` to have `height: auto` and `min-height: 100%`, dynamically expanding to fit content without arbitrary clipping.
3. Apply `overflow-wrap: anywhere` and `word-break: break-word` on long text fields.
4. Disable 3D tilt animation (`animation: none; transform: none`) on viewports `<= 47.99rem`.
5. Enforce `min-height: 44px` on all action buttons and links on mobile.
6. Provide visible `:focus-visible` cyan outline (`2px solid var(--cyan)`).

## Verification Strategy
1. Automated contract tests in `bookings/tests_ux16.py` (8/8 passed).
2. Targeted regression: `tests_ux16 + tests_ux15 + tests_ui4` (22/22 passed).
3. Real Browser QA using headless Chrome CDP across 6 viewports (360, 390, 430, 768, 1280, 1440px) to verify 0 horizontal overflow, 0 vertical card overflow, >= 44px touch targets, and keyboard flip (Enter/Space).
4. Full regression suite: `uv run pytest -q` (356/356 passed).
