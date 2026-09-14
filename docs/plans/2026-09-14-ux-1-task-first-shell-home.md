# SIGROOM UX-1 Implementation Plan — Task-First Shell & Home

## Status
`PLANNING`

## 1. Context & Baseline
- **Integration Base**: `feat/lodging-v5-2` (commit `f0c4fab9b1df9e9825387d8ab8b0e91c00bb41fd`)
- **Current Branch**: `feat/ux-1-task-first-shell-home`
- **Dependencies**: UI-1 through UI-5 are merged into base. Full pytest regression baseline: 197 passed, 2 warnings in ~43s.
- **Goal**: Implement UX-1 Task-First Shell & Home to simplify navigation around user tasks rather than system modules and transform the homepage into a concise, mobile-scannable task-first command center.

---

## 2. Scope & Objectives (UX-1 Only)

### Part A: Task-First Shell & Top-Level Navigation (`templates/base.html`)
1. **Simplify Authenticated Navigation for Regular Users**:
   - Prominently feature core user tasks:
     - **หน้าแรก** (`bookings:calendar`)
     - **จองห้อง** (`bookings:book_search`, `bookings:book_form`)
     - **การจองของฉัน** (`bookings:my_bookings`)
     - **จองห้องพัก** (`bookings:lodging_index`)
   - Remove operational administrative modules from top-level clutter.
2. **Cleanly Group Role-Specific Operational Work**:
   - For users with elevated roles (`nav_can_access_approvals`, `nav_can_manage_usage`, `nav_can_manage_lodging`, `nav_can_access_reports`), provide a clean, grouped operational menu (**งานปฏิบัติการ** / Ops):
     - **รออนุมัติ** (`approvals:queue`) with badge count
     - **การใช้งานห้อง** (`usage:list`)
     - **จัดการที่พักหลักสูตร** (`bookings:lodging_manage`)
     - **รายงาน** (`reports:dashboard`) positioned as secondary rather than primary
   - Ensure native HTML semantic dropdown (`<details class="nav-dropdown">`) on desktop and an organized secondary section in mobile menu panel (`.mobile-menu-panel`).
3. **Preserve Simple Guest Navigation**:
   - Guest navigation stays simple and focused:
     - **สถานะห้องวันนี้** (`bookings:calendar`)
     - **จองห้องพัก** (`bookings:lodging_index`)
     - **เข้าสู่ระบบ** login CTA button

### Part B: Task-First Homepage Redesign (`templates/bookings/calendar.html`)
1. **Above-the-Fold Primary Task & Next Action**:
   - Provide a prominent hero command center showing immediate next action:
     - For Approvers with pending items: Highlight pending approvals count with direct action.
     - For Room Custodians with today's tasks: Highlight usage verification items for today.
     - For Users with upcoming bookings: Display next scheduled booking with room, time, and link to detail.
     - For General users without bookings: Clear quick-action to search and book an available room.
2. **Quick Room Booking & Search**:
   - Streamlined, high-visibility quick search/booking entry without competing duplicate CTAs.
3. **Scannable Room Availability & Entry Grid**:
   - Consolidate room availability into a concise, mobile-friendly card layout.
   - Maintain compatibility with existing anchors (`#now-teaching`, `#now-meeting`, `#now-online`, `home-entry-grid`, `today-board`) expected by downstream workflows and tests.
4. **Secondary Operational Calendar & Today Board**:
   - Retain full operational FullCalendar and Today timeline board on the same route `/` without altering URL, context, or business semantics.
   - Organize into a clearly discoverable, tabbed/progressive section so it does not elongate the mobile scroll while remaining instantly accessible.
5. **Mobile-First Scannability & Performance**:
   - Maintain 360px minimum width layout, 44px minimum touch targets, WCAG AA contrast, and reduced-motion preferences.
   - Use existing design tokens and CSS components without duplicated styles or inline CSS hacks.

---

## 3. Non-Goals & Invariants

- **No Schema / Database Migrations**: Zero changes to models or database schema (`makemigrations --check --dry-run` must report 0 changes).
- **No Business Logic Alteration**:
  - Keep conflict detection, database ExclusionConstraints, and transaction safety untouched.
  - Keep approval queues, SLA logic, and delegation logic untouched.
  - Keep room usage management rules untouched.
  - Keep course lodging business rules, phone deduplication, and room allocation logic untouched.
- **No Permissions / Security Compromise**:
  - No server-side permission checks or route protections removed.
  - Roommate privacy invariant preserved: never expose roommate PII in student/public views.
- **No Production Deploy**: Never deploy or trigger production releases.
- **Preserve Untracked Files**: Never touch or commit `.claude/handoffs/` or `.tmp/`.

---

## 4. Potential Risks & Mitigations

1. **Risk**: Existing tests (e.g. `tests_v6_a.py`, `tests_v7_a.py`, `tests_lodging_v4.py`) asserting specific DOM classes or texts on `bookings:calendar`.
   - **Mitigation**: Carefully retain required semantic hooks (`home-entry-grid`, `now-teaching`, `now-meeting`, `today-board`, `stat_free_now`, `stat_in_use`, `สงวนที่พักหลักสูตร`) while improving visual hierarchy and vertical compaction.
2. **Risk**: Mobile navigation overflow when operational menu is added.
   - **Mitigation**: Use clean vertical grouping in `.mobile-menu-panel` with clear section headers and 44px touch targets.
3. **Risk**: Desktop dropdown accessible interaction.
   - **Mitigation**: Use standard `<details>`/`<summary>` with keyboard focus indicators, click-outside auto-dismiss or native toggle, and high-contrast styling matching the design foundation.

---

## 5. Verification & Testing Strategy

1. **Automated Tests**:
   - Create `bookings/tests_ux1.py`:
     - Test navigation links and hierarchy for Guest (simple nav).
     - Test navigation links for Normal Authenticated User (Home, Book, My Bookings, Lodging; no operational clutter).
     - Test navigation links for Approver, Custodian, Lodging Manager (grouped under operational section).
     - Test Reports link is secondary in operational group.
     - Test Task-First Homepage:
       - Approver sees pending approval next action above fold.
       - Custodian sees usage count action above fold.
       - User with booking sees next booking above fold.
       - General user sees quick booking above fold.
       - Operational calendar and today board are present and discoverable.
2. **System Gates**:
   - `uv run pytest bookings/tests_ux1.py -q`
   - `uv run manage.py check`
   - `uv run manage.py makemigrations --check --dry-run`
   - Full regression: `uv run pytest --tb=short -q` (must pass >= 197 tests)
   - `git diff --check`
3. **Real Browser QA (Headless Chrome / CDP)**:
   - Viewports: **360, 390, 430, 768, 1280, 1440 px**.
   - Personas:
     - Guest
     - Authenticated Normal User
     - Authenticated Approver
     - Authenticated Room Custodian
     - Authenticated Lodging Manager
   - Scenarios:
     - Navigation menu toggle and operational dropdown on desktop and mobile.
     - Task-First homepage scan, next action click, quick search click.
     - Verify zero horizontal overflow, visible focus, >= 44px touch targets, and zero console errors.

---

## 6. Branch & PR Strategy
- Branch: `feat/ux-1-task-first-shell-home`
- Base: `feat/lodging-v5-2` (`f0c4fab9b1df9e9825387d8ab8b0e91c00bb41fd`)
- Open PR against `feat/lodging-v5-2` with detailed description upon passing all gates.
- Do NOT merge.
