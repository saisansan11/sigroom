# Deployment Profile

- Verify the current production/pilot architecture from repo configuration before changing deployment assumptions.
- Keep deployment changes separate from feature/UI changes unless the phase explicitly requires both.
- Preserve session/cookie, CSRF, proxy, canonical-host, database connection, static/media, backup/restore, and rollback gates.
- Run preflight and smoke checks against the intended environment; distinguish local/LAN warnings from production blockers.
- Never deploy or change production infrastructure merely to make local tests pass.
- Record exact deploy target, migration state, smoke result, rollback point, and any manual gate in the handoff.
