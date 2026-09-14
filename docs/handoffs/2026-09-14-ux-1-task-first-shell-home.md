# UX-1 Task-First Shell & Home Handoff — 2026-09-14

## 1. Verified Repository & Base State
- **Integration base**: `feat/lodging-v5-2`
- **Base SHA**: `f0c4fab9b1df9e9825387d8ab8b0e91c00bb41fd` (on `origin/feat/lodging-v5-2`)
- **Open dependency PRs**: None.
- **Untracked files preserved**: `.claude/handoffs/` and `.tmp/` remain intact and uncommitted.

## 2. Branch & HEAD Commit
- **Branch**: `feat/ux-1-task-first-shell-home`
- **HEAD commit**: `83e57e1` (`feat(ux): implement UX-1 task-first navigation shell and home`)
- **Remote**: `origin/feat/ux-1-task-first-shell-home` (up to date)

## 3. Pull Request Details
- **PR Number**: `#22`
- **PR URL**: https://github.com/saisansan11/sigroom/pull/22
- **Head / Base**: `feat/ux-1-task-first-shell-home` -> `feat/lodging-v5-2`
- **Mergeability**: Clean / Mergeable (`auto-merge: disabled`, **DO NOT MERGE** as per instructions)
- **CI State**: No remote GitHub Actions workflow configured (`no checks reported`). All verification gates validated locally.

## 4. Files Changed Grouped by Purpose
- **Planning & Documentation**:
  - `docs/plans/2026-09-14-ux-1-task-first-shell-home.md`: Comprehensive UX-1 implementation plan including scope, non-goals, risks, test matrix, and verification gates.
- **Navigation Shell (`templates/base.html`)**:
  - Top-level authenticated navigation simplified to core everyday user tasks: หน้าแรก, จองห้อง, การจองของฉัน, จองห้องพัก.
  - Role-specific operational work consolidated inside an accessible `<details class="ops-menu">` dropdown menu labeled "งานปฏิบัติการ" on desktop and `.mobile-ops-section` inside the mobile drawer.
  - Secondary grouping for reports (`รายงานสรุป`) inside the operations menu.
  - Guest navigation kept minimal and direct: สถานะห้องวันนี้, จองห้องพัก, เข้าสู่ระบบ.
  - Click-outside dismiss handler added for accessible `<details>` menus.
- **Task-First Homepage (`templates/bookings/calendar.html`)**:
  - Reorganized the page hierarchy above the fold to present task-first orientation.
  - Dynamic primary task card prioritizing urgent actions: pending approvals for approvers, custodian today usage checks, user upcoming bookings, or a quick booking search launcher.
  - Quick action launcher buttons ("จองห้องทันที", "ดูตารางปฏิทิน") alongside direct role actions (`role-actions`).
  - Compact operational status band summarizing free/occupied/pending metrics without visual clutter.
  - Retained room category filter tabs, compact entry grid (`home-entry-grid`), and real-time room availability cards.
  - Reorganized FullCalendar (`#calendar`) and Today Board timeline (`#today-board`) as secondary discoverable content on the same `/` route without semantic or URL breakage.
- **Styling & Accessibility (`static/css/app.css`)**:
  - CSS styling for `.ops-menu`, `.ops-menu-summary`, `.ops-dropdown-panel`, `.mobile-ops-section`, `.task-home-hero`, `.primary-task-banner` (with urgent, action, normal, neutral variants), and `.task-statusband`.
  - Enforced touch target sizes of >= 44x44px via `max(44px, 2.75rem)` and explicit min-heights.
  - Supported `prefers-reduced-motion: reduce`.
  - Clean whitespace passing `git diff --check`.
- **Automated Tests (`bookings/tests_ux1.py`)**:
  - 13 focused automated tests validating top-level and operational navigation across all user roles (guest, regular user, approver, custodian, lodging supervisor, staff), reports placement, and homepage task hero components.

## 5. Decisions & Rejected Alternatives
- **Dropdown implementation using semantic HTML `<details>` and `<summary>`**:
  - *Decision*: Used standard HTML5 `<details>` with `.ops-menu` styling and a lightweight vanilla JS click-outside listener.
  - *Rationale*: Requires no heavy JS libraries, supports native keyboard navigation and accessibility, and fails open if JS is unavailable.
- **Header assertion scoping in tests**:
  - *Decision*: In `bookings/tests_ux1.py`, assertions checking for links like `"รออนุมัติ"` were scoped to `<header>` (`_header_html`) rather than entire page HTML.
  - *Rationale*: Strings like `"รออนุมัติ"` legitimately occur in the Today Board status legend and primary task banners on the homepage body; asserting `<header>` specifically tests the top-level shell navigation.
