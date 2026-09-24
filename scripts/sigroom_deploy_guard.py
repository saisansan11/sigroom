from __future__ import annotations

import argparse
import re
import sys

EXPECTED_PROJECT = "sixth-storm-439008-u2"
EXPECTED_REGION = "asia-southeast3"
EXPECTED_SERVICE = "sigroom"
EXPECTED_CONFIGURATION = "sigroom"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_target(
    *,
    project: str,
    region: str,
    service: str,
    configuration: str,
    commit_sha: str,
    head_sha: str,
) -> list[str]:
    errors: list[str] = []
    if project != EXPECTED_PROJECT:
        errors.append(f"project must be {EXPECTED_PROJECT!r}, got {project!r}")
    if region != EXPECTED_REGION:
        errors.append(f"region must be {EXPECTED_REGION!r}, got {region!r}")
    if service != EXPECTED_SERVICE:
        errors.append(f"service must be {EXPECTED_SERVICE!r}, got {service!r}")
    if configuration != EXPECTED_CONFIGURATION:
        errors.append(
            f"configuration must be {EXPECTED_CONFIGURATION!r}, got {configuration!r}"
        )
    if not SHA_RE.fullmatch(commit_sha):
        errors.append("commit SHA must be a full 40-character lowercase Git SHA")
    if not SHA_RE.fullmatch(head_sha):
        errors.append("HEAD SHA must be a full 40-character lowercase Git SHA")
    if SHA_RE.fullmatch(commit_sha) and SHA_RE.fullmatch(head_sha) and commit_sha != head_sha:
        errors.append(f"approved commit {commit_sha} does not match worktree HEAD {head_sha}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed target validator for SIGROOM production deploys."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = validate_target(
        project=args.project,
        region=args.region,
        service=args.service,
        configuration=args.configuration,
        commit_sha=args.commit_sha,
        head_sha=args.head_sha,
    )
    if errors:
        print("BLOCKED: SIGROOM production target validation failed.", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print(
        "TARGET PASS: "
        f"configuration={EXPECTED_CONFIGURATION} "
        f"project={EXPECTED_PROJECT} "
        f"region={EXPECTED_REGION} "
        f"service={EXPECTED_SERVICE} "
        f"sha={args.commit_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
