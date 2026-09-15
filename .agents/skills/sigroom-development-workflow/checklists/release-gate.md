# Release / PR Gate

Required before a normal SIGROOM PR is declared ready:

- self-review complete
- targeted tests PASS
- `uv run manage.py check` PASS
- `uv run manage.py makemigrations --check --dry-run` reports no unintended changes
- full `uv run pytest` PASS
- `git diff --check` PASS
- Browser QA PASS for user-facing changes
- complete diff reviewed before staging
- only scoped files staged
- branch pushed
- PR diff re-reviewed
- GitHub Actions aggregate check **PR Safety Gate** PASS when CI is available for the target PR; once required on the protected default branch, never bypass it
- dependency/base PR state recorded for stacked work

Never merge without an explicit user instruction.
