# Booking integrity audit handoff — 2026-10-03

## State and scope

- Verified remote default/base: `feat/lodging-v5-2`, `69d4b75` (PR #79 merged). No open PRs at preflight; no dependency PR.
- Branch: `fix/bug-audit-20261003`; worktree: `F:/ogn_ROOM/.worktrees/bug-audit-20261003`.
- Original checkout and unrelated untracked work preserved. No production deployment, data change or merge.
- Reviewed booking submission/cancellation/search, series, amendment, preemption, approval, usage and lodging allocation service paths. This is a focused integrity review, not a claim that every application path is bug-free.

## Confirmed defects and fixes

1. **P1 — stale cancellation overwrites current state/revision and bypasses a changed cutoff.** `cancel_booking` now reloads the booking under `select_for_update` before permission, state and time checks, matching amendment/approval transaction discipline.
2. **P1 — lodging conflict detection ignores regular-booking buffers when the cohort exists first.** Shared conflict detection now uses `compute_hold`, making cohort-first and booking-first checks agree. Exact adjacent half-open boundaries remain valid; amendment validation shares the fix.
3. **P1 — rooms without an optional ResourceRule bypass blackouts/outages.** Closure checks now execute before the no-rule early return, so search and submission both reject closed rooms.

Files: `bookings/services.py`, `bookings/lodging_services.py`, `bookings/tests_integrity_audit.py`, implementation plan and this handoff. No schema, UI template, permission policy or exclusion-constraint change.

## Verification observed

Using existing Python 3.12 environment via `UV_PROJECT_ENVIRONMENT=F:/ogn_ROOM/.venv` and installed uv executable:

- Baseline `uv run pytest -q --tb=short`: **774 passed** (178.38s).
- New reproduction tests before fixes: **9 failed, 2 passed**. Failures demonstrated stale terminal states, changed deadline, revision loss, both closure types, and both buffer directions.
- Targeted `uv run pytest bookings/tests_integrity_audit.py bookings/tests_m2.py bookings/tests_m5.py bookings/tests_lodging_v4.py bookings/tests_bugfix_booking_status.py -q --tb=short`: **66 passed** (113.35s), before adding reverse-order and amendment coverage.
- Final full `uv run pytest -q --tb=short`: **786 passed** (151.02s), including 12 new regression cases and reverse-order/adjacent-boundary checks.
- `uv run manage.py check`: no issues.
- `uv run manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: clean. Source diff and new tests reviewed.
- Existing local warnings: SMTP host absent, DEBUG/SECURE local configuration, proxy-IP configuration and uncollected static directory. No production configuration inferred or changed.

## Real browser QA

Dedicated local PostgreSQL database `sigroom_audit_qa_20261003`; synthetic user and rooms only; local server `127.0.0.1:8013`.

Edge desktop (default viewport): signed in as ordinary requester, opened booking detail, opened cancellation confirmation. On search, expanded unavailable-room reasons and observed `ห้องงดใช้: ปิดซ่อม QA` for a room without ResourceRule. Changed dropdowns from 09:00–10:00 to 10:00–11:00 and observed both rooms become available, proving adjacency is accepted. No captured console errors on search.

Edge mobile viewport override 390x844 (reported inner viewport 390x845): changed dropdowns back, expanded unavailable-room reasons and observed correct closure text; document width did not overflow.

**Incomplete:** cancellation confirmation could not be completed through browser automation because the browser control timed out (`Emulation.setFocusEmulationEnabled`). No successful cancellation POST observed in server log. Screenshot capture also timed out; no screenshot evidence claimed. Viewport reset was requested but could not be verified after control errors. Student/supervisor buffer scenarios validated by automated tests, not browser interactions. Keep PR draft until these browser gates are completed.

## Invariants and rollback

Retain PostgreSQL exclusion constraints and ordered resource locks; cohort conflict checks include regular-booking buffers; exact touching boundaries remain non-conflicting. Never trust a caller's stale booking state for cancellation. Closures apply with or without ResourceRule. Revert this scoped commit to roll back; no schema rollback needed.

## Next step / continuation prompt

Read AGENTS.md and the SIGROOM workflow, reverify Git/GitHub state, then continue `fix/bug-audit-20261003`. Review this handoff and current PR. Automated regression is 786 passing. Complete local browser cancellation plus lodging buffer scenarios, recover browser screenshot capture, verify/reset any viewport override, inspect PR Safety Gate, and update the draft PR readiness. Preserve all unrelated files; do not merge or deploy without user instructions.

PR URL, final commit and CI outcome are recorded in the completion report after publication.
