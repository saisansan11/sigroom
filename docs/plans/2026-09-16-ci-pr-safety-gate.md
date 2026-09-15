# SIGROOM CI / PR Safety Gate — Implementation Plan

## Status
`GITHUB CI PASS + BRANCH PROTECTION ACTIVE — FINAL DOCS CI PENDING`

## 1. Verified source of truth
- Repository: `saisansan11/sigroom`
- Default / integration branch: `feat/lodging-v5-2`
- Verified base SHA: `5ee980c6134433977947f03203bc23b0fa0dbe9c`
- Base includes merged PR #26 (`UX-5: Improve series booking management on mobile`).
- Open PRs at plan start: none.
- GitHub reported the default branch as **not protected**.
- Canonical `F:\ogn_ROOM` contains unrelated local work, so this phase uses an isolated worktree only.
- Implementation branch: `chore/ci-pr-safety-gate`.

## 2. Goal
Add a repeatable GitHub Actions safety gate so every pull request is independently verified by GitHub before merge, then protect the default branch with one stable required check.

The intended release flow becomes:

`implementation/review → PR → GitHub CI → PR Safety Gate green → user explicitly approves merge → merge`

## 3. CI design
Create `.github/workflows/pr-safety-gate.yml` with least-privilege `contents: read`, stale-run cancellation, Python 3.12, PostgreSQL 16, and the locked `uv` environment.

Use four independent verification jobs plus one aggregate gate:

1. **Repository checks**
   - whitespace/error check against the actual PR diff (`git diff --check` with PR base/head SHAs)
   - `uv sync --frozen`
   - `uv run manage.py check`
   - `uv run manage.py makemigrations --check --dry-run`

2. **Critical regression**
   - PostgreSQL-backed focused tests covering authentication/password handling, booking privacy/conflicts, lodging/public flows, approvals/permissions, audit behavior, and security/deployment contracts.
   - This is deliberately smaller than the full suite so failures surface quickly.

3. **Full regression**
   - PostgreSQL-backed `uv run pytest --tb=short -q`.

4. **Security audit**
   - Run `uv run manage.py check --deploy` using production-like secure settings; allow only the explicitly documented HSTS policy warnings `security.W005` and `security.W021`, and fail on any other Django deploy security warning/error.
   - Export locked runtime dependencies from `uv.lock` and audit them with a pinned `pip-audit` version.
   - No repository or deployment secrets are required.

5. **PR Safety Gate**
   - depends on all four jobs;
   - always evaluates their outcomes;
   - succeeds only when every required job succeeded.
   - This stable job name is the only status check intended for branch protection.

## 4. Supply-chain choices
- Pin external GitHub Actions to immutable commit SHAs, with their release tags documented inline.
- Pin the `uv` tool version used in CI.
- Pin the `pip-audit` version used by the security job.
- Do not grant write permissions to workflow jobs.

Verified versions at plan time (2026-09-16):
- `actions/checkout` v7.0.1
- `actions/setup-python` v7.0.0
- `astral-sh/setup-uv` v10.1.0
- local/CI target `uv` 0.11.19
- `pip-audit` 2.10.1

## 5. Branch protection rollout
Do **not** guess the required-check context before GitHub has produced a real run.

Sequence:
1. implement and locally review workflow;
2. push branch and open PR to `feat/lodging-v5-2`;
3. observe the real GitHub Actions check names and results;
4. require the observed aggregate **PR Safety Gate** context on `feat/lodging-v5-2`;
5. require pull requests before merging and prevent accidental direct merge paths as supported by repository settings;
6. re-query GitHub protection state and record exact settings;
7. leave the CI PR open until the user explicitly authorizes merge.

## 6. Explicit non-goals
- No application feature/UI/business-rule changes.
- No database schema or migration changes.
- No production deploy or Cloud Run/Firebase changes.
- No secret creation or secret exposure.
- No forced pushes, history rewrite, or cleanup of unrelated worktrees.
- No merge without a new explicit user instruction.

## 7. Local verification before PR — observed 2026-09-16
Because this phase changes repository automation rather than user-facing UI, real browser QA is **not applicable**.

Observed gates:
- workflow YAML/structure validation: **PASS**; exactly 5 intended jobs and **12 immutable 40-character action SHA references**;
- Python runtime verification: **3.12.10**;
- exact critical regression selection: **68 passed**;
- `uv run manage.py check`: **System check identified no issues (0 silenced)**;
- `uv run manage.py makemigrations --check --dry-run`: **No changes detected**;
- full `uv run pytest --tb=short -q`: **237 passed**;
- dependency audit from hashed runtime export of `uv.lock` with `pip-audit==2.10.1`: **No known vulnerabilities found**;
- production-like Django deploy check reports only known `security.W005` and `security.W021`; CI explicitly allows only these two HSTS policy warnings and fails on any other Django deploy security warning/error;
- `git diff --check`: **PASS** (only line-ending normalization notices for two existing CRLF docs);
- canonical `F:\ogn_ROOM` unrelated dirty working tree was not used for implementation and must remain untouched.

The two accepted HSTS warnings are not silently fixed here: `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` require an explicit domain-wide HTTPS/preload decision and are unsafe to enable merely to make CI green.

## 8. GitHub rollout observed — 2026-09-16
- PR #27 opened against `feat/lodging-v5-2`.
- GitHub Actions run `35029859996`: **SUCCESS**.
- `Repository checks`, `Critical regression`, `Full regression`, `Security audit`, and aggregate `PR Safety Gate`: **SUCCESS**.
- Branch protection is active on `feat/lodging-v5-2` with strict required check `PR Safety Gate`, PR-required flow, admin enforcement, 0 approving reviews, force-push disabled, and deletion disabled.
- A non-blocking setup-uv cache reservation annotation was observed from parallel jobs; it did not affect dependency installation or test results.

## 9. Acceptance criteria
- GitHub Actions executes successfully on the CI PR using PostgreSQL 16 and the repository lockfile.
- Aggregate check reports success only when all four subordinate jobs succeed.
- No workflow job has write permissions.
- Default branch protection requires the observed aggregate check and PR-based merging.
- The CI PR is `OPEN`, mergeable, and green when reported `READY FOR MERGE`.
- User retains the final merge decision.
