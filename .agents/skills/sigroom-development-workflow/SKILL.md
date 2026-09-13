---
name: sigroom-development-workflow
description: Enforces the SIGROOM repository workflow for implementation, review, UI, lodging, booking, security, deployment, regression testing, browser QA, pull requests, and handoffs. Use for any substantive development work in SIGROOM.
---

# SIGROOM Development Workflow

Use this skill for every substantive change in SIGROOM. The live repository is the source of truth; handoffs are context, not authority.

## Mandatory loop

`DISCOVER → READ SOURCE OF TRUTH → VERIFY CURRENT STATE → WRITE IMPLEMENTATION PLAN → CREATE ISOLATED BRANCH → IMPLEMENT SMALL SCOPE → SELF REVIEW → TARGETED TESTS → FULL REGRESSION → REAL BROWSER QA → DIFF REVIEW → COMMIT + PUSH → OPEN PR → CHECK CI → WRITE HANDOFF`

Do not skip a gate merely because an earlier handoff reported PASS.

## Source of truth

1. Inspect `git status`, current branch, recent log, remotes, open PRs, base branch, and relevant docs before editing.
2. Prefer current repo state over chat summaries, handoff files, or assumptions.
3. Read the files that own the behavior before proposing a fix.
4. Preserve unrelated working-tree and untracked files. Never clean, delete, stage, or commit them without explicit scope.
5. Keep SIGROOM business rules in services/models, not templates or visual-only code.

See [checklists/preflight.md](checklists/preflight.md).

## Plan and branch

- Write a scoped implementation plan before editing.
- State what is intentionally out of scope.
- Never develop directly on the shared base branch.
- Use one isolated branch per phase or coherent change.
- If the base work is still an open PR, use a stacked branch/PR and record the dependency explicitly.

## Implementation discipline

- Make the smallest coherent change that satisfies the phase.
- Reuse existing components and semantic tokens before adding new ones.
- Do not redesign proven booking/lodging logic merely to change presentation.
- Avoid speculative abstractions, duplicate CSS, dead code, and unrelated cleanup.
- Preserve privacy, permissions, database constraints, and migration discipline.

Use the matching profile when relevant:
- [profiles/ui-refresh.md](profiles/ui-refresh.md)
- [profiles/lodging.md](profiles/lodging.md)
- [profiles/security.md](profiles/security.md)
- [profiles/deployment.md](profiles/deployment.md)

## Verification gates

Before calling a change complete:

1. Self-review the diff as an independent reviewer.
2. Run targeted tests for changed behavior.
3. Run `uv run manage.py check`.
4. Run `uv run manage.py makemigrations --check --dry-run` for normal application changes.
5. Run the full test suite with `uv run pytest`.
6. Run `git diff --check`.
7. Perform real Browser QA when the change affects user-facing behavior or navigation.
8. Re-run relevant tests after fixing any issue found during review or Browser QA.

A targeted test pass is never evidence that full regression passed. Classify failures before changing code or tests: **code regression**, **stale/time-brittle test**, or **environment problem**. Never weaken a test merely to make CI green without proving the intended behavior.

See [checklists/code-review.md](checklists/code-review.md), [checklists/browser-qa.md](checklists/browser-qa.md), and [checklists/release-gate.md](checklists/release-gate.md).

## Git and PR contract

- Review the complete diff before staging.
- Stage only scoped files.
- Commit messages must identify the scope and intent.
- Push the branch and open a PR against the verified base.
- Re-read the PR diff after opening it.
- Check CI/status checks when available; report clearly when no CI exists.
- **Never merge a PR unless the user explicitly instructs you to merge it.**

## Handoff contract

Every phase ends with a handoff containing:
- verified base state and dependency PRs
- branch
- commit
- PR and base branch
- files changed
- design/architecture decisions
- targeted tests
- full regression result
- Browser QA roles/viewports/interactions actually tested
- CI result or explicit absence of CI
- known issues / deferred debt
- invariants that must not be regressed
- next phase
- ready-to-paste prompt for the next chat

See [checklists/handoff.md](checklists/handoff.md).

## Stop conditions

Do not claim PASS or DONE when a required gate is incomplete. Report the exact incomplete gate and continue if it can be completed safely in the current session. Do not merge, delete unrelated files, reset other people's work, or alter production infrastructure outside the current approved scope.
