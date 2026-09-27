# SIGROOM — Lodging booking iOS 27 convergence + login journey

Date: 2026-09-28
Branch: `feat/lodging-booking-ios27-login-journey-20260928`
Stacked on: PR #69 (`codex/p2-lodging-checkout`) → PR #68 → `feat/lodging-v5-2`

## Goal

Make the lodging booking experience feel like the same product as `/lodging/about/` before resuming P2 Production acceptance.

1. Student lodging portal adopts the bright iOS 27 / hospitality visual language used by the lodging information page while preserving all booking fields, service rules, privacy, and routes.
2. Selecting an available bed opens a polished selection dialog inspired by the supplied dark-glass reference: clear selected room/bed context, restrained depth, strong CTA, mobile-first layout, and keyboard/focus restoration.
3. Login becomes a short arrival journey: a Signal School soldier wheels a suitcase into view, the suitcase settles and opens, and the login card rises from it. The effect is CSS/SVG only, plays once per tab session, does not block the form, and is disabled for `prefers-reduced-motion` and on validation-error reloads.
4. After implementation, run targeted UI/template tests, Django checks, migration drift, full regression, diff check, and real browser QA at desktop + mobile before returning to P2 acceptance.

## Design contract

- Same page shell as `/lodging/about/`: light canvas, translucent white navigation, deep navy text, cyan/teal action color, rounded 16–24 px surfaces, soft low-contrast shadows.
- Student portal remains privacy-safe: occupied-bed status only; no roommate PII.
- Booking dialog intentionally uses a darker glass panel (matching the reference screenshot) as a focus layer over the bright page, not as a second global theme.
- Login illustration is a sober vector silhouette, not cartoon/emoji art. Motion should read as purposeful arrival rather than decorative looping.
- Body text stays >= 16 px on the new light surfaces; touch targets >= 44 px; no horizontal overflow at 320–430 px.
- No change to booking POST target, field names, lodging service/model rules, checkout implementation, migrations, authorization, or Production infrastructure.

## Implementation slices

### A. Student portal shell
- Add page-specific light theme/body class and stylesheet.
- Restyle hero, stats, room cards, photo controls, bed rows, sticky navigation, privacy callout, gallery and dialogs.
- Preserve existing DOM hooks and JS functions used by UX-18 tests.

### B. Room/bed selection dialog
- Upgrade existing `<dialog id="bookingModal">` instead of adding a second booking flow.
- Add selected-room icon/kicker/context block and dialog backdrop/glass styling.
- Update JS to synchronize room/bed text and accessibility description before opening.
- Keep focus restoration and existing form fields/action unchanged.

### C. Login arrival animation
- Replace radar-only presentation with an inline SVG scene containing soldier + suitcase.
- Add staged CSS keyframes: walk-in → suitcase settle → lid open → login card rise.
- JS chooses `journey-play` or `journey-skip` using reduced-motion, sessionStorage, and login-error state.
- Login form remains usable if JS fails; animation is progressive enhancement only.

### D. Verification before P2 resumes
- Add regression assertions for theme hooks, booking dialog semantics, unchanged booking contract, login reduced-motion/session behavior, and no emoji art dependency.
- Targeted pytest.
- `manage.py check`.
- `makemigrations --check --dry-run`.
- Full pytest regression.
- `git diff --check`.
- Browser QA at 1280×844 and 390×844: lodging portal room selection dialog + form, keyboard Escape/focus return, login first visit + repeat visit + reduced motion, overflow and console.

## Explicitly out of scope

- Merging PR #68/#69.
- Production deploy or Production database migration.
- Resuming the 100-run Production campaign until this visual phase passes its local/CI gates and the user separately authorizes promotion.
- Changing lodging inventory, checkout semantics, authorization, or real-user data.
