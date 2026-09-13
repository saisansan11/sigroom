# Code Review Checklist

Review the final diff as if you did not implement it.

- Change matches the phase plan and does not smuggle unrelated cleanup.
- No business rule or permission moved into presentation code.
- No accidental privacy expansion or sensitive data rendering.
- No duplicated CSS/logic where an existing component/token fits.
- Template conditions cover empty/permission/error states.
- Keyboard/focus/mobile behavior remains usable.
- No unnecessary complexity, dead code, debug output, or stale comments.
- No migration/schema change unless explicitly required and reviewed.
- Tests validate intended behavior rather than implementation trivia.

Fix findings before opening the PR, then rerun relevant gates.
