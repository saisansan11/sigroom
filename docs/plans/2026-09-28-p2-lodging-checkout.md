# P2 Lodging checkout and bed release

## Verified starting point

- Production remains on revision `sigroom-00066-88b` (100% traffic).
- PR #68 is open and passing; this change stacks on its head `bd77b8f`.
- The first Production QA journey exposed `SIG-P2-001`: check-in succeeds, but no supported staff checkout can return the bed.
- The QA reservation was cleaned up; the 100-run ledger records 1 completed, failed journey.

## Scope

1. Add a distinct `checked_out` release outcome for a checked-in guest. Keep cancellation and no-show limited to guests who have not checked in.
2. Preserve check-in time and confirming staff in immutable release history, and record a separate checkout audit action.
3. Expose checkout only in the authorized staff workspace. Require a reason and show clear success/error feedback.
4. Cover authorization, transition rules, duplicate attempts, history, audit, inventory, stale public/private capabilities, and rendered workspace behavior.

## Boundaries

- Do not merge PR #68 or this change, deploy, mutate Production, or touch real-user reservations.
- Do not reinterpret a checked-in guest as a cancellation or no-show.
- Do not modify the unrelated root checkout or its untracked files.
- The Production 100-run acceptance remains open until the code is deployed with separate approval and all journeys are recorded.

## Verification

Run targeted lodging tests, Django check, migration drift check, full pytest, diff check, and local browser QA for staff checkout and denied access. Review the exact stacked PR diff and CI before handoff.