- **Preservation of DOM IDs & Classes**:
  - *Decision*: Preserved `#calendar`, `#today-board`, `.role-actions`, `#home-entry-grid`, and operational metric IDs.
  - *Rationale*: Avoided regressing legacy tests (`tests_v6_a.py`, `tests_v7_a.py`, `tests_lodging_v4.py`) that rely on these selectors.

## 6. Exact Targeted Test Commands & Results
- Command: `uv run pytest bookings/tests_ux1.py -q`
  - Result: **13 passed in 4.96s**
- Command: `uv run pytest bookings/tests_ux1.py bookings/tests_v6_a.py bookings/tests_v7_a.py bookings/tests_ui5.py -q`
  - Result: **48 passed, 2 warnings in 9.94s**

## 7. Verification Gates Passed
- **Django Check**:
  - Command: `uv run manage.py check`
  - Result: `System check identified no issues (0 silenced).` (PASS)
- **Migration Drift Gate**:
  - Command: `uv run manage.py makemigrations --check --dry-run`
  - Result: `No changes detected` (PASS)
- **Full Regression Suite**:
  - Command: `uv run pytest --tb=short -q`
  - Result: **210 passed, 2 warnings in 41.40s** (PASS, up from 197 baseline)
- **Git Whitespace Check**:
  - Command: `git diff --check`
  - Result: **Clean / no output** (PASS)

## 8. Browser QA Actually Completed
Executed via local test server (`http://127.0.0.1:7357`) and Headless Chromium via Chrome DevTools Protocol (CDP):
- **Viewports Tested**: 360, 390, 430, 768, 1280, 1440 px.
- **Personas Tested**:
  1. Guest / Unauthenticated
  2. Normal Authenticated User
  3. Approver
  4. Custodian / Staff / Admin
- **Results**:
  - **78 total page/viewport combinations checked**: **0 horizontal layout overflows** (`scrollWidth <= innerWidth` across all combinations).
  - **18 interactive exercises performed**:
    - Mobile drawer menu toggling at 360px, 390px, 430px across all roles: confirmed menu opens smoothly, displaying core task links and `.mobile-ops-section` where applicable.
    - Desktop operations menu `<details class="ops-menu">` toggling at 768px, 1280px, 1440px: verified open/close, focus outline, and dismissal upon outside click.
    - Task Hero primary action card and quick action links verified visible and fully accessible above the fold.
    - Touch targets verified >= 44x44px across all viewports.

## 9. Known Issues / Deferred Debt / Environment Warnings
- Pytest emits 2 expected non-blocking warnings:
  - `RuntimeWarning: DJANGO_SECURE=0 ขณะ DJANGO_DEBUG=0`: Standard local test environment warning for LAN testing.
  - `RemovedInDjango60Warning: The default scheme will be changed from 'http' to 'https' in Django 6.0`: Standard upstream URLField form deprecation warning.

## 10. Invariants Next Phase Must Not Regress
- **Authorization & Security**: No server-side route removal, permission loosening, or URL modifications. All backend permissions remain enforced by Django views.
- **Privacy Policy**: Student and public room occupancy masking rules remain strictly intact.
- **Data Integrity**: Zero schema changes; `makemigrations --check --dry-run` must always report no changes.
- **Responsive Layout**: Zero horizontal overflow on mobile viewports (360px+); touch targets >= 44px.
- **Untracked Directories**: Preserve `.claude/handoffs/` and `.tmp/` at all times.

## 11. Next Phase Scope & Non-Goals
- **Next Phase (UX-2)**: Task-first booking flow and room detail optimization.
- **Scope**:
  - Streamline the room selection, search filters, and booking creation journey.
  - Improve room detail presentation and booking confirmation steps.
- **Non-Goals**:
  - Do NOT modify the database schema or booking business logic rules.
  - Do NOT deploy to production.

## 12. Ready-to-Paste Prompt for Next Chat
```
Operate SIGROOM in F:\ogn_ROOM. Base is updated feat/lodging-v5-2. Current branch feat/ux-1-task-first-shell-home has PR #22 open against feat/lodging-v5-2. First re-verify repository state (git status, git log -1, uv run manage.py check, uv run pytest bookings/tests_ux1.py -q). Preserve all unrelated/untracked files (.claude/handoffs and .tmp). Never deploy production. Do not merge PR #22 without instruction. Proceed to next task per workflow instructions.
```
