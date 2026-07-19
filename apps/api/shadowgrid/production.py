"""Supervise the fixed ARQ and Uvicorn production commands without a shell."""

from __future__ import annotations

import os
import signal
import subprocess  # nosec B404
import sys
import time
from collections.abc import Sequence

CONTAINER_BIND_HOST = "0.0.0.0"  # noqa: S104  # nosec B104


def process_commands(port: str) -> list[list[str]]:
    return [
        [sys.executable, "-m", "arq", "apps.worker.worker.WorkerSettings"],
        [
            sys.executable,
            "-m",
            "uvicorn",
            "shadowgrid.main:app",
            "--host",
            CONTAINER_BIND_HOST,
            "--port",
            port,
            "--proxy-headers",
        ],
    ]


def stop_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 10
    for process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    # Every command comes from process_commands(); shell expansion is never enabled.
    processes = [
        subprocess.Popen(command)  # noqa: S603  # nosec B603
        for command in process_commands(os.getenv("PORT", "8000"))
    ]
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while not stopping:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    return return_code or 1
            time.sleep(0.5)
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
