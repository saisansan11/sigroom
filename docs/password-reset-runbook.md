# SIGROOM — Audited Password Reset Runbook

## Purpose

Use `reset_user_password` when an existing SIGROOM account owner cannot recover the current password and an authorized administrator must issue a temporary password.

This command exists to avoid raw database edits, ad-hoc password hashes, password bypasses, and plaintext secrets in command arguments or application audit logs.

## Safety contract

The command resets exactly one existing active user and:

- requires an existing **active superuser** as `--operator`;
- requires an exact write confirmation `--confirm RESET:<username>`;
- accepts the temporary password only from `--password-file` or `--password-stdin`;
- never accepts a plaintext `--password <value>` argument;
- validates the new password with the configured Django password validators;
- locks the operator and target rows inside one database transaction;
- changes only the target password and `must_change_password` flag;
- sets `must_change_password=True` so the account owner must choose a new password after login;
- writes one append-only `AuditLog` event named `password_reset_by_admin_command`;
- never stores the plaintext password or encoded password hash in the audit row;
- suppresses the generic registry audit for the same password write to avoid duplicate/noisy credential events;
- does not change username, email, unit, role/group membership, superuser state, permissions, bookings, room data, or deployment state.

Inactive target accounts are rejected. Account reactivation is a separate administrative decision.

## 1. Dry-run first

Dry-run validates the target and operator and performs no write. It does not require or read a password secret.

```powershell
uv run manage.py reset_user_password wasan.t `
  --operator wasan.t `
  --dry-run
```

Expected result includes:

```text
DRY RUN PASS target=wasan.t operator=wasan.t active_target=true active_superuser_operator=true
```

Self-reset is permitted only when the operator account itself is an active superuser. The infrastructure/IAM identity that launches the command is still responsible for controlling who can execute Production jobs.

## 2. Prepare a temporary password securely

Do **not** put the password directly in the command line because command arguments can be retained in shell history, Cloud Run execution metadata, or audit systems.

Recommended secret sources:

### Option A — local/administrative environment: password file

Create a temporary file outside the repository and restrict access to the operator. The file must contain exactly one password line.

Example path:

```text
C:\Temp\sigroom-wasan-reset.txt
```

The command does not delete this file automatically. Delete it securely after the owner has logged in and changed the password.

### Option B — interactive or piped stdin

```powershell
uv run manage.py reset_user_password wasan.t `
  --operator wasan.t `
  --password-stdin `
  --confirm RESET:wasan.t
```

When stdin is a terminal, the command uses a hidden password prompt. When stdin is piped, it reads at most 4096 bytes and requires one non-empty line.

## 3. Execute the reset

Using a password file:

```powershell
uv run manage.py reset_user_password wasan.t `
  --operator wasan.t `
  --password-file C:\Temp\sigroom-wasan-reset.txt `
  --confirm RESET:wasan.t
```

Successful output contains only the username, `must_change_password=true`, and the audit row ID. It never prints the password.

## 4. First login

After the reset:

1. the account owner signs in using the temporary password;
2. middleware redirects the account to `/accounts/change-initial-password/` because `must_change_password=True`;
3. the owner supplies the temporary password as the old password and chooses a new password;
4. `complete_initial_password_change()` validates and saves the owner-selected password, clears the flag, and records `initial_password_changed` in AuditLog.

## 5. Verification

Verify all of the following:

- target user can authenticate with the temporary password before the first-login change;
- the user is forced to `/accounts/change-initial-password/`;
- after changing it, `must_change_password=False`;
- the temporary password no longer authenticates;
- AuditLog contains `password_reset_by_admin_command` with the expected operator and target;
- AuditLog contains `initial_password_changed` after the owner completes the forced change;
- no audit row contains plaintext password or a password hash.

## Production / Cloud Run guidance

Do not pass a Production temporary password through `gcloud run jobs execute --args` or `--update-env-vars`, because those values can be retained in execution metadata.

For Cloud Run, use one of these approved patterns:

1. mount a Secret Manager secret as a file and pass only the mounted **file path** to `--password-file`; or
2. run the management command from a trusted administrative environment connected to Cloud SQL and use the hidden `--password-stdin` prompt.

The current `sigroom-migrate` job should not be permanently repurposed just to reset a password. Any Production job configuration change or application deployment remains behind the normal explicit Production approval gate.

## Rollback / incident note

A password reset cannot restore the previous plaintext password because SIGROOM stores only a one-way password hash. If a reset is performed in error, issue another controlled reset using this same command and document the corrective action in the incident/change record.
