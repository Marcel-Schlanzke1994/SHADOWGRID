from shadowgrid.production import process_commands


def test_production_supervisor_starts_worker_and_api() -> None:
    commands = process_commands("9123")

    assert commands[0][-2:] == ["arq", "apps.worker.worker.WorkerSettings"]
    assert "uvicorn" in commands[1]
    assert commands[1][commands[1].index("--port") + 1] == "9123"
