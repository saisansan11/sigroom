# UI Refresh Profile

Apply this profile to SIGROOM UI work.

## Direction

Target: **EMSO About aesthetic + Apple-style product clarity + operational usability**.

Translate the reference rather than copying its theatrical effects. SIGROOM is an operational tool: speed, legibility, status clarity, and task completion win over spectacle.

- Large, Thai-safe typography with generous line-height.
- Clear information hierarchy and more whitespace.
- Reduce nested cards, heavy borders, grid/HUD noise, glow, glass, gradients, and decorative animation.
- Keep a restrained SIGROOM signal accent for identity and important interaction/status only.
- Use real room imagery and operational data as primary visuals where relevant.
- Mobile-first; touch targets at least 44px where practical.
- Motion must communicate state or orientation and respect `prefers-reduced-motion`.
- Visible keyboard focus, semantic HTML, useful loading/empty/error states, sufficient contrast.
- Prefer design tokens and reusable components over page-specific CSS.

## Phase boundaries

### UI-1 — Design foundation
Tokens, base layout, navigation, page headings, buttons, forms, cards/panels, badges/status, notices, empty/loading/error states. Preserve business logic and page workflows.

### UI-2 — Homepage / Availability / Calendar
Product-style hero, key live statuses, 2–3 primary CTAs, room availability as the main content, reduced calendar noise, mobile Today/Agenda behavior. Lodging calendar reservations retain V5.1 non-clickable/background semantics.

### UI-3 — Booking flow
Create strong visual steps `เวลา → ห้อง → รายละเอียด → ตรวจสอบ → ยืนยัน`; prefill known data, hide secondary fields under progressive disclosure when safe, retain all booking rules.

### UI-4 — Lodging
Hotel-like room/bed selection, mobile-first LINE/QR entry, no roommate PII, digital key-card student pass, efficient staff tables/lists.

### UI-5 — Responsive / accessibility / performance
Verify at least 360, 390, 430, 768, 1280, 1440 px. Check overflow, clipping, touch, keyboard, focus, contrast, semantics, reduced motion, lazy images, loading state, and layout shift.

## Browser QA

Do not rely on screenshots alone. Exercise click/navigation/form behavior for applicable roles: Guest, Student lodging, Supervisor, Approver, Custodian. Test desktop and mobile viewport. Fix discovered UI defects and rerun relevant tests.
