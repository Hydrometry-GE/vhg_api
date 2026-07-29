"""Display project readiness before running the numbered manual tests."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from vhg_api import __version__
from vhg_api.console import print_header, print_success, print_warning


def main() -> None:
    print_header("vhg_api - Project information")
    print(f"Version      : {__version__}")
    print(f"Python       : {platform.python_version()}")
    print(f"Interpreter  : {sys.executable}")
    print(f"Platform     : {platform.platform()}")
    print(f"Project root : {PROJECT_ROOT}")
    print()

    required = [
        PROJECT_ROOT / "config" / "settings.yml",
        PROJECT_ROOT / "config" / "sources.csv",
    ]
    for path in required:
        if path.exists():
            print_success(f"Found {path.relative_to(PROJECT_ROOT)}")
        else:
            print_warning(f"Missing {path.relative_to(PROJECT_ROOT)}")

    env_path = PROJECT_ROOT / "config" / ".env"
    if env_path.exists():
        print_success("Found config/.env")
    else:
        print_warning("config/.env is missing; copy config/.env.example first")

    print()
    print("Next manual test: scripts/test/01_test_config.py")


if __name__ == "__main__":
    main()
