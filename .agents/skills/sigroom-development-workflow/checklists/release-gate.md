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
- CI/status checks PASS when configured; if none exist, state that explicitly
- dependency/base PR state recorded for stacked work

Never merge without an explicit user instruction.
