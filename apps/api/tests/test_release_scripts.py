from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_restore_path_resolver_rejects_sibling_prefix(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required for the release scripts")
    project = tmp_path / "release-project"
    backups = project / "backups"
    sibling = project / "backups-untrusted"
    backups.mkdir(parents=True)
    sibling.mkdir()
    allowed = backups / "allowed.dump"
    outside = sibling / "outside.dump"
    allowed.touch()
    outside.touch()
    resolver = Path(__file__).resolve().parents[3] / "scripts" / "resolve-backup-path.ps1"

    accepted = subprocess.run(  # noqa: S603
        [
            powershell,
            "-NoProfile",
            "-File",
            str(resolver),
            "-ProjectRoot",
            str(project),
            "-Backup",
            str(allowed),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    rejected = subprocess.run(  # noqa: S603
        [
            powershell,
            "-NoProfile",
            "-File",
            str(resolver),
            "-ProjectRoot",
            str(project),
            "-Backup",
            str(outside),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert accepted.returncode == 0
    assert Path(accepted.stdout.strip()) == allowed.resolve()
    assert rejected.returncode != 0


def test_restore_script_restarts_services_from_finally_block() -> None:
    restore = (Path(__file__).resolve().parents[3] / "scripts" / "restore.ps1").read_text(
        encoding="utf-8"
    )

    finally_block = restore.split("finally", maxsplit=1)[1]
    assert "docker compose start api worker" in finally_block


def test_cross_platform_local_lifecycle_scripts_are_complete() -> None:
    project = Path(__file__).resolve().parents[3]
    required = [
        "setup-local",
        "start-local",
        "stop-local",
        "reset-local",
        "verify-local",
    ]

    for stem in required:
        powershell_script = project / "scripts" / f"{stem}.ps1"
        shell_script = project / "scripts" / f"{stem}.sh"
        assert powershell_script.is_file()
        assert shell_script.is_file()
        assert "$ErrorActionPreference = 'Stop'" in powershell_script.read_text(encoding="utf-8")
        assert "set -euo pipefail" in shell_script.read_text(encoding="utf-8")


def test_local_reset_scripts_require_exact_confirmation_and_bound_the_database_path() -> None:
    project = Path(__file__).resolve().parents[3]
    powershell_reset = (project / "scripts" / "reset-local.ps1").read_text(encoding="utf-8")
    shell_reset = (project / "scripts" / "reset-local.sh").read_text(encoding="utf-8")

    assert "[ValidateSet('RESET')]" in powershell_reset
    assert "StartsWith($localRoot" in powershell_reset
    assert 'confirmation" != "RESET' in shell_reset
    assert '"$shadowgrid_root/.local/"*' in shell_reset


def test_local_start_verifies_worker_and_never_prints_credentials() -> None:
    project = Path(__file__).resolve().parents[3]
    for suffix in ("ps1", "sh"):
        start = (project / "scripts" / f"start-local.{suffix}").read_text(encoding="utf-8")
        verify = (project / "scripts" / f"verify-local.{suffix}").read_text(encoding="utf-8")
        assert "worker" in start
        assert "worker" in verify
        assert "data:verify" in verify
        assert "contents intentionally not printed" in start


def test_lifecycle_plan_maps_every_required_step_persona_and_browser_project() -> None:
    project = Path(__file__).resolve().parents[3]
    plan = json.loads((project / "scripts" / "lifecycle-plan.json").read_text(encoding="utf-8"))
    runner = (project / "scripts" / "verify-lifecycle.mjs").read_text(encoding="utf-8")
    required_personas = {
        "entrepreneur",
        "investor",
        "cartel_leader",
        "cartel_member",
        "intelligence_strategist",
        "administrator",
        "local_ai_player",
    }

    assert plan["schema_version"] == 1
    assert set(plan["personas"]) == required_personas
    assert [step["number"] for step in plan["steps"]] == list(range(1, 31))
    assert all(step["api_tests"] and step["e2e_specs"] for step in plan["steps"])
    assert '"chromium", "mobile"' in runner
    assert '"playwright"' in runner
