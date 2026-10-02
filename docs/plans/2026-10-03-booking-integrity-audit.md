# Booking integrity bug audit — 2026-10-03

Base: origin/feat/lodging-v5-2 at 69d4b75; no open PRs observed.
Branch: fix/bug-audit-20261003 in an isolated worktree.

Review booking, approval, usage and lodging services, then reproduce confirmed defects with regression tests. Fix stale cancellation state, asymmetric lodging-buffer conflict checks, and any confirmed related booking-window validation gap. Preserve database exclusion constraints and resource locking.

Non-goals: UI redesign, production changes, unrelated files, schema changes, dependency upgrades, merge.

Verification: failing-before/passing-after targeted tests, Django check, migration drift, full pytest, diff review, real local browser interactions for affected flows. Commit scoped files, push, open PR, inspect CI and write handoff. Report any environment or pre-existing failures accurately.
