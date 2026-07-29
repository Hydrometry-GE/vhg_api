"""Repository-local entry point for manual or scheduled downloads.

The wrapper makes the project package importable without installation and
resolves the CLI's default ``config/`` paths from the repository root. All
arguments are forwarded unchanged to :func:`vhg_api.cli.main`.

Examples
--------
Validate the deployment configuration::

    python scripts/run_download.py validate-config

Run the configured incremental update::

    python scripts/run_download.py download
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vhg_api.cli import main  # noqa: E402


if __name__ == "__main__":
    # Relative defaults such as config/settings.yml must be interpreted from
    # the repository root, not from Spyder's or cron's current directory.
    os.chdir(PROJECT_ROOT)
    raise SystemExit(main())
