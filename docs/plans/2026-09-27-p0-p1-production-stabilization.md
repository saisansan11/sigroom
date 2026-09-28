# P0 Production Stabilization / P1 UX Acceptance

Base: `9145a79ba7abbdac045c343cf6b3a283835e16e1` (production revision `sigroom-00066-88b`).
Branch: `codex/p0-p1-production-stabilization`.

## Scope

1. Read current Cloud Run revision, migration execution, request/error logs, and browser console without changing production.
2. Exercise the public service gateway at 320, 360, 390, 430, 768, 1024, and 1440 px; follow booking and staff links as a guest.
3. Record observed P0/P1/P2 findings and verification limits in a new QA register.
4. Fix the observed `/favicon.ico` 404 by declaring the existing static PNG icon in the shared page head and routing the root icon request to it.

## Boundaries

No production deployment, migration, infrastructure change, booking submission, credential use, or PR merge. Authenticated role routing requires role-specific test accounts or an approved safe test environment; guest redirects alone cannot prove it.

## Verification

Review the diff; run the icon/template test, Django check, migration drift check, full pytest, and diff whitespace check. Revisit the changed page in a local browser if the environment allows it. Production remains on the baseline SHA until a separate deployment approval.
