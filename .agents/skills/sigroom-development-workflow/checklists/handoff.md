# Handoff Checklist

End each phase with a ready-to-paste handoff for a new chat.

Include:

1. verified repository/base state and open dependency PRs
2. branch and HEAD commit
3. PR number, URL, head/base, mergeability and CI state
4. files changed grouped by purpose
5. decisions and rejected alternatives that matter later
6. exact targeted test commands/results
7. `manage.py check`, migration drift check, full regression, `git diff --check`
8. Browser QA routes, roles, viewports and interactions actually completed
9. known issues / deferred debt / environment warnings
10. invariants that the next phase must not regress
11. next phase scope and non-goals
12. a complete prompt for the next chat that starts by re-verifying the repo

Never state a gate passed unless its result was observed in the current work.
