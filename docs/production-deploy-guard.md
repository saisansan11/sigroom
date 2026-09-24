# SIGROOM Production Deploy Guard

Use this path for every manual SIGROOM production release. Do not rely on the machine's active/default gcloud project.

## Fixed production target

- gcloud configuration: `sigroom`
- project: `sixth-storm-439008-u2`
- region: `asia-southeast3`
- Cloud Run service: `sigroom`
- Cloud Build trigger `auto-deploy-sigroom`: must remain disabled for manual releases

The local machine may keep another gcloud configuration active. The SIGROOM deploy wrapper always uses the named `sigroom` configuration and explicit project/region flags.

## One-time local configuration

Create the SIGROOM configuration without activating it, then bind only the SIGROOM target to it:

```powershell
gcloud config configurations create sigroom --no-activate
gcloud config set account <AUTHORIZED_ACCOUNT> --configuration=sigroom
gcloud config set project sixth-storm-439008-u2 --configuration=sigroom
gcloud config set run/region asia-southeast3 --configuration=sigroom
```

Do not change the machine-wide active/default configuration merely to deploy SIGROOM. Do not change Application Default Credentials quota-project as part of this setup.

## Check-only preflight

From the exact commit intended for release:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-sigroom-production.ps1 `
  -CommitSha <FULL_40_CHAR_SHA>
```

A passing preflight verifies all of the following before any build or production write:

1. requested project is exactly `sixth-storm-439008-u2`
2. requested region is exactly `asia-southeast3`
3. requested service is exactly `sigroom`
4. requested gcloud configuration is exactly `sigroom`
5. approved SHA is a full SHA and exactly matches worktree `HEAD`
6. worktree is clean, including non-ignored untracked files, so uncommitted code cannot be published under an approved SHA
7. named gcloud configuration points to the expected project and region
8. `auto-deploy-sigroom` is disabled
9. the Cloud Run service lookup resolves to `sigroom`

Any mismatch exits non-zero before Cloud Build is submitted.

## Production release

Only after explicit production approval:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-sigroom-production.ps1 `
  -CommitSha <FULL_40_CHAR_SHA> `
  -Deploy `
  -ConfirmProduction DEPLOY
```

The wrapper submits `cloudbuild.yaml` with an explicit project, named configuration, and exact `COMMIT_SHA`. `cloudbuild.yaml` then builds/pushes the exact tag, runs `sigroom-migrate`, and deploys Cloud Run.

## Negative check

This must fail before any production action:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-sigroom-production.ps1 `
  -CommitSha <FULL_40_CHAR_SHA> `
  -Project signal-nco-ew
```

Expected result: `BLOCKED` / non-zero exit. Never weaken this check to make a release proceed.
