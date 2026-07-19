from unittest.mock import patch

from shadowgrid.predeploy import run_predeploy


def test_predeploy_runs_migration_before_bootstrap() -> None:
    calls: list[str] = []

    with (
        patch(
            "shadowgrid.predeploy.command.upgrade",
            side_effect=lambda *_: calls.append("migration"),
        ) as upgrade,
        patch("shadowgrid.predeploy.bootstrap", side_effect=lambda: calls.append("bootstrap")),
    ):
        run_predeploy()

    assert calls == ["migration", "bootstrap"]
    assert upgrade.call_args.args[1] == "head"
    assert upgrade.call_args.args[0].get_main_option("script_location").endswith("migrations")
