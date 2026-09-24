from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "sigroom_deploy_guard.py"
GOOD_SHA = "05d485d6621c9f7e1758b5b1c05d843bc5b43825"


def run_guard(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sigroom_guard_accepts_exact_target_and_sha():
    result = run_guard(
        "--project",
        "sixth-storm-439008-u2",
        "--region",
        "asia-southeast3",
        "--service",
        "sigroom",
        "--configuration",
        "sigroom",
        "--commit-sha",
        GOOD_SHA,
        "--head-sha",
        GOOD_SHA,
    )

    assert result.returncode == 0, result.stderr
    assert "TARGET PASS" in result.stdout


def test_sigroom_guard_blocks_emso_project():
    result = run_guard(
        "--project",
        "signal-nco-ew",
        "--region",
        "asia-southeast3",
        "--service",
        "sigroom",
        "--configuration",
        "sigroom",
        "--commit-sha",
        GOOD_SHA,
        "--head-sha",
        GOOD_SHA,
    )

    assert result.returncode == 2
    assert "BLOCKED" in result.stderr
    assert "sixth-storm-439008-u2" in result.stderr


def test_sigroom_guard_blocks_wrong_service_or_region():
    result = run_guard(
        "--project",
        "sixth-storm-439008-u2",
        "--region",
        "us-central1",
        "--service",
        "emso",
        "--configuration",
        "sigroom",
        "--commit-sha",
        GOOD_SHA,
        "--head-sha",
        GOOD_SHA,
    )

    assert result.returncode == 2
    assert "region must be 'asia-southeast3'" in result.stderr
    assert "service must be 'sigroom'" in result.stderr


def test_sigroom_guard_blocks_sha_mismatch():
    other_sha = "1" * 40
    result = run_guard(
        "--project",
        "sixth-storm-439008-u2",
        "--region",
        "asia-southeast3",
        "--service",
        "sigroom",
        "--configuration",
        "sigroom",
        "--commit-sha",
        GOOD_SHA,
        "--head-sha",
        other_sha,
    )

    assert result.returncode == 2
    assert "does not match worktree HEAD" in result.stderr
