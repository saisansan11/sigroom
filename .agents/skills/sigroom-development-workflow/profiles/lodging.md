# Lodging Profile

Preserve the V5.1 invariants unless the user explicitly changes requirements.

- `is_active` controls student-portal open/closed state; it is not allocation state.
- `allocation_status` controls allocated/released lodging resources.
- Conflict checking must remain bidirectional across lodging cohorts and regular bookings.
- Resource allocation mutations must retain transaction/race protection.
- Authorization must remain server-side; UI hiding is not authorization.
- Public/student views expose only the minimum required personal data. Do not introduce roommate PII.
- Duplicate/normalized phone behavior and bed-range validation must not regress.
- Calendar lodging reservations remain non-clickable/background semantics where required.
- Admin paths must apply the same conflict and integrity rules as normal flows.

When changing lodging UI, test both student-facing and supervisor/management paths and verify privacy with rendered output, not only model/service tests.
