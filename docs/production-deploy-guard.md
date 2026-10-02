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

After Cloud Build succeeds (and only in `-Deploy` mode) the wrapper continues with the Firebase Hosting half of the release:

1. `uv run python manage.py collectstatic --noinput --clear` (with a dummy `DJANGO_SECRET_KEY` scoped to that process only, same as the Dockerfile) fills `public/static/` from the exact committed tree, so it matches the image just deployed. `public/static/` is git-ignored; `public/index.html` (the splash page) is committed.
2. The wrapper refuses to continue unless `public/index.html` and `public/static/staticfiles.json` exist.
3. `firebase deploy --only hosting:sigroom --project sixth-storm-439008-u2 --non-interactive` uploads `public/`. `hosting:sigroom` is the site id declared via `"site": "sigroom"` in `firebase.json` (Firebase CLI accepts a site id or a target name after `hosting:`); a wrong id makes the CLI fail instead of deploying elsewhere. The site and project are fixed constants in the script, not parameters.
4. Smoke check: `GET https://sigroom.web.app/home/` is retried for up to ~60 seconds; the script prints an OK/FAIL line in Thai and exits non-zero on FAIL.

The Cloud Build trigger `auto-deploy-sigroom` stays disabled; the guard that requires this is unchanged. If Cloud Build passes but Firebase fails, rerunning the same release is safe (the build/migrate/deploy steps are idempotent for the same SHA).

### One-click wrapper

`deploy-sigroom.cmd` (repo root) is a double-click front-end for the same script. It reads `HEAD`, runs the check-only preflight, shows the commit SHA and latest commit message, requires the operator to type `DEPLOY` exactly, then runs the script with `-Deploy -ConfirmProduction DEPLOY`. It does not bypass or duplicate any guard; every guard above still runs inside the PowerShell script.

### Cold start / min-instances

Cloud Run is intentionally NOT kept warm (scale to zero, startup CPU boost on). The first visitor after idle sees the static splash from Firebase Hosting for roughly 5-15 seconds. If this ever needs to change (costs money continuously), run, for example: `gcloud run services update sigroom --min-instances=1 --region=asia-southeast3 --project=sixth-storm-439008-u2 --configuration=sigroom`, and revert with `--min-instances=0`.

## Negative check

This must fail before any production action:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-sigroom-production.ps1 `
  -CommitSha <FULL_40_CHAR_SHA> `
  -Project signal-nco-ew
```

Expected result: `BLOCKED` / non-zero exit. Never weaken this check to make a release proceed.
